import Base
import ./core.bend as A

type Times is Data:
  Times{walk: Nat, best: Nat, reward: Nat, evaporate: Nat}

def loop(left: Nat, +problem: U32, +bins: U32, +depth: Nat, +generation: U32,
  +table: List<&2, A.Row>, +winner: A.Ant, final: U32,
  walk_time: Nat, best_time: Nat, reward_time: Nat, evaporate_time: Nat) -> IO(A.Outcome & Times):
  match left:
    case 0n:
      IO.pure(A.Outcome & Times, (A.Outcome{final, winner, (generation * 50 : U32)},
        Times{walk_time, best_time, reward_time, evaporate_time}))
    case 1n+rest:
      do IO<A.Outcome & Times>:
        +start : Nat <- IO.now()
        +paths : List<&2, A.Ant> = A.population(3n, 0, 50, table, problem, bins, depth, 0, generation)
        +after_walk : Nat <- IO.now()
        +best : A.Ant = A.best(paths, A.Ant{[], 4294967295})
        +after_best : Nat <- IO.now()
        updated : List<&2, A.Row> = A.reward(paths, table)
        +after_reward : Nat <- IO.now()
        evaporated : List<&2, A.Row> = A.evaporate(updated, 0.7)
        end : Nat <- IO.now()
        loop(rest, problem, bins, depth, (generation + 1 : U32), evaporated,
          A.better(winner, best), A.fitness(best),
          Nat.add(walk_time, Nat.sub(after_walk, start)),
          Nat.add(best_time, Nat.sub(after_best, after_walk)),
          Nat.add(reward_time, Nat.sub(after_reward, after_best)),
          Nat.add(evaporate_time, Nat.sub(end, after_reward)))

def show(problem: U32, pair: A.Outcome & Times) -> IO(Unit):
  match pair:
    case (A.Outcome{final, A.Ant{path, best}, evaluations}, Times{walk, selection, reward, evaporate}):
      IO.print("{\"problem\":" ++ U32.show(problem) ++ ",\"walk_ms\":" ++ Nat.show(walk) ++
        ",\"best_ms\":" ++ Nat.show(selection) ++ ",\"reward_ms\":" ++ Nat.show(reward) ++
        ",\"evaporate_ms\":" ++ Nat.show(evaporate) ++ ",\"best_quarters\":" ++ U32.show(best) ++ "}")

def profile(+problem: U32, items: U32, +bins: U32) -> IO(Unit):
  +depth = {1n+U32.log2((bins - 1 : U32)) : Nat}
  IO.bind(A.Outcome & Times, Unit,
    loop(200n, problem, bins, depth, 0, A.table_new(U32.to_nat(items), 0, bins, depth, 0),
      A.Ant{[], 4294967295}, 4294967295, 0n, 0n, 0n, 0n), show(problem))

def main() -> IO(Unit):
  do IO<Unit>:
    profile(1, 600, 12)
    profile(2, 400, 40)
