"""Original scalar-walk NumPy ACO baseline.

Only input validation and lint/format cleanup were added for packaging;
the algorithm and valid-input random-number consumption are unchanged.
"""

import numpy as np


# problem 1
def bpp1():
    weights = np.arange(1, 601)
    weights = 2 * weights + 1

    return weights, 12


# problem 2
def bpp2():
    weights = np.arange(1, 401)
    weights = pow(weights, 2) / 4

    return weights, 40


# create the table that holds the construction graph
def create_table(gen, k, b):
    graph = gen.random((k, b))
    return graph


def fitness(path, weights, b):
    d = np.bincount(path, weights=weights, minlength=b)
    return d.max() - d.min()


# let the ant select a bin via roulette wheel selection
def choose_bin(gen, pheromones):
    prob = pheromones / pheromones.sum()
    intervals = np.cumsum(prob)
    num = gen.random()
    chosen = np.searchsorted(intervals, num, side="right")
    return min(chosen, len(pheromones) - 1)


# let the ant walk the actual path
def walk_path(gen, table):
    path = np.empty(len(table), dtype=int)
    for item in range(len(table)):
        path[item] = choose_bin(gen, table[item])
    return path


def update_pheromone(table, path, d):
    items = np.arange(len(path))
    table[items, path] += 100 / (d + 1)


def evaporate(table, e):
    table *= 1 - e


def aco(weights, b, p, e, max_evals, seed):
    if p < 1 or max_evals < 1:
        raise ValueError("population and evaluation budget must be positive")
    ds = []
    gen = np.random.default_rng(seed)
    table = create_table(gen, len(weights), b)
    evals = 0
    best_ever = np.inf

    while evals < max_evals:
        paths = [walk_path(gen, table) for _ in range(p)]
        ds = [fitness(path, weights, b) for path in paths]
        evals += p

        for path, d in zip(paths, ds, strict=True):
            update_pheromone(table, path, d)
        evaporate(table, e)

        best_ever = min(best_ever, min(ds))

    return min(ds), best_ever


if __name__ == "__main__":
    max_evals = 10_000
    trials = 5
    settings = [(50, 0.05), (50, 0.30), (10, 0.05), (10, 0.30)]

    for name, problem in [("BPP1", bpp1), ("BPP2", bpp2)]:
        weights, b = problem()
        for p, e in settings:
            for trial in range(trials):
                final_best, best_ever = aco(weights, b, p, e, max_evals, seed=trial)
                print(
                    f"{name} p={p} e={e} trial={trial + 1}: "
                    f"final population best d={final_best}, best ever d={best_ever}"
                )
