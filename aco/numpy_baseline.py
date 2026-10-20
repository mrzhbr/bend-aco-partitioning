"""Algorithm-preserving NumPy optimization of the user's scalar-walk baseline.

Build each row's normalized CDF once per generation, draw uniforms in the SAME
ant-major order as the original, and vectorize roulette selection. Keep fitness,
deposit order, evaporation order, and full-population budget rounding unchanged.
Uses the existing NumPy installation; no new dependencies are installed.
"""


def aco(weights, bins, ants, evaporation, max_evals, seed):
    import numpy as np

    if max_evals < 1 or ants < 1:
        raise ValueError("evaluations and ants must be positive")
    scores = []
    gen = np.random.default_rng(seed)
    table = gen.random((len(weights), bins))
    items = np.arange(len(weights))
    best_ever = np.inf
    evaluations = 0
    while evaluations < max_evals:
        cdf = np.cumsum(table / table.sum(axis=1, keepdims=True), axis=1)
        draws = gen.random((ants, len(weights)))
        paths = np.minimum(
            np.count_nonzero(draws[:, :, None] >= cdf[None, :, :], axis=2), bins - 1
        )
        scores = []
        for path in paths:
            loads = np.bincount(path, weights=weights, minlength=bins)
            scores.append(loads.max() - loads.min())
        for path, score in zip(paths, scores, strict=True):
            table[items, path] += 100 / (score + 1)
        table *= 1 - evaporation
        evaluations += ants
        best_ever = min(best_ever, min(scores))
    return min(scores), best_ever
