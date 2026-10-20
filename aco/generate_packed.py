"""Generate auditable pure-Bend kernels; no foreign compute or compiler patches.

Specialize the two standard bin counts, pack sixteen item choices per cell,
retain each leaf's ant-order F32 additions, and cache pairwise sums once/row.
Run from any directory: python3 aco/generate_packed.py
"""

from pathlib import Path

BLOCK = 16


def tree(start, size, bins):
    if start >= bins:
        return None
    if size == 1:
        return (start, size, None, None)
    left = tree(start, size // 2, bins)
    right = tree(start + size // 2, size // 2, bins)
    return (start, size, left, right) if right is not None else left


def ref(node):
    return f"m{node[0]}" if node[2] is None else f"s{node[0]}_{node[1]}"


def nodes(node):
    if node[2] is None:
        return []
    return nodes(node[2]) + nodes(node[3]) + [node]


def full_required(start, size, bins):
    if size == 1:
        return []
    left = tree(start, size // 2, bins)
    return [
        ref(left) if left is not None else "0.0",
        *full_required(start, size // 2, bins),
        *full_required(start + size // 2, size // 2, bins),
    ]


def generate_seek(size):
    fields = [f"h{i}" for i in range(size - 1)]
    out = [
        signature(
            f"seek{size}", ["+u: F32", *[f"+{field}: F32" for field in fields]], "U32"
        )
    ]
    if size == 2:
        out.append("  F.word((u < h0 : F32), 0, 1)")
    else:
        half = size // 2
        out.extend(
            ["  +right = (u >= h0 : F32)", "  t = F.number(right, (u - h0 : F32), u)"]
        )
        for i in range(half - 1):
            out.append(f"  s{i} = F.number(right, h{half + i}, h{1 + i})")
        out.append(
            f"  (F.word(right, {half}, 0) + seek{half}(t, "
            + ", ".join(f"s{i}" for i in range(half - 1))
            + ") : U32)"
        )
    return "\n".join(out)


def signature(name, params, result):
    return (
        f"def {name}("
        + ",\n  ".join(", ".join(params[i : i + 6]) for i in range(0, len(params), 6))
        + f") -> {result}:"
    )


def generate(bins):
    n = bins
    capacity = 1 << (n - 1).bit_length()
    root = tree(0, capacity, n)
    inner = nodes(root)
    selections = full_required(0, capacity, n)
    cached = list(
        dict.fromkeys(
            [value for value in selections if value.startswith("s")] + [ref(root)]
        )
    )
    masses = [f"m{i}" for i in range(n)]
    fields = ["weight", *masses, *cached]
    row_type = f"Row{n}"
    block_type = f"Block{n}"
    out = [
        f"\n# ---- {n} bins: packed scalar rows, sixteen-item path blocks ----",
        f"type {row_type} is Data:",
        f"  R{n}{{weight: U32, "
        + ", ".join(f"{field}: F32" for field in fields[1:])
        + "}",
        f"type {block_type} is Data:",
        f"  B{n}{{" + ", ".join(f"r{i}: {row_type}" for i in range(BLOCK)) + "}",
    ]

    def emit(text=""):
        out.append(text)

    emit(
        signature(
            f"make{n}", ["weight: U32", *[f"+{m}: F32" for m in masses]], row_type
        )
    )
    for node in inner:
        emit(f"  +{ref(node)} = ({ref(node[2])} + {ref(node[3])} : F32)")
    emit(f"  R{n}{{" + ", ".join(fields) + "}")
    emit(signature(f"weight{n}", [f"row: {row_type}"], "U32"))
    emit(f"  match row:\n    case R{n}{{" + ", ".join(fields) + "}:\n      weight")
    emit(
        signature(
            f"new{n}",
            ["+problem: U32", "+item: U32", "+items: U32", "+seed: U32"],
            row_type,
        )
    )
    emit(
        "  weight = F.word((item < items : U32), A.weight(problem, (item + 1 : U32)), 0)"
    )
    emit(
        f"  make{n}(weight, "
        + ", ".join(
            f"A.uniform(A.mix(U32.xor(seed, U32.xor(U32.mul((item + 1 : U32), 3266489917), {i}))))"
            for i in range(n)
        )
        + ")"
    )
    emit(
        signature(
            f"table{n}",
            ["left: Nat", "+block: U32", "+problem: U32", "+items: U32", "+seed: U32"],
            f"List<&2, {block_type}>",
        )
    )
    emit("  match left:\n    case 0n:\n      []\n    case 1n+rest:")
    emit(
        f"      B{n}{{"
        + ", ".join(
            f"new{n}(problem, (block * 16 + {i} : U32), items, seed)"
            for i in range(BLOCK)
        )
        + "} <>"
    )
    emit(f"        table{n}(rest, (block + 1 : U32), problem, items, seed)")

    emit(signature(f"choose{n}", [f"row: {row_type}", "u: F32"], "U32"))
    emit(
        f"  match row:\n    case R{n}{{"
        + ", ".join("+" + field for field in fields)
        + "}:"
    )
    emit(
        f"      F.min(seek{capacity}((u * {ref(root)} : F32), "
        + ", ".join(selections)
        + f"), {n - 1})"
    )

    emit(
        signature(
            f"walk{n}",
            [
                f"table: List<&2, {block_type}>",
                "+bins: U32",
                "seed: U32",
                "loads: Array<U32>",
                "path: List<&2, F.Choices>",
            ],
            "F.Ant",
        )
    )
    emit(
        "  match table:\n    case Nil{}:\n      F.finish(U32.to_nat(bins), 1, Array.get(U32, loads, 0), 4294967295, 0, path)"
    )
    emit(
        f"    case Con{{B{n}{{"
        + ", ".join(f"+r{i}" for i in range(BLOCK))
        + "}, rest}:"
    )
    for i in range(BLOCK):
        prior_seed = "seed" if i == 0 else f"s{i - 1}"
        prior_loads = "loads" if i == 0 else f"a{i - 1}"
        emit(f"      +s{i} = A.next({prior_seed})")
        emit(f"      +b{i} = choose{n}(r{i}, A.uniform(s{i}))")
        emit(
            f"      a{i} = A.bump(Array.get(U32, {prior_loads}, b{i}), b{i}, weight{n}(r{i}))"
        )
    emit(
        f"      walk{n}(rest, bins, s15, a15, F.Choices{{"
        + ", ".join(f"b{i}" for i in range(BLOCK))
        + "} <> path)"
    )

    emit(
        signature(
            f"serial{n}",
            [
                "left: Nat",
                "+first: U32",
                f"+table: List<&2, {block_type}>",
                "+seed: U32",
                "+generation: U32",
            ],
            "List<&2, F.Ant>",
        )
    )
    emit("  match left:\n    case 0n:\n      []\n    case 1n+rest:")
    depth = (n - 1).bit_length()
    emit(
        f"      ant = walk{n}(table, {n}, A.ant_seed(seed, generation, first), Array.new(U32, {depth}n, 0), [])"
    )
    emit(f"      ant <> serial{n}(rest, (first + 1 : U32), table, seed, generation)")
    emit(
        signature(
            f"population{n}",
            [
                "+forks: Nat",
                "+first: U32",
                "+count: U32",
                f"+table: List<&2, {block_type}>",
                "+seed: U32",
                "+generation: U32",
            ],
            "List<&2, F.Ant>",
        )
    )
    emit("  match forks:\n    case 0n:")
    emit(f"      serial{n}(U32.to_nat(count), first, table, seed, generation)")
    emit("    case 1n+rest:\n      +half = (count / 2 : U32)")
    emit(f"      a b = population{n}(rest, first, half, table, seed, generation)")
    emit(
        f"        population{n}(rest, (first + half : U32), (count - half : U32), table, seed, generation)"
    )
    emit("      List.append(&2, F.Ant, a, b)")

    # Keep all leaf accumulators in scalar registers across the ordered ant loop.
    # Masked additions vectorize better here than temporary array/record updates.
    for slot in range(BLOCK):
        emit(
            signature(
                f"update{n}_{slot}",
                [
                    "heads: List<&2, F.Head>",
                    "+factor: F32",
                    "weight: U32",
                    *[f"+{m}: F32" for m in masses],
                ],
                row_type,
            )
        )
        emit("  match heads:\n    case Nil{}:")
        emit(
            f"      make{n}(weight, "
            + ", ".join(f"({m} * factor : F32)" for m in masses)
            + ")"
        )
        emit(
            "    case Con{F.Head{F.Choices{"
            + ", ".join(f"+b{i}" for i in range(BLOCK))
            + "}, +amount}, rest}:"
        )
        emit(
            f"      update{n}_{slot}(rest, factor, weight, "
            + ", ".join(
                f"({m} + F.number(U32.is_eq(b{slot}, {i}), amount, 0.0) : F32)"
                for i, m in enumerate(masses)
            )
            + ")"
        )
        emit(
            signature(
                f"apply{n}_{slot}",
                [f"row: {row_type}", "heads: List<&2, F.Head>", "factor: F32"],
                row_type,
            )
        )
        emit(f"  match row:\n    case R{n}{{" + ", ".join(fields) + "}:")
        emit(
            f"      update{n}_{slot}(heads, factor, weight, " + ", ".join(masses) + ")"
        )
    emit(
        signature(
            f"block_update{n}",
            [f"block: {block_type}", "+heads: List<&2, F.Head>", "+factor: F32"],
            block_type,
        )
    )
    emit(
        f"  match block:\n    case B{n}{{"
        + ", ".join(f"r{i}" for i in range(BLOCK))
        + "}:"
    )
    for i in range(BLOCK):
        emit(f"      a{i} = apply{n}_{i}(r{i}, heads, factor)")
    emit(f"      B{n}{{" + ", ".join(f"a{i}" for i in range(BLOCK)) + "}")
    emit(
        signature(
            f"apply_heads{n}",
            [
                f"block: {block_type}",
                "state: List<&2, F.Head> & List<&2, F.Trail>",
                "factor: F32",
            ],
            f"{block_type} & List<&2, F.Trail>",
        )
    )
    emit(
        f"  match state:\n    case Tuple{{heads, tails}}:\n      (block_update{n}(block, heads, factor), tails)"
    )
    emit(
        signature(
            f"step{n}",
            [f"block: {block_type}", "trails: List<&2, F.Trail>", "factor: F32"],
            f"{block_type} & List<&2, F.Trail>",
        )
    )
    emit(f"  apply_heads{n}(block, F.advance(trails, [], []), factor)")
    emit(
        signature(
            f"updates_loop{n}",
            [
                f"table: List<&2, {block_type}>",
                f"state: {block_type} & List<&2, F.Trail>",
                f"acc: List<&2, {block_type}>",
                "+factor: F32",
            ],
            f"List<&2, {block_type}>",
        )
    )
    emit(
        f"  match table state:\n    case Nil{{}} Tuple{{block, trails}}:\n      List.reverse(&2, {block_type}, block <> acc)"
    )
    emit(
        f"    case Con{{next, rest}} Tuple{{block, trails}}:\n      updates_loop{n}(rest, step{n}(next, trails, factor), block <> acc, factor)"
    )
    emit(
        signature(
            f"updates_start{n}",
            [
                f"table: List<&2, {block_type}>",
                "trails: List<&2, F.Trail>",
                "+factor: F32",
            ],
            f"List<&2, {block_type}>",
        )
    )
    emit("  match table:\n    case Nil{}:\n      []\n    case Con{block, rest}:")
    emit(f"      updates_loop{n}(rest, step{n}(block, trails, factor), [], factor)")
    emit(
        signature(
            f"updates{n}",
            [
                "+forks: Nat",
                "+count: U32",
                f"+table: List<&2, {block_type}>",
                "+trails: List<&2, F.Trail>",
                "+factor: F32",
            ],
            f"List<&2, {block_type}>",
        )
    )
    emit(f"  match forks:\n    case 0n:\n      updates_start{n}(table, trails, factor)")
    emit(
        "    case 1n+rest:\n      +half = (count / 2 : U32)\n      +cut = U32.to_nat(half)"
    )
    emit(
        f"      a b = updates{n}(rest, half, List.take(&2, {block_type}, table, cut), F.left_trails(trails, cut), factor)"
    )
    emit(
        f"        updates{n}(rest, (count - half : U32), List.drop(&2, {block_type}, table, cut), F.right_trails(trails, cut), factor)"
    )
    emit(f"      List.append(&2, {block_type}, a, b)")

    emit(
        signature(
            f"iterate{n}",
            [
                "left: Nat",
                "+items: U32",
                "+blocks: U32",
                "+ants: U32",
                "+seed: U32",
                "+generation: U32",
                "+forks: Nat",
                "+factor: F32",
                f"+table: List<&2, {block_type}>",
                "+winner: F.Ant",
                "final: U32",
            ],
            "A.Outcome",
        )
    )
    emit(
        "  match left:\n    case 0n:\n      F.outcome(winner, items, final, (generation * ants : U32))\n    case 1n+rest:"
    )
    emit(f"      +population = population{n}(forks, 0, ants, table, seed, generation)")
    emit("      +best = F.best(population, F.Ant{[], 4294967295})")
    emit(
        f"      updated = updates{n}(forks, blocks, table, F.trails(population), factor)"
    )
    emit(
        f"      iterate{n}(rest, items, blocks, ants, seed, (generation + 1 : U32), forks, factor,"
    )
    emit("        updated, F.better(winner, best), F.fitness(best))")
    emit(
        signature(
            f"run{n}",
            [
                "+problem: U32",
                "+items: U32",
                "+ants: U32",
                "evaporation: F32",
                "+budget: U32",
                "+seed: U32",
                "forks: Nat",
            ],
            "A.Outcome",
        )
    )
    emit(
        "  +blocks = ((items + 15) / 16 : U32)\n  generations = ((budget + ants - 1) / ants : U32)"
    )
    emit(
        f"  iterate{n}(U32.to_nat(generations), items, blocks, ants, seed, 0, forks, (1.0 - evaporation : F32),"
    )
    emit(
        f"    table{n}(U32.to_nat(blocks), 0, problem, items, seed), F.Ant{{[], 4294967295}}, 4294967295)"
    )
    return "\n\n".join(out)


def render():
    header = "# GENERATED by generate_packed.py. Pure Bend; edit the generator, then regenerate.\nimport Base\nimport ./core.bend as A\nimport ./fast.bend as F\n"
    selectors = "\n\n".join(generate_seek(size) for size in (2, 4, 8, 16, 32, 64))
    return header + selectors + "\n" + generate(12) + generate(40) + "\n"


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).with_name("packed.bend")
    text = render()
    if args.check:
        if not path.is_file() or path.read_text() != text:
            parser.error("packed.bend is out of date; run generate_packed.py")
    else:
        path.write_text(text)


if __name__ == "__main__":
    main()
