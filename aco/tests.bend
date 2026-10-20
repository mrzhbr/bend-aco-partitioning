import Base
import ./core.bend as A

def check(ok: Bool, label: String) -> IO(Unit):
  match ok:
    case True{}:
      IO.pure(Unit, Unit{})
    case False{}:
      IO.die(Unit, 1, "FAIL: " ++ label)

def two_bins() -> A.Row:
  A.node(1, A.Bin{0, 0.5}, A.Bin{1, 0.5})

def sum_weights(left: Nat, +problem: U32, +i: U32, acc: U32) -> U32:
  match left:
    case 0n:
      acc
    case 1n+rest:
      sum_weights(rest, problem, (i + 1 : U32), (acc + A.weight(problem, i) : U32))

def main() -> IO(Unit):
  do IO<Unit>:
    check(U32.is_eq(A.weight(1, 1), 12), "BPP1 first quarter-weight")
    check(U32.is_eq(A.weight(1, 600), 4804), "BPP1 last quarter-weight")
    check(U32.is_eq(A.weight(2, 1), 1), "BPP2 first quarter-weight")
    check(U32.is_eq(A.weight(2, 400), 160000), "BPP2 last quarter-weight")
    check(U32.is_eq(sum_weights(600n, 1, 1, 0), 1444800), "BPP1 total")
    check(U32.is_eq(sum_weights(400n, 2, 1, 0), 21413400), "BPP2 total fits U32")
    check(U32.is_eq(A.choose(two_bins(), 0.0, 2), 0), "roulette lower endpoint")
    check(U32.is_eq(A.choose(two_bins(), 0.5, 2), 1), "roulette right-side tie")
    check(U32.is_eq(A.choose(two_bins(), 1.0, 2), 1), "roulette upper clamp")
    check(U32.is_eq(A.choose(A.node(1, A.Bin{0, 0.0}, A.Bin{1, 1.0}), 0.0, 2), 1), "zero-mass branch skipped")
    check(U32.is_eq(A.choose(A.node(1, A.Bin{0, 1.0}, A.Bin{1, 0.0}), 0.75, 1), 0), "padded bin never selected")
    check(F32.is_eq(A.mass(A.deposit(two_bins(), 0, 0.5)), 1.5), "deposit magnitude")
    check(U32.is_eq(A.choose(A.deposit(two_bins(), 0, 0.5), 0.6, 2), 0), "deposit affects selection")
    check(F32.is_eq(A.mass(A.evaporate_row(two_bins(), 0.5)), 0.5), "evaporation magnitude")
    check(U32.is_eq(A.spread(3n, [7, 5, 10, 0], 4294967295, 0), 5), "padded load slots ignored")
    check(U32.is_eq(A.spread(3n, [7, 0, 10, 0], 4294967295, 0), 10), "real empty bins included")
    check(U32.is_ne(A.ant_seed(0, 0, 0), 0), "nonzero xorshift stream")
    check(F32.is_eq(A.reward_amount(0), 100.0), "perfect balance reward")
    check(F32.is_eq(A.reward_amount(4), 50.0), "one unit fitness reward")
    check(F32.is_eq(A.reward_amount(1), 80.0), "quarter-unit fitness reward")
    IO.print("20 ACO numerical tests passed")
