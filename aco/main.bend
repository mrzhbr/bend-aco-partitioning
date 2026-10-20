import Base
import ./core.bend as A
import ./packed.bend as P

type Mode is Data:
  Mode{parallel: Bool, packed: Bool}

def usage() -> String:
  "Usage: aco problem ants evaporation evaluations seed sequential|parallel|packed-sequential|packed-parallel [items bins]\nProblems: 1 (600 items, 12 bins), 2 (400 items, 40 bins).\nExample: ./build/aco --threads 8 1 50 0.30 10000 0 parallel\nOptional smaller item/bin counts are for validation; all weights retain the original formulas."

def require(ok: Bool, message: String) -> IO(Unit):
  match ok:
    case True{}:
      IO.pure(Unit, Unit{})
    case False{}:
      IO.die(Unit, 2, message)

def integer_result(value: Maybe<&2, U32>, label: String, +low: U32, +high: U32) -> IO(U32):
  match value:
    case None{}:
      IO.die(U32, 2, "Invalid integer: " ++ label)
    case Some{+n}:
      do IO<U32>:
        require((n >= low : U32) && (n <= high : U32), "Out of range: " ++ label)
        return n

def integer(text: String, label: String, low: U32, high: U32) -> IO(U32):
  integer_result(U32.read(text), label, low, high)

def rate_result(value: Maybe<&2, F32>) -> IO(F32):
  match value:
    case None{}:
      IO.die(F32, 2, "Invalid evaporation rate")
    case Some{+n}:
      do IO<F32>:
        require((n >= 0.0 : F32) && (n < 1.0 : F32), "Evaporation must be finite and in [0,1)")
        return n

def mode_result(sequential: Bool, parallel: Bool, packed_sequential: Bool, packed_parallel: Bool) -> IO(Mode):
  match sequential parallel packed_sequential packed_parallel:
    case True{} _ _ _:
      IO.pure(Mode, Mode{False{}, False{}})
    case _ True{} _ _:
      IO.pure(Mode, Mode{True{}, False{}})
    case _ _ True{} _:
      IO.pure(Mode, Mode{False{}, True{}})
    case _ _ _ True{}:
      IO.pure(Mode, Mode{True{}, True{}})
    case _ _ _ _:
      IO.die(Mode, 2, "Unknown solver mode")

def mode(+text: String) -> IO(Mode):
  mode_result(String.eq(text, "sequential"), String.eq(text, "parallel"),
    String.eq(text, "packed-sequential"), String.eq(text, "packed-parallel"))

def forks(parallel: Bool) -> Nat:
  match parallel:
    case True{}:
      3n
    case False{}:
      0n

def mode_name(mode: Mode) -> String:
  match mode:
    case Mode{False{}, False{}}:
      "sequential"
    case Mode{True{}, False{}}:
      "parallel"
    case Mode{False{}, True{}}:
      "packed-sequential"
    case Mode{True{}, True{}}:
      "packed-parallel"

# Arbitrary validation bin counts retain the generic engine, not a different ACO.
def packed(problem: U32, items: U32, bins: U32, ants: U32,
  evaporation: F32, budget: U32, seed: U32, forks: Nat) -> A.Outcome:
  match bins:
    case 12:
      P.run12(problem, items, ants, evaporation, budget, seed, forks)
    case 40:
      P.run40(problem, items, ants, evaporation, budget, seed, forks)
    case _:
      A.run(problem, items, bins, ants, evaporation, budget, seed, forks)

def solve(mode: Mode, problem: U32, items: U32, bins: U32, ants: U32,
  evaporation: F32, budget: U32, seed: U32) -> A.Outcome:
  match mode:
    case Mode{parallel, False{}}:
      A.run(problem, items, bins, ants, evaporation, budget, seed, forks(parallel))
    case Mode{parallel, True{}}:
      packed(problem, items, bins, ants, evaporation, budget, seed, forks(parallel))

# Keep quarter-unit fitness formatting exact even above F32's integer precision.
def show_fitness(+quarters: U32) -> String:
  +fraction = (quarters % 4 : U32)
  U32.show((quarters / 4 : U32)) ++ "." ++
    Bool.pick(String, U32.is_eq(fraction, 0), "00",
      Bool.pick(String, U32.is_eq(fraction, 1), "25",
        Bool.pick(String, U32.is_eq(fraction, 2), "50", "75")))

def path_strings(path: List<&2, U32>) -> List<&2, String>:
  match path:
    case Nil{}:
      []
    case Con{bin, rest}:
      U32.show(bin) <> path_strings(rest)

def report(result: A.Outcome, +problem: U32, +items: U32, +bins: U32,
  ants: U32, evaporation: F32, budget: U32, seed: U32, mode: Mode, elapsed: Nat) -> String:
  match result:
    case A.Outcome{+final, A.Ant{path, +best}, evaluations}:
      "{\"problem\":" ++ U32.show(problem) ++ ",\"items\":" ++ U32.show(items) ++
        ",\"bins\":" ++ U32.show(bins) ++ ",\"ants\":" ++ U32.show(ants) ++
        ",\"evaporation\":" ++ F32.show(evaporation) ++ ",\"budget\":" ++ U32.show(budget) ++
        ",\"evaluations\":" ++ U32.show(evaluations) ++ ",\"seed\":" ++ U32.show(seed) ++
        ",\"mode\":\"" ++ mode_name(mode) ++ "\",\"elapsed_ms\":" ++ Nat.show(elapsed) ++
        ",\"final_quarters\":" ++ U32.show(final) ++ ",\"best_quarters\":" ++ U32.show(best) ++
        ",\"final\":" ++ show_fitness(final) ++ ",\"best\":" ++ show_fitness(best) ++
        ",\"best_path\":[" ++ String.join(path_strings(path), ",") ++ "]}"

def run(+problem: U32, +items: U32, +bins: U32, +ants: U32, +evaporation: F32,
  +budget: U32, +seed: U32, +mode: Mode) -> IO(Unit):
  do IO<Unit>:
    start : Nat <- IO.now()
    result : A.Outcome = solve(mode, problem, items, bins, ants, evaporation, budget, seed)
    end : Nat <- IO.now()
    IO.print(report(result, problem, items, bins, ants, evaporation, budget, seed, mode, Nat.sub(end, start)))

def sizes(args: List<String>, +problem: U32) -> IO(U32 & U32):
  match args:
    case Nil{}:
      IO.pure(U32 & U32, (Bool.pick(U32, U32.is_eq(problem, 1), 600, 400),
        Bool.pick(U32, U32.is_eq(problem, 1), 12, 40)))
    case Con{items, Con{bins, Nil{}}}:
      do IO<U32 & U32>:
        items : U32 <- integer(items, "items", 1, 600)
        bins : U32 <- integer(bins, "bins", 1, 64)
        return (items, bins)
    case _:
      IO.die(U32 & U32, 2, usage())

def configured(pair: U32 & U32, problem: U32, ants: U32, evaporation: F32,
  budget: U32, seed: U32, mode: Mode) -> IO(Unit):
  (items, bins) = pair
  run(problem, items, bins, ants, evaporation, budget, seed, mode)

def arguments(args: List<String>) -> IO(Unit):
  match args:
    case Con{p, Con{a, Con{e, Con{n, Con{s, Con{m, rest}}}}}}:
      do IO<Unit>:
        +problem : U32 <- integer(p, "problem", 1, 2)
        ants : U32 <- integer(a, "ants", 1, 512)
        evaporation : F32 <- rate_result(F32.read(e))
        budget : U32 <- integer(n, "evaluations", 1, 1000000)
        seed : U32 <- integer(s, "seed", 0, 4294967295)
        mode : Mode <- mode(m)
        pair : U32 & U32 <- sizes(rest, problem)
        configured(pair, problem, ants, evaporation, budget, seed, mode)
    case _:
      IO.die(Unit, 2, usage())

def command_line(args: List<String>) -> IO(Unit):
  match args:
    case Con{program, rest}:
      arguments(rest)
    case Nil{}:
      IO.die(Unit, 2, usage())

def main() -> IO(Unit):
  IO.bind(List<String>, Unit, IO.args(), command_line)
