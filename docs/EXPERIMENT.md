# ACO: multi-way number partitioning in Bend 2

Detailed notes for an exploratory load-balancing experiment. The scalar-walk
NumPy baseline is bundled as `aco/original_numpy.py`, alongside vectorized NumPy
and reference/packed Bend implementations. The bundled original adds only
positive-budget/population validation and lint cleanup; valid-input ACO rules
and random-number consumption are unchanged. No sibling project is required.
Some source-level `bpp1`/`bpp2` names are legacy instance identifiers, not a claim
that this is conventional bin packing.

## Run

From the repository root:

```sh
make -C aco setup           # only if the pinned local Bend compiler is missing
make -C aco test            # 20 generic + 14 packed checks + 15 integration tests + proofs

# problem ants evaporation evaluations seed mode
# Recommended packed kernels: four workers for 50 ants, sequential for 10.
./aco/build/aco --threads 4 1 50 0.30 10000 0 packed-parallel
./aco/build/aco --threads 1 2 10 0.05 10000 4 packed-sequential

# Original generic Bend engine remains available for reference/parity checks.
./aco/build/aco --threads 1 1 50 0.30 10000 0 sequential

# Tiny instances for inspecting/debugging the same weight formulas.
# Optional trailing arguments: items bins.
./aco/build/aco --threads 4 2 5 0.30 31 42 parallel 9 3
```

Uses pinned **Bend 2.0.37**, installed at `.tools/bend/bin/bend` in the repo root.
Native builds require clang 14+. Tests and tooling use Python 3.10+; only the
optional original-versus-vectorized test and benchmarking require NumPy. The
native solver and independent F32 reference have no NumPy dependency. No new
packages were installed.

The executable emits one JSON object containing the configuration, actual number
of evaluations, internal elapsed milliseconds, final-population best, best-ever
fitness, and the best-ever assignment (`best_path`, zero-based bin indices).
`*_quarters` fields are exact integer fitnesses in quarter-weight units;
`final` and `best` are formatted back in the original units. Timing excludes
argument validation, JSON formatting and process startup; the benchmark records
subprocess wall time separately.

## Problem and preserved algorithm

This is **multi-way number partitioning**, not capacity-constrained bin packing.
Each number belongs to one of a fixed number of groups. The objective is
`max(group_loads) - min(group_loads)` (load range), rather than minimizing only
`max(group_loads)` (makespan). The code uses “bins” for the groups.

| Instance | Numbers | Groups | Weight of number i, starting at 1 |
| --- | ---: | ---: | --- |
| 1 | 600 | 12 | `2*i + 1` |
| 2 | 400 | 40 | `i*i / 4` |

Each generation follows the original ordering:

1. Construct the entire population using one unchanged pheromone snapshot.
2. Evaluate every ant, including real empty bins in the minimum.
3. Deposit `100 / (fitness + 1)` for **every** ant, in population order.
4. Evaporate all pheromones by multiplying by `1 - evaporation`.
5. Record the final-population best and the best-ever result separately.

There is no extra balancing heuristic, elitist update or local search. Like the
Python original, a budget not divisible by population size rounds **up** to a
whole generation. The JSON exposes that actual evaluation count.

CLI bounds: problem 1 or 2, ants 1–512, requested evaluations 1–1,000,000,
seed 0–4,294,967,295, evaporation finite and in `[0,1)` after F32 parsing. Custom
validation sizes accept 1–600 items and 1–64 bins. These bounds keep all integer
loads within U32; arbitrary larger instances would need a new overflow analysis.

## Implementation choices

The original `core.bend` reference engine uses the following representation:

- **Exact integer loads:** multiply every weight by four. Instance 1 uses `4*(2*i+1)`;
  instance 2 uses `i*i`. Full-instance totals are 1,444,800 and 21,413,400, well within
  U32. Convert fitness back before computing the pheromone reward; forgetting
  that conversion changes the algorithm. Runtime tests cover the quarter-unit case.
- **Weighted binary trees:** pheromone leaves hold masses; internal nodes cache
  their child-mass sums. Roulette selection descends in logarithmic time, without
  allocating a probability vector and CDF for every ant/item decision. Padded
  bins have zero mass and are excluded from load fitness.
- **Owned load arrays:** each ant owns its array and path. Ants share only the
  immutable pheromone snapshot; there are no shared mutable arrays or atomics.
- **Explicit fork–join:** parallel mode splits ants into eight balanced batches;
  sequential mode uses zero forks. Deposits and evaporation remain serial.
- **Deterministic streams:** each generation/ant gets a stream derived from the
  run seed and stable indices. Scheduling cannot change the random sequence.

### Packed engine (`packed-sequential` / `packed-parallel`)

The new engine is **pure Bend**, generated reproducibly by `generate_packed.py`
into `packed.bend`, with common support in `fast.bend`. No foreign C kernels,
compiler patches, fast-math flags or new packages are involved. Specialization
is for **12 or 40 bins**, not particular seeds or solutions. Other bin counts
fall back to the generic engine, including when a packed mode is requested.

The initial stage probe identified deposits as the largest cost: about 443 ms
of 575 ms on instance 1 and 566 ms of 817 ms on instance 2. These diagnostic timings include
instrumentation boundaries, not a separate fair benchmark of the final engines.

The rewrite:

1. Keeps a packed immutable row snapshot, with cached pairwise subtree masses.
   Predicated roulette selection uses the same comparisons, F32 subtractions,
   right-side ties and final clamp as the reference.
2. Stores sixteen consecutive item choices per path cell, cutting path-node
   allocation. Row blocks have the same width.
3. Scans each ant's owned load buffer directly at completion, rather than
   converting it to a list. This lets the native backend keep the walk flat.
4. Transposes choices one block at a time into ordered ant columns.
5. Updates each row independently in scalar registers, retaining **ant-order
   reward additions**, then evaporates its leaves. Internal sums are rebuilt
   **once per row/generation**, not after every deposit: nobody samples those
   intermediate sums. Predicated nonmatching rewards add positive zero, which
   preserves the finite nonnegative masses this solver constructs; this is not
   a claim about arbitrary F32 NaNs or signed-zero inputs.
6. Parallelizes both ant batches and independent row-update batches, without
   shared mutation. Tests require packed/generic and sequential/parallel output
   equality, including the returned assignment.

The last partial block is padded with zero-weight items, and returned paths are
truncated to the real item count. Extra trailing RNG draws affect no real item:
the existing Bend reference restarts each ant's stream in every generation.
No real item or fitness evaluation is skipped.

For the measured workloads, parallel overhead is not worthwhile at 10 ants.
The fixed recommendation is therefore sequential for 10 and parallel for 50;
both modes are still measured in the benchmark. Four workers worked better than
eight on this machine. These are explicit execution choices, not algorithm changes.

### Important reproducibility boundary

Bend uses **F32 pheromones**, **xorshift32** with hashed per-ant streams, and
**pairwise tree sums**. The original uses NumPy **F64**, **PCG64**, and linear
CDF construction. The same integer seed therefore does **not** mean the same
trajectory or solution across NumPy and Bend. This port preserves the ACO update
rules and fitness, not NumPy's floating-point or RNG implementation. Small
floating-point differences can change an entire adaptive search trajectory.

Within Bend, sequential and parallel results are required to match exactly.
Separately, the vectorized NumPy baseline is required to match the original's
seeded final/best-ever scores. Neither check implies NumPy/Bend equality.

## Tests and laws

- `tests.bend`: 20 numerical checks for weights, exact totals, roulette endpoint
  conventions, zero-mass padding, deposit magnitudes, evaporation, empty bins,
  nonzero RNG streams and quarter-unit reward scaling.
- `packed_tests.bend`: 14 kernel checks, including 2,000 direct roulette
  comparisons, zero-total rows, exact ties and upper clamps for both bin counts.
- `reference.py`: independent standard-library F32/tree/RNG implementation.
- `test_aco.py`: end-to-end small instances and generation prefixes against the
  reference, assignment/fitness recomputation, reproducibility across native
  modes, real instance configurations, budget rounding and invalid arguments.
  Packed tests cover 16-item boundaries, incomplete blocks, real empty bins,
  near-one evaporation, all eight standard settings at the full 10,000-evaluation
  budget, oversized populations, fallback dimensions and generated-file freshness.
  The NumPy comparison test uses the bundled original and skips if NumPy is absent.
- `LAWS.bend` / `PROOF.bend`: structural induction proving that evaporation
  preserves every bin label and tree decision boundary, plus a law that unpacking
  a sixteen-choice block preserves its order. These are **not** proofs of
  floating-point probabilities, full solver correctness, or search optimality.

```sh
make -C aco proof
# Equivalent to running the compiler from the proof's folder:
(cd aco && ../.tools/bend/bin/bend PROOF.bend)
```

The standard Bend checker accepts the proof. The optional independent
`--verdict` kernel was **not** run successfully: Lean v4.34.0 is not installed.
No Lean installation was attempted.

## Packed benchmark (current)

```sh
make -C aco bench-packed
# Exact latest measurement command:
python3 -m aco.benchmark_packed --seed 100 --repeat 5 --threads 4

# Diagnostic stage profiles, separate from the performance benchmark:
make -C aco profile
```

The current benchmark uses all **eight** standard problem/population/evaporation
configurations, **10,000 evaluations** each, and **five untuned seeds (100–104)**.
It rotates engine order, warms up outside timing, and measures NumPy plus both
packed native modes. The execution policy was fixed before the holdout run:
sequential for 10 ants; four-worker parallel for 50. Every native best assignment
is independently rescored, and native modes must match each other exactly.

Latest medians (solver time, milliseconds):

| Instance | Ants | Evaporation | Vectorized NumPy | Packed Bend | Speedup |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 10 | 0.05 | 256.43 | 87 | 2.95× |
| 1 | 10 | 0.30 | 249.31 | 86 | 2.90× |
| 1 | 50 | 0.05 | 280.38 | 139 | 2.02× |
| 1 | 50 | 0.30 | 216.88 | 86 | 2.52× |
| 2 | 10 | 0.05 | 280.88 | 110 | 2.55× |
| 2 | 10 | 0.30 | 283.05 | 114 | 2.48× |
| 2 | 50 | 0.05 | 239.23 | 82 | 2.92× |
| 2 | 50 | 0.30 | 235.48 | 81 | 2.91× |

This is **2.02–2.95× faster** than the existing vectorized NumPy baseline on
solver time, or **1.93–2.82×** when charging Bend for subprocess startup while
still excluding interpreter/import startup from NumPy. It is not a claim against
every possible NumPy implementation or for larger/different bin counts.

Other experiments were running on this machine; these are **not isolated idle
machine measurements**. A previous identical-source run under heavier contention
is retained as `aco/results/packed-benchmark-contended.json` (1.32–2.96× on wall time).
Parallel scaling is sensitive to that contention. The latest raw artifact is
**`aco/results/packed-benchmark.json`**: all 120 timed runs, both native modes,
per-run load averages, timing ranges, outcomes, and source/binary hashes. Do not
compare absolute times here with the historical run below as if load were equal.
These results concern runtime, not statistically better solution quality.

## Original reference benchmark (historical, before packed kernels)

`numpy_baseline.py` builds each normalized CDF **once per generation**, draws
uniforms in the original ant-major order, and vectorizes roulette selection.
Fitness calculation, deposit order, evaporation and budget rounding stay the
same. This removes millions of tiny NumPy calls without changing the original's
seeded scores in the tested cases.

```sh
make -C aco bench
make -C aco bench-quick

# More trials / other original settings:
python3 -m aco.benchmark --ants 10 --evaporation 0.05 --repeat 5

# If the original Python file lives elsewhere:
python3 -m aco.benchmark --original /path/to/main.py

# Optionally omit the scalar-walk original when comparing NumPy and Bend:
python3 -m aco.benchmark --skip-original
```

Default measurement: both problems, **10,000 evaluations**, **50 ants**,
**evaporation 0.30**, **seeds 0, 1, 2**. One short unmeasured warm-up per engine;
rotate engine order between seeds. Native parallel uses 8 workers and native
sequential uses 1. Python imports are outside the function timer. Bend also
reports full subprocess wall times, and every returned best assignment has its
fitness independently recomputed. Seeds vary, so these are medians across
search runs, not repeated timing of one fixed trajectory.

Measured medians on this machine:

| Engine | Instance 1 | Instance 2 |
| --- | ---: | ---: |
| Original Python/NumPy | 13.294 s | 9.421 s |
| Vectorized NumPy | **0.160 s** | **0.179 s** |
| Bend sequential | 0.807 s | 0.938 s |
| Bend parallel, 8 workers | 0.597 s | 0.763 s |

**Historical takeaway:** the first generic Bend port was about **22× / 12×
faster than the original**, but optimized NumPy was still about **3.7× / 4.3×
faster than that generic parallel Bend engine**. The packed engine above supersedes
this result.
Bend's measured multicore gain is only about 1.35× / 1.23× here—not the near-linear
scaling seen in the Mandelbrot experiment. These are local performance results,
not evidence that any implementation finds statistically better solutions.

Raw timings, outcomes, NumPy version, platform information and original-source
SHA-256 are in **`aco/results/benchmark.json`**. The artifact records distinct RNGs
and timing scopes; it intentionally does not demand equality across NumPy/Bend.
The historical original-source SHA refers to the pre-packaging source, before
its input-validation and lint-only cleanup in the bundled baseline.

## Reproduction and next steps

`make -C aco regenerate` rebuilds generated sources; `make -C aco check` fails if
`packed.bend` does not match its generator. Commit the generator and generated
Bend together. The legacy implementation remains the parity oracle.

Next steps are dedicated idle-machine measurements, larger instance/bin-count
specializations, and throughput comparisons across many independent trials.
A GPU port is a separate experiment; 10–50 ants are small GPU batches, and
irregular traversal does not automatically favour a GPU.

Start in **`core.bend`** for the reference algorithm, **`fast.bend`** and
**`generate_packed.py`** for the fast engine, **`main.bend`** for the CLI,
**`numpy_baseline.py`** for the Python optimization, and
**`benchmark_packed.py`** for the current measurement protocol.
