import Base
import ./core.bend as A
import ./fast.bend as F
import ./packed.bend as P


def loop12(left: Nat, +generation: U32, +table: List<&2, P.Block12>, +winner: F.Ant,
  walk_ms: Nat, prepare_ms: Nat, update_ms: Nat) -> IO(Unit):
  match left:
    case 0n:
      IO.print("{\"bins\":12,\"walk_ms\":" ++ Nat.show(walk_ms) ++
        ",\"prepare_ms\":" ++ Nat.show(prepare_ms) ++ ",\"update_ms\":" ++ Nat.show(update_ms) ++
        ",\"best_quarters\":" ++ U32.show(F.fitness(winner)) ++ "}")
    case 1n+rest:
      do IO<Unit>:
        +start : Nat <- IO.now()
        +paths : List<&2, F.Ant> = P.population12(3n, 0, 50, table, 0, generation)
        +after_walk : Nat <- IO.now()
        +best : F.Ant = F.best(paths, F.Ant{[], 4294967295})
        trails : List<&2, F.Trail> = F.trails(paths)
        +after_prepare : Nat <- IO.now()
        updated : List<&2, P.Block12> = P.updates12(3n, 38, table, trails, 0.7)
        end : Nat <- IO.now()
        loop12(rest, (generation + 1 : U32), updated, F.better(winner, best),
          Nat.add(walk_ms, Nat.sub(after_walk, start)),
          Nat.add(prepare_ms, Nat.sub(after_prepare, after_walk)),
          Nat.add(update_ms, Nat.sub(end, after_prepare)))


def loop40(left: Nat, +generation: U32, +table: List<&2, P.Block40>, +winner: F.Ant,
  walk_ms: Nat, prepare_ms: Nat, update_ms: Nat) -> IO(Unit):
  match left:
    case 0n:
      IO.print("{\"bins\":40,\"walk_ms\":" ++ Nat.show(walk_ms) ++
        ",\"prepare_ms\":" ++ Nat.show(prepare_ms) ++ ",\"update_ms\":" ++ Nat.show(update_ms) ++
        ",\"best_quarters\":" ++ U32.show(F.fitness(winner)) ++ "}")
    case 1n+rest:
      do IO<Unit>:
        +start : Nat <- IO.now()
        +paths : List<&2, F.Ant> = P.population40(3n, 0, 50, table, 0, generation)
        +after_walk : Nat <- IO.now()
        +best : F.Ant = F.best(paths, F.Ant{[], 4294967295})
        trails : List<&2, F.Trail> = F.trails(paths)
        +after_prepare : Nat <- IO.now()
        updated : List<&2, P.Block40> = P.updates40(3n, 25, table, trails, 0.7)
        end : Nat <- IO.now()
        loop40(rest, (generation + 1 : U32), updated, F.better(winner, best),
          Nat.add(walk_ms, Nat.sub(after_walk, start)),
          Nat.add(prepare_ms, Nat.sub(after_prepare, after_walk)),
          Nat.add(update_ms, Nat.sub(end, after_prepare)))


def main() -> IO(Unit):
  do IO<Unit>:
    loop12(200n, 0, P.table12(38n, 0, 1, 600, 0), F.Ant{[], 4294967295}, 0n, 0n, 0n)
    loop40(200n, 0, P.table40(25n, 0, 2, 400, 0), F.Ant{[], 4294967295}, 0n, 0n, 0n)
