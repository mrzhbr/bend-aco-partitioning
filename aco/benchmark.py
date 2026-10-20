"""Measure original NumPy, vectorized NumPy, and native Bend without conflating RNGs."""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

from . import numpy_baseline, reference

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "build" / "aco"


def load_original(path):
    spec = importlib.util.spec_from_file_location("nic_benchmark_original", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import original source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native(problem, args, seed, parallel, budget, mode=None):
    start = time.perf_counter()
    process = subprocess.run(
        [
            str(BINARY),
            "--threads",
            str(args.threads if parallel else 1),
            str(problem),
            str(args.ants),
            str(args.evaporation),
            str(budget),
            str(seed),
            mode or ("parallel" if parallel else "sequential"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    wall_ms = (time.perf_counter() - start) * 1000
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Invalid Bend output: {process.stdout!r}") from error
    path = result["best_path"]
    if len(path) != result["items"] or any(b < 0 or b >= result["bins"] for b in path):
        raise RuntimeError("Invalid Bend assignment")
    loads = [0] * result["bins"]
    for bin_index, weight in zip(
        path, reference.weights(problem, result["items"]), strict=True
    ):
        loads[bin_index] += weight
    if max(loads) - min(loads) != result["best_quarters"]:
        raise RuntimeError("Bend fitness does not match its returned assignment")
    if result["evaluations"] != ((budget + args.ants - 1) // args.ants) * args.ants:
        raise RuntimeError("Unexpected Bend evaluation budget")
    return {"function_ms": result["elapsed_ms"], "wall_ms": wall_ms, "result": result}


def python_run(function, weights, bins, args, seed, budget):
    start = time.perf_counter()
    final, best = function(weights, bins, args.ants, args.evaporation, budget, seed)
    elapsed = (time.perf_counter() - start) * 1000
    return {
        "function_ms": elapsed,
        "wall_ms": elapsed,
        "result": {"final": final, "best": best},
    }


def check_pair(records):
    by_engine = {record["engine"]: record["result"] for record in records}
    if (
        "original_numpy" in by_engine
        and by_engine["original_numpy"] != by_engine["vectorized_numpy"]
    ):
        raise RuntimeError("Vectorized NumPy changed original seeded results")
    a, b = by_engine["bend_sequential"], by_engine["bend_parallel"]
    for key in ("final_quarters", "best_quarters", "best_path", "evaluations"):
        if a[key] != b[key]:
            raise RuntimeError(f"Bend modes diverged: {key}")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--problem", nargs="+", type=int, choices=(1, 2), default=[1, 2]
    )
    parser.add_argument("--ants", type=int, default=50)
    parser.add_argument("--evaporation", type=float, default=0.3)
    parser.add_argument("--evaluations", type=int, default=10000)
    parser.add_argument(
        "--repeat", type=int, default=3, help="number of consecutive distinct seeds"
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument(
        "--original", type=Path, default=ROOT / "original_numpy.py"
    )
    parser.add_argument("--skip-original", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "results" / "benchmark.json"
    )
    args = parser.parse_args()
    if not 1 <= args.ants <= 512 or not 1 <= args.evaluations <= 1000000:
        parser.error("ants must be 1..512; evaluations must be 1..1000000")
    if not math.isfinite(args.evaporation) or not 0 <= args.evaporation < 1:
        parser.error("evaporation must be finite and in [0,1)")
    if reference.f32(args.evaporation) >= 1:
        parser.error("evaporation must remain below 1 after F32 rounding")
    if (
        args.repeat < 1
        or args.threads < 1
        or not 0 <= args.seed <= 4294967296 - args.repeat
    ):
        parser.error("invalid repeats, threads or U32 seed range")
    return args


def execute(engine, seed, budget, problem, args, functions, weights, bins):
    if engine.startswith("bend_"):
        return native(problem, args, seed, engine == "bend_parallel", budget)
    return python_run(functions[engine], weights, bins, args, seed, budget)


def measure(args, original):
    import numpy as np

    records = []
    engines = ["vectorized_numpy", "bend_sequential", "bend_parallel"]
    if original is not None:
        engines.insert(0, "original_numpy")
    for problem in args.problem:
        count, bins = (600, 12) if problem == 1 else (400, 40)
        weights = np.array(reference.weights(problem, count), dtype=np.float64) / 4
        functions = {"vectorized_numpy": numpy_baseline.aco}
        if original is not None:
            functions["original_numpy"] = original.aco

        # Short warm-ups load code without adding an entire slow Python trial.
        for engine in engines:
            execute(
                engine,
                args.seed,
                min(args.evaluations, args.ants * 2),
                problem,
                args,
                functions,
                weights,
                bins,
            )
        for trial in range(args.repeat):
            seed = args.seed + trial
            order = engines[trial % len(engines) :] + engines[: trial % len(engines)]
            paired = []
            for engine in order:
                result = execute(
                    engine,
                    seed,
                    args.evaluations,
                    problem,
                    args,
                    functions,
                    weights,
                    bins,
                )
                record = {"problem": problem, "seed": seed, "engine": engine, **result}
                records.append(record)
                paired.append(record)
                print(
                    f"Instance {problem} seed={seed} {engine:17s} {result['function_ms']:9.2f} ms "
                    f"final={result['result']['final']} best={result['result']['best']}",
                    flush=True,
                )
            check_pair(paired)
    return records


def main():
    args = arguments()
    import numpy as np

    original = None
    source_hash = None
    if not args.skip_original:
        if not args.original.is_file():
            raise RuntimeError(
                "Original source not found; provide --original PATH or use --skip-original"
            )
        original = load_original(args.original)
        source_hash = hashlib.sha256(args.original.read_bytes()).hexdigest()
    records = measure(args, original)
    summary = []
    for problem in args.problem:
        print(f"\nInstance {problem}: median over {args.repeat} distinct seeds")
        for engine in dict.fromkeys(record["engine"] for record in records):
            group = [
                r for r in records if r["problem"] == problem and r["engine"] == engine
            ]
            entry = {
                "problem": problem,
                "engine": engine,
                "function_ms": statistics.median(r["function_ms"] for r in group),
                "wall_ms": statistics.median(r["wall_ms"] for r in group),
            }
            summary.append(entry)
            print(
                f"  {engine:17s} {entry['function_ms']:9.2f} ms function; {entry['wall_ms']:9.2f} ms wall"
            )
    artifact = {
        "schema": 1,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "bend_version": "2.0.37",
        "original_source_sha256": source_hash,
        "parameters": {
            "ants": args.ants,
            "evaporation": args.evaporation,
            "evaluations": args.evaluations,
            "threads": args.threads,
            "repeat": args.repeat,
            "first_seed": args.seed,
        },
        "method": "Rotate engine order; distinct seeds; short unmeasured warmups. Bend function clock is milliseconds. Python function timing excludes imports; Bend wall includes subprocess startup. No trajectory equality between NumPy and Bend is claimed.",
        "summary": summary,
        "runs": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"\nSaved {args.output}")


if __name__ == "__main__":
    main()
