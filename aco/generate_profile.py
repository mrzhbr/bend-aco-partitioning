"""Generate stage-timed wrappers for the two packed kernels (diagnostic only)."""

from pathlib import Path


def main():
    pieces = [
        "import Base\nimport ./core.bend as A\nimport ./fast.bend as F\nimport ./packed.bend as P\n"
    ]
    for n, items in ((12, 600), (40, 400)):
        blocks = (items + 15) // 16
        pieces.append(f"""
def loop{n}(left: Nat, +generation: U32, +table: List<&2, P.Block{n}>, +winner: F.Ant,
  walk_ms: Nat, prepare_ms: Nat, update_ms: Nat) -> IO(Unit):
  match left:
    case 0n:
      IO.print("{{\\\"bins\\\":{n},\\\"walk_ms\\\":" ++ Nat.show(walk_ms) ++
        ",\\\"prepare_ms\\\":" ++ Nat.show(prepare_ms) ++ ",\\\"update_ms\\\":" ++ Nat.show(update_ms) ++
        ",\\\"best_quarters\\\":" ++ U32.show(F.fitness(winner)) ++ "}}")
    case 1n+rest:
      do IO<Unit>:
        +start : Nat <- IO.now()
        +paths : List<&2, F.Ant> = P.population{n}(3n, 0, 50, table, 0, generation)
        +after_walk : Nat <- IO.now()
        +best : F.Ant = F.best(paths, F.Ant{{[], 4294967295}})
        trails : List<&2, F.Trail> = F.trails(paths)
        +after_prepare : Nat <- IO.now()
        updated : List<&2, P.Block{n}> = P.updates{n}(3n, {blocks}, table, trails, 0.7)
        end : Nat <- IO.now()
        loop{n}(rest, (generation + 1 : U32), updated, F.better(winner, best),
          Nat.add(walk_ms, Nat.sub(after_walk, start)),
          Nat.add(prepare_ms, Nat.sub(after_prepare, after_walk)),
          Nat.add(update_ms, Nat.sub(end, after_prepare)))
""")
    pieces.append("""
def main() -> IO(Unit):
  do IO<Unit>:
    loop12(200n, 0, P.table12(38n, 0, 1, 600, 0), F.Ant{[], 4294967295}, 0n, 0n, 0n)
    loop40(200n, 0, P.table40(25n, 0, 2, 400, 0), F.Ant{[], 4294967295}, 0n, 0n, 0n)
""")
    Path(__file__).with_name("profile_packed.bend").write_text("\n".join(pieces))


if __name__ == "__main__":
    main()
