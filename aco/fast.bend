import Base
import ./core.bend as A

# Shared support for the generated pure-Bend register kernels in packed.bend.
# Sixteen consecutive choices share one allocation instead of sixteen list cells.
type Choices is Data:
  Choices{b0: U32, b1: U32, b2: U32, b3: U32, b4: U32, b5: U32, b6: U32, b7: U32,
    b8: U32, b9: U32, b10: U32, b11: U32, b12: U32, b13: U32, b14: U32, b15: U32}

type Ant is Data:
  Ant{path: List<&2, Choices>, fitness: U32}

type Trail is Data:
  Trail{path: List<&2, Choices>, amount: F32}

type Head is Data:
  Head{bins: Choices, amount: F32}

def word(select: Bool, a: U32, b: U32) -> U32:
  match select:
    case True{}:
      a
    case False{}:
      b

def number(select: Bool, a: F32, b: F32) -> F32:
  match select:
    case True{}:
      a
    case False{}:
      b

def min(+a: U32, +b: U32) -> U32:
  word((a < b : U32), a, b)

def max(+a: U32, +b: U32) -> U32:
  word((a > b : U32), a, b)

def fitness(ant: Ant) -> U32:
  match ant:
    case Ant{path, value}:
      value

def pick(a: Ant, b: Ant, first: Bool) -> Ant:
  match first:
    case True{}:
      a
    case False{}:
      b

def better(+a: Ant, +b: Ant) -> Ant:
  pick(a, b, (fitness(a) <= fitness(b) : U32))

def best(ants: List<&2, Ant>, winner: Ant) -> Ant:
  match ants:
    case Nil{}:
      winner
    case Con{ant, rest}:
      best(rest, better(winner, ant))

def trails(ants: List<&2, Ant>) -> List<&2, Trail>:
  match ants:
    case Nil{}:
      []
    case Con{Ant{path, value}, rest}:
      Trail{path, A.reward_amount(value)} <> trails(rest)

# Transpose one sixteen-item block. Reverse both accumulators to retain ant order.
def advance(ants: List<&2, Trail>, heads: List<&2, Head>, tails: List<&2, Trail>) ->
  List<&2, Head> & List<&2, Trail>:
  match ants:
    case Nil{}:
      (List.reverse(&2, Head, heads), List.reverse(&2, Trail, tails))
    case Con{Trail{Con{bins, tail}, +amount}, rest}:
      advance(rest, Head{bins, amount} <> heads, Trail{tail, amount} <> tails)
    case Con{Trail{Nil{}, amount}, rest}:
      advance(rest, heads, tails)

def left_trails(ants: List<&2, Trail>, +count: Nat) -> List<&2, Trail>:
  match ants:
    case Nil{}:
      []
    case Con{Trail{path, amount}, rest}:
      Trail{List.take(&2, Choices, path, count), amount} <> left_trails(rest, count)

def right_trails(ants: List<&2, Trail>, +count: Nat) -> List<&2, Trail>:
  match ants:
    case Nil{}:
      []
    case Con{Trail{path, amount}, rest}:
      Trail{List.drop(&2, Choices, path, count), amount} <> right_trails(rest, count)

# Scan only real bins. Avoid Array.to_list: it made the old ant walk non-flat.
# The last extra read is discarded; array indexing wraps within its allocation.
def finish(left: Nat, +index: U32, pair: Array<U32> & U32,
  low: U32, high: U32, path: List<&2, Choices>) -> Ant:
  match left pair:
    case 0n _:
      Ant{List.reverse(&2, Choices, path), (high - low : U32)}
    case 1n+rest Tuple{loads, +value}:
      finish(rest, (index + 1 : U32), Array.get(U32, loads, index),
        min(low, value), max(high, value), path)

def flatten(chunks: List<&2, Choices>, acc: List<&2, U32>) -> List<&2, U32>:
  match chunks:
    case Nil{}:
      List.reverse(&2, U32, acc)
    case Con{Choices{b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15}, rest}:
      flatten(rest, b15 <> b14 <> b13 <> b12 <> b11 <> b10 <> b9 <> b8 <>
        b7 <> b6 <> b5 <> b4 <> b3 <> b2 <> b1 <> b0 <> acc)

def outcome(best: Ant, items: U32, final: U32, evaluations: U32) -> A.Outcome:
  match best:
    case Ant{path, value}:
      A.Outcome{final, A.Ant{List.take(&2, U32, flatten(path, []), U32.to_nat(items)), value}, evaluations}
