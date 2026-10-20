"""Interleaved, full-budget packed Bend versus vectorized NumPy comparison.

A fixed policy is declared before measurement: sequential for 10 ants, parallel
for 50. Both native modes are always measured and checked for identical outputs.
"""

import argparse
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path

from . import benchmark, numpy_baseline, reference

ROOT = Path(__file__).resolve().parent


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--problem", type=int, nargs="+", choices=(1, 2), default=[1, 2]
    )
    parser.add_argument(
        "--ants", type=int, nargs="+", choices=(10, 50), default=[10, 50]
    )
    parser.add_argument(
        "--evaporation", type=float, nargs="+", choices=(0.05, 0.3), default=[0.05, 0.3]
    )
    parser.add_argument("--evaluations", type=int, default=10000)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument(
        "--output", type=Path, default=ROOT / "results" / "packed-benchmark.json"
    )
    args = parser.parse_args()
    if not 1 <= args.evaluations <= 1000000 or args.repeat < 1 or args.threads < 1:
        parser.error("invalid evaluation count, repeats or threads")
    if not 0 <= args.seed <= 4294967296 - args.repeat:
        parser.error("seeds must fit U32")
    return args


def verify_pair(pair):
    a = pair["packed_sequential"]["result"]
    b = pair["packed_parallel"]["result"]
    for field in ("final_quarters", "best_quarters", "best_path", "evaluations"):
        if a[field] != b[field]:
            raise RuntimeError(f"Native modes diverged: {field}")


def summary_for(config, records):
    summaries = {}
    for engine in ("vectorized_numpy", "packed_sequential", "packed_parallel"):
        group = [row for row in records if row["engine"] == engine]
        summaries[engine] = {
            "function_ms": statistics.median(row["function_ms"] for row in group),
            "wall_ms": statistics.median(row["wall_ms"] for row in group),
            "min_ms": min(row["function_ms"] for row in group),
            "max_ms": max(row["function_ms"] for row in group),
        }
    recommended = "packed_sequential" if config["ants"] == 10 else "packed_parallel"
    native = summaries[recommended]
    numpy = summaries["vectorized_numpy"]
    return {
        **config,
        "engines": summaries,
        "recommended_engine": recommended,
        "function_speedup": numpy["function_ms"] / native["function_ms"]
        if native["function_ms"]
        else None,
        "wall_speedup": numpy["wall_ms"] / native["wall_ms"]
        if native["wall_ms"]
        else None,
    }


def ratio_text(value):
    return "n/a (timer resolution)" if value is None else f"{value:.2f}x"


def run(args):
    import numpy as np

    results = []
    summaries = []
    order = ["vectorized_numpy", "packed_sequential", "packed_parallel"]
    for problem in args.problem:
        items, bins = (600, 12) if problem == 1 else (400, 40)
        weights = np.array(reference.weights(problem, items), dtype=np.float64) / 4
        for ants in args.ants:
            for evaporation in args.evaporation:
                config = {
                    "problem": problem,
                    "ants": ants,
                    "evaporation": evaporation,
                    "evaluations": args.evaluations,
                    "threads": args.threads,
                }
                options = argparse.Namespace(
                    ants=ants, evaporation=evaporation, threads=args.threads
                )

                def execute(
                    engine,
                    seed,
                    budget,
                    options=options,
                    weights=weights,
                    problem=problem,
                    bins=bins,
                ):
                    if engine == "vectorized_numpy":
                        return benchmark.python_run(
                            numpy_baseline.aco, weights, bins, options, seed, budget
                        )
                    parallel = engine == "packed_parallel"
                    mode = "packed-parallel" if parallel else "packed-sequential"
                    return benchmark.native(
                        problem, options, seed, parallel, budget, mode=mode
                    )

                for engine in order:
                    execute(engine, args.seed, min(args.evaluations, ants * 2))
                rows = []
                for trial in range(args.repeat):
                    seed = args.seed + trial
                    rotated = order[trial % len(order) :] + order[: trial % len(order)]
                    pair = {}
                    for engine in rotated:
                        load = os.getloadavg()
                        sample = execute(engine, seed, args.evaluations)
                        pair[engine] = sample
                        row = {
                            **config,
                            "engine": engine,
                            "seed": seed,
                            "load_average_before": load,
                            **sample,
                        }
                        rows.append(row)
                        results.append(row)
                    verify_pair(pair)
                summary = summary_for(config, rows)
                summaries.append(summary)
                selected = summary["engines"][summary["recommended_engine"]]
                print(
                    f"Instance {problem} p={ants} e={evaporation}: "
                    f"NumPy {summary['engines']['vectorized_numpy']['function_ms']:.2f} ms, "
                    f"Bend {selected['function_ms']:.2f} ms "
                    f"({ratio_text(summary['function_speedup'])} function, {ratio_text(summary['wall_speedup'])} wall)",
                    flush=True,
                )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "core.bend",
            "fast.bend",
            "packed.bend",
            "main.bend",
            "numpy_baseline.py",
            "generate_packed.py",
        )
    }
    return {
        "schema": 1,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "parameters": {
            "problems": args.problem,
            "ants": args.ants,
            "evaporation": args.evaporation,
            "evaluations": args.evaluations,
            "repeat": args.repeat,
            "first_seed": args.seed,
            "parallel_threads": args.threads,
        },
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "bend_version": "2.0.37",
        "source_sha256": hashes,
        "binary_sha256": hashlib.sha256(benchmark.BINARY.read_bytes()).hexdigest(),
        "policy": "Before timing: sequential for 10 ants, parallel for 50; both always measured. No post-hoc fastest-mode selection.",
        "method": "Full budgets, rotating engine order per seed, short untimed warmups. NumPy excludes interpreter/import startup. Bend function time excludes subprocess startup; wall time includes it. Native outputs must match each other, not NumPy's different RNG/F64 trajectory. Every returned native best assignment is independently rescored.",
        "summary": summaries,
        "runs": results,
    }


def main():
    args = arguments()
    artifact = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
