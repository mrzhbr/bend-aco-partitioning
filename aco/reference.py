"""Slow, independent executable specification for the Bend F32/tree/RNG variant.

This is NOT the NumPy baseline: it exists to test every stochastic decision.
All arithmetic affecting probabilities is explicitly rounded to IEEE float32.
"""

import struct
from dataclasses import dataclass

MASK = 0xFFFFFFFF


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def mix(value):
    a = ((value ^ (value >> 16)) * 2146121005) & MASK
    b = ((a ^ (a >> 15)) * 2221713035) & MASK
    return b ^ (b >> 16)


def next_state(state):
    state ^= (state << 13) & MASK
    state ^= state >> 17
    return (state ^ ((state << 5) & MASK)) & MASK


def uniform(state):
    return f32((state >> 8) / 16777216.0)


def ant_seed(seed, generation, index):
    return (
        mix(
            seed
            ^ ((generation * 2654435769) & MASK)
            ^ (((index + 1) * 2246822519) & MASK)
        )
        | 1
    )


def weights(problem, items):
    return [4 * (2 * i + 1) if problem == 1 else i * i for i in range(1, items + 1)]


@dataclass
class Row:
    mass: float
    index: int = 0
    cut: int = 0
    left: "Row | None" = None
    right: "Row | None" = None


def row_new(depth, start, bins, seed, item):
    if depth == 0:
        value = uniform(mix(seed ^ (((item + 1) * 3266489917) & MASK) ^ start))
        return Row(value if start < bins else 0.0, index=start)
    middle = start + (1 << (depth - 1))
    left = row_new(depth - 1, start, bins, seed, item)
    right = row_new(depth - 1, middle, bins, seed, item)
    return Row(f32(left.mass + right.mass), cut=middle, left=left, right=right)


def choose(row, u, bins):
    threshold = f32(u * row.mass)
    while row.left is not None:
        assert row.right is not None
        if threshold < row.left.mass:
            row = row.left
        else:
            threshold = f32(threshold - row.left.mass)
            row = row.right
    return min(row.index, bins - 1)


def deposit(row, bin_index, amount):
    if row.left is None:
        row.mass = f32(row.mass + amount)
        return
    assert row.right is not None
    deposit(row.left if bin_index < row.cut else row.right, bin_index, amount)
    row.mass = f32(row.left.mass + row.right.mass)


def evaporate(row, factor):
    if row.left is None:
        row.mass = f32(row.mass * factor)
        return
    assert row.right is not None
    evaporate(row.left, factor)
    evaporate(row.right, factor)
    row.mass = f32(row.left.mass + row.right.mass)


def run(problem, items, bins, ants, evaporation, budget, seed):
    depth = max(1, (bins - 1).bit_length())
    table = [row_new(depth, 0, bins, seed, item) for item in range(items)]
    item_weights = weights(problem, items)
    factor = f32(1.0 - f32(evaporation))
    best_value = MASK
    best_path = []
    generations = (budget + ants - 1) // ants
    final_value = MASK
    for generation in range(generations):
        population = []
        for ant in range(ants):
            state = ant_seed(seed, generation, ant)
            path = []
            loads = [0] * bins
            for row, weight in zip(table, item_weights, strict=True):
                state = next_state(state)
                bin_index = choose(row, uniform(state), bins)
                path.append(bin_index)
                loads[bin_index] += weight
            value = max(loads) - min(loads)
            population.append((value, path))
        final_value, winner = min(population, key=lambda entry: entry[0])
        if final_value < best_value:
            best_value, best_path = final_value, winner
        for value, path in population:
            amount = f32(100.0 / f32(f32(f32(value) / 4.0) + 1.0))
            for row, bin_index in zip(table, path, strict=True):
                deposit(row, bin_index, amount)
        for row in table:
            evaporate(row, factor)
    return {
        "final_quarters": final_value,
        "best_quarters": best_value,
        "best_path": best_path,
        "evaluations": generations * ants,
    }
