import Base
import ./core.bend as A
import ./fast.bend as F
import ./packed.bend as P

def check(ok: Bool, label: String) -> IO(Unit):
  match ok:
    case True{}:
      IO.pure(Unit, Unit{})
    case False{}:
      IO.die(Unit, 1, "FAIL: " ++ label)

def same12(left: Nat, +seed: U32, +generic: A.Row, +packed: P.Row12) -> Bool:
  match left:
    case 0n:
      True{}
    case 1n+rest:
      +state = A.next(seed)
      +u = A.uniform(state)
      U32.is_eq(A.choose(generic, u, 12), P.choose12(packed, u)) &&
        same12(rest, state, generic, packed)

def same40(left: Nat, +seed: U32, +generic: A.Row, +packed: P.Row40) -> Bool:
  match left:
    case 0n:
      True{}
    case 1n+rest:
      +state = A.next(seed)
      +u = A.uniform(state)
      U32.is_eq(A.choose(generic, u, 40), P.choose40(packed, u)) &&
        same40(rest, state, generic, packed)

def zero12() -> P.Row12:
  P.apply12_0(P.new12(1, 7, 600, 42), [], 0.0)

def zero40() -> P.Row40:
  P.apply40_0(P.new40(2, 7, 400, 42), [], 0.0)

def head(bin: U32) -> F.Head:
  F.Head{F.Choices{bin, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0}, 0.5}

def main() -> IO(Unit):
  do IO<Unit>:
    check(same12(1000n, 1, A.row_new(4n, 0, 12, 42, 7), P.new12(1, 7, 600, 42)), "12-bin selections")
    check(same40(1000n, 1, A.row_new(6n, 0, 40, 42, 7), P.new40(2, 7, 400, 42)), "40-bin selections")
    check(U32.is_eq(P.choose12(P.new12(1, 7, 600, 42), 0.0), 0), "12-bin lower endpoint")
    check(U32.is_eq(P.choose40(P.new40(2, 7, 400, 42), 0.0), 0), "40-bin lower endpoint")
    check(U32.is_eq(P.choose12(P.new12(1, 7, 600, 42), 1.0), 11), "12-bin upper clamp")
    check(U32.is_eq(P.choose40(P.new40(2, 7, 400, 42), 1.0), 39), "40-bin upper clamp")
    check(U32.is_eq(F.min(7, 2), 2), "scalar minimum")
    check(U32.is_eq(F.max(7, 2), 7), "scalar maximum")
    check(U32.is_eq(P.choose12(zero12(), 0.0), A.choose(A.evaporate_row(A.row_new(4n, 0, 12, 42, 7), 0.0), 0.0, 12)), "12-bin zero total")
    check(U32.is_eq(P.choose40(zero40(), 0.0), A.choose(A.evaporate_row(A.row_new(6n, 0, 40, 42, 7), 0.0), 0.0, 40)), "40-bin zero total")
    check(U32.is_eq(P.choose12(zero12(), 1.0), 11), "12-bin zero total clamp")
    check(U32.is_eq(P.choose40(zero40(), 1.0), 39), "40-bin zero total clamp")
    check(U32.is_eq(P.choose12(P.apply12_0(zero12(), [head(0), head(1)], 1.0), 0.5), 1), "12-bin exact tie chooses right")
    check(U32.is_eq(P.choose40(P.apply40_0(zero40(), [head(0), head(1)], 1.0), 0.5), 1), "40-bin exact tie chooses right")
    IO.print("14 packed-kernel checks passed (including 2000 roulette comparisons)")
