# ACO for Multi-Way Number Partitioning in Bend 2

An exploratory performance experiment: port an Ant Colony Optimization (ACO)
solver from Python/NumPy to Bend 2, then optimize its execution and data layout.

## Problem

Partition positive numbers into a **fixed number of groups**, balancing their
loads. The implemented objective is:

```text
minimize max(group loads) - min(group loads)
```

This is **multi-way number partitioning with a load-range objective**, not
capacity-constrained bin packing. It minimizes the gap between the heaviest and
lightest groups, rather than the conventional makespan objective `min(max(load))`.

| Instance | Numbers | Groups | Weight of number i (starting at 1) |
| --- | ---: | ---: | --- |
| 1 | 600 | 12 | `2*i + 1` |
| 2 | 400 | 40 | `i*i / 4` |

Ants assign numbers using pheromone-weighted roulette selection. After evaluating
a whole population, each path receives `100 / (fitness + 1)` pheromone, followed
by evaporation. No local search or additional balancing heuristic is used.

## Implementations and comparison

Includes the original scalar-walk NumPy baseline, vectorized NumPy, reference
Bend, and packed Bend kernels specialized for 12/40 groups. The packed version
reduces allocations, caches sampling sums, and parallelizes independent updates.

Local measurements across eight configurations and five seeds favored packed
Bend by approximately **2–3× in solver time**. This is **not a controlled language
benchmark**: Bend uses Float32 and xorshift32 streams; NumPy uses Float64 and
PCG64. Initial states and trajectories differ. Native core usage and specialization
also differ, and other experiments were active on the machine. Exact-output
parity is tested between the Bend engines—not between Bend and NumPy.

## Run

Requires macOS/Linux, clang 14+, and Python 3.10+ with NumPy (measurements used
NumPy 2.5.3). Setup downloads checksum-verified Bend **2.0.37** locally.

```sh
make setup
make test
make bench

# instance ants evaporation evaluations seed mode
./aco/build/aco --threads 4 1 50 0.30 10000 0 packed-parallel
```

See [experiment notes](docs/EXPERIMENT.md) for methodology, limitations, profiling
and tests, and [raw results](aco/results/) for timings, outcomes and fingerprints.
