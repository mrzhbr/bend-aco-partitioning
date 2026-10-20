"""Run with python3 -m aco.test_aco; standard library unless noted."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from . import numpy_baseline, reference

ROOT = Path(__file__).resolve().parent
BINARY = ROOT / "build" / "aco"
ORIGINAL = ROOT / "original_numpy.py"


def load_original(path):
    spec = importlib.util.spec_from_file_location("nic_original", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ACOTests(unittest.TestCase):
    def invoke(self, args, threads=4):
        return subprocess.run(
            [str(BINARY), "--threads", str(threads), *map(str, args)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def run_aco(
        self,
        problem=1,
        ants=10,
        evaporation=0.3,
        budget=100,
        seed=0,
        mode="parallel",
        items=None,
        bins=None,
        threads=4,
    ):
        args = [problem, ants, evaporation, budget, seed, mode]
        if items is not None:
            args.extend([items, bins])
        process = self.invoke(args, threads)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        try:
            result = json.loads(process.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"Invalid native JSON: {process.stdout!r}; stderr: {process.stderr}"
            )
        self.assertEqual(result["evaluations"], ((budget + ants - 1) // ants) * ants)
        path = result["best_path"]
        self.assertEqual(len(path), result["items"])
        self.assertTrue(all(0 <= bin_index < result["bins"] for bin_index in path))
        loads = [0] * result["bins"]
        for bin_index, weight in zip(
            path, reference.weights(problem, result["items"]), strict=True
        ):
            loads[bin_index] += weight
        self.assertEqual(sum(loads), sum(reference.weights(problem, result["items"])))
        self.assertEqual(max(loads) - min(loads), result["best_quarters"])
        self.assertLessEqual(result["best_quarters"], result["final_quarters"])
        self.assertEqual(result["best"], result["best_quarters"] / 4)
        self.assertEqual(result["final"], result["final_quarters"] / 4)
        return result

    def test_full_small_trajectories_match_independent_reference(self):
        for problem in (1, 2):
            for items, bins, ants, budget in [
                (1, 1, 1, 1),
                (3, 5, 2, 7),
                (9, 3, 5, 31),
                (17, 7, 10, 40),
            ]:
                for evaporation in (0.05, 0.3):
                    with self.subTest(
                        problem=problem, items=items, bins=bins, evaporation=evaporation
                    ):
                        seed = 4294967295 if items == 1 else 42
                        expected = reference.run(
                            problem, items, bins, ants, evaporation, budget, seed
                        )
                        actual = self.run_aco(
                            problem,
                            ants,
                            evaporation,
                            budget,
                            seed,
                            items=items,
                            bins=bins,
                        )
                        for key, value in expected.items():
                            self.assertEqual(actual[key], value, key)

    def test_generation_prefixes_match_reference(self):
        for problem in (1, 2):
            for budget in (4, 8, 12, 16, 20):
                with self.subTest(problem=problem, budget=budget):
                    expected = reference.run(problem, 11, 5, 4, 0.3, budget, 9)
                    actual = self.run_aco(problem, 4, 0.3, budget, 9, items=11, bins=5)
                    for key, value in expected.items():
                        self.assertEqual(actual[key], value, key)

    def test_real_problem_parameters_match_across_modes_and_threads(self):
        for problem in (1, 2):
            for ants in (10, 50):
                for evaporation in (0.05, 0.3):
                    with self.subTest(
                        problem=problem, ants=ants, evaporation=evaporation
                    ):
                        sequential = self.run_aco(
                            problem, ants, evaporation, 150, 3, "sequential", threads=1
                        )
                        parallel = self.run_aco(
                            problem, ants, evaporation, 150, 3, "parallel", threads=4
                        )
                        for key in (
                            "final_quarters",
                            "best_quarters",
                            "best_path",
                            "evaluations",
                        ):
                            self.assertEqual(sequential[key], parallel[key], key)

    def test_packed_padding_and_short_runs_match_independent_reference(self):
        for problem, bins in ((1, 12), (2, 40)):
            for items in (1, 15, 16, 17, 31, 33):
                for evaporation in (0, 0.3, 0.99999994):
                    with self.subTest(
                        problem=problem, items=items, evaporation=evaporation
                    ):
                        expected = reference.run(
                            problem, items, bins, 3, evaporation, 14, 42
                        )
                        for mode in ("packed-sequential", "packed-parallel"):
                            actual = self.run_aco(
                                problem,
                                3,
                                evaporation,
                                14,
                                42,
                                mode=mode,
                                items=items,
                                bins=bins,
                            )
                            for key, value in expected.items():
                                self.assertEqual(actual[key], value, (mode, key))

    def test_packed_full_budget_matches_generic_engine_for_all_settings(self):
        for problem in (1, 2):
            for ants in (10, 50):
                for evaporation in (0.05, 0.3):
                    with self.subTest(
                        problem=problem, ants=ants, evaporation=evaporation
                    ):
                        expected = self.run_aco(
                            problem,
                            ants,
                            evaporation,
                            10000,
                            0,
                            "sequential",
                            threads=1,
                        )
                        for mode in ("packed-sequential", "packed-parallel"):
                            actual = self.run_aco(
                                problem, ants, evaporation, 10000, 0, mode=mode
                            )
                            for key in (
                                "final_quarters",
                                "best_quarters",
                                "best_path",
                                "evaluations",
                            ):
                                self.assertEqual(
                                    actual[key], expected[key], (mode, key)
                                )

    def test_packed_fallback_and_oversized_population(self):
        for bins in (1, 3, 12, 40, 64):
            expected = self.run_aco(2, 50, 0.3, 3, 7, "sequential", items=17, bins=bins)
            actual = self.run_aco(
                2, 50, 0.3, 3, 7, "packed-parallel", items=17, bins=bins
            )
            self.assertEqual(actual["best_path"], expected["best_path"])
            self.assertEqual(actual["final_quarters"], expected["final_quarters"])

    def test_generated_kernels_are_current(self):
        from .generate_packed import render

        self.assertEqual((ROOT / "packed.bend").read_text(), render())

    def test_seed_changes_the_search(self):
        first = self.run_aco(items=17, bins=5, seed=0)
        second = self.run_aco(items=17, bins=5, seed=1)
        self.assertNotEqual(first["best_path"], second["best_path"])

    def test_more_budget_cannot_worsen_best_ever(self):
        shorter = self.run_aco(budget=20, items=19, bins=5)
        longer = self.run_aco(budget=100, items=19, bins=5)
        self.assertLessEqual(longer["best_quarters"], shorter["best_quarters"])

    def test_population_larger_than_budget_is_not_truncated(self):
        self.run_aco(ants=50, budget=3, items=7, bins=3)

    def test_no_evaporation(self):
        actual = self.run_aco(evaporation=0, items=7, bins=3)
        expected = reference.run(1, 7, 3, 10, 0, 100, 0)
        self.assertEqual(actual["best_path"], expected["best_path"])

    def test_invalid_arguments_fail(self):
        cases = [
            [],
            [1, 10],
            [0, 10, 0.3, 100, 0, "parallel"],
            [1, 0, 0.3, 100, 0, "parallel"],
            [1, 513, 0.3, 100, 0, "parallel"],
            [1, 10, -0.1, 100, 0, "parallel"],
            [1, 10, 1, 100, 0, "parallel"],
            [1, 10, "nan", 100, 0, "parallel"],
            [1, 10, "inf", 100, 0, "parallel"],
            [1, 10, 0.3, 0, 0, "parallel"],
            [1, 10, 0.3, 1000001, 0, "parallel"],
            [1, 10, 0.3, 100, -1, "parallel"],
            [1, 10, 0.3, 100, "4294967296", "parallel"],
            [1, 10, 0.3, 100, 0, "invalid"],
            [1, 10, 0.3, 100, 0, "parallel", 0, 3],
            [1, 10, 0.3, 100, 0, "parallel", 601, 3],
            [1, 10, 0.3, 100, 0, "parallel", 6, 65],
            [1, 10, 0.3, 100, 0, "parallel", 6],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertNotEqual(self.invoke(args).returncode, 0)

    @unittest.skipUnless(
        importlib.util.find_spec("numpy"), "NumPy required for benchmark smoke test"
    )
    def test_packed_benchmark_handles_tiny_budget_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packed.json"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aco.benchmark_packed",
                    "--problem",
                    "1",
                    "--ants",
                    "10",
                    "--evaporation",
                    "0.3",
                    "--evaluations",
                    "1",
                    "--repeat",
                    "1",
                    "--threads",
                    "1",
                    "--output",
                    str(output),
                ],
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            try:
                artifact = json.loads(output.read_text())
            except (OSError, json.JSONDecodeError) as error:
                self.fail(str(error))
            self.assertEqual(artifact["parameters"]["evaluations"], 1)
            self.assertEqual(len(artifact["runs"]), 3)
            self.assertEqual(
                artifact["summary"][0]["recommended_engine"], "packed_sequential"
            )
            for run in artifact["runs"]:
                if run["engine"].startswith("packed_"):
                    self.assertEqual(run["result"]["evaluations"], 10)

    def test_benchmark_rejects_unrepresentable_rate_before_running(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "aco.benchmark",
                    "--skip-original",
                    "--evaporation",
                    "0.99999999",
                    "--output",
                    str(output),
                ],
                cwd=ROOT.parent,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            self.assertEqual(process.returncode, 2)
            self.assertIn("F32", process.stderr)
            self.assertFalse(output.exists())

    @unittest.skipUnless(
        ORIGINAL.is_file() and importlib.util.find_spec("numpy"),
        "local original + NumPy required",
    )
    def test_vectorized_numpy_preserves_original_seeded_results(self):
        original = load_original(ORIGINAL)
        for problem in (original.bpp1, original.bpp2):
            weights, _ = problem()
            for ants, evaporation, budget in [(3, 0.05, 14), (5, 0.3, 30)]:
                for seed in (0, 42):
                    with self.subTest(problem=problem.__name__, ants=ants, seed=seed):
                        expected = original.aco(
                            weights[:25], 5, ants, evaporation, budget, seed
                        )
                        actual = numpy_baseline.aco(
                            weights[:25], 5, ants, evaporation, budget, seed
                        )
                        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
