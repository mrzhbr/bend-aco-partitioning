import Base

# U32 quarter-weight units keep both problem fitnesses exact.
# Problem 1: 4*(2*i+1). Problem 2: i*i. i starts at one.
def weight(+problem: U32, +i: U32) -> U32:
  Bool.pick(U32, U32.is_eq(problem, 1), (4 * (2 * i + 1) : U32), (i * i : U32))

# Portable deterministic RNG: xorshift32, with an avalanched stream per ant.
# Different from NumPy PCG64; never claim same-seed equivalence to NumPy.
def mix(+x: U32) -> U32:
  +a = U32.mul(U32.xor(x, U32.shrn(x, 16n)), 2146121005)
  +b = U32.mul(U32.xor(a, U32.shrn(a, 15n)), 2221713035)
  U32.xor(b, U32.shrn(b, 16n))

def next(+state: U32) -> U32:
  +a = U32.xor(state, U32.shln(state, 13n))
  +b = U32.xor(a, U32.shrn(a, 17n))
  U32.xor(b, U32.shln(b, 5n))

def uniform(state: U32) -> F32:
  (U32.to_f32(U32.shrn(state, 8n)) / 16777216.0 : F32)

def ant_seed(seed: U32, generation: U32, index: U32) -> U32:
  U32.or(mix(U32.xor(seed, U32.xor(U32.mul(generation, 2654435769),
    U32.mul((index + 1 : U32), 2246822519)))), 1)

# An immutable weighted decision tree; the mass of every internal node is the
# F32 sum of its children. Pad to a power of two with zero-weight choices.
type Row is Data:
  Bin{index: U32, mass: F32}
  Split{cut: U32, mass: F32, left: Row, right: Row}

def mass(row: Row) -> F32:
  match row:
    case Bin{index, value}:
      value
    case Split{cut, value, left, right}:
      value

def split_index(row: Row) -> U32:
  match row:
    case Bin{index, value}:
      0
    case Split{index, value, left, right}:
      index

def left_mass(row: Row) -> F32:
  match row:
    case Bin{index, value}:
      0.0
    case Split{cut, value, left, right}:
      mass(left)

def node(cut: U32, +left: Row, +right: Row) -> Row:
  Split{cut, (mass(left) + mass(right) : F32), left, right}

def row_new(+depth: Nat, +start: U32, +bins: U32, +seed: U32, +item: U32) -> Row:
  match depth:
    case 0n:
      value = uniform(mix(U32.xor(seed, U32.xor(U32.mul((item + 1 : U32), 3266489917), start))))
      Bin{start, Bool.pick(F32, (start < bins : U32), value, 0.0)}
    case 1n+rest:
      +middle = (start + U32.shln(1, rest) : U32)
      node(middle, row_new(rest, start, bins, seed, item),
        row_new(rest, middle, bins, seed, item))

def table_new(left: Nat, +item: U32, +bins: U32, +depth: Nat, +seed: U32) -> List<&2, Row>:
  match left:
    case 0n:
      []
    case 1n+rest:
      row_new(depth, 0, bins, seed, item) <>
        table_new(rest, (item + 1 : U32), bins, depth, seed)

# Direction is an explicit parameter because Bend matches parameters, not
# computed conditions. The recursive argument is a structural subtree.
def choose_go(row: Row, +threshold: F32, left: Bool) -> U32:
  match row left:
    case Bin{index, value} _:
      index
    case Split{cut, value, +a, b} True{}:
      choose_go(a, threshold, (threshold < left_mass(a) : F32))
    case Split{cut, value, +a, +b} False{}:
      +rest = (threshold - mass(a) : F32)
      choose_go(b, rest, (rest < left_mass(b) : F32))

def choose(+row: Row, u: F32, +bins: U32) -> U32:
  +threshold = (u * mass(row) : F32)
  # Multiplication may round up to the total: clamp like the original Python.
  U32.min(choose_go(row, threshold, (threshold < left_mass(row) : F32)), (bins - 1 : U32))

def deposit_go(row: Row, +bin: U32, +amount: F32, left: Bool) -> Row:
  match row left:
    case Bin{index, value} _:
      Bin{index, (value + amount : F32)}
    case Split{cut, value, +a, b} True{}:
      node(cut, deposit_go(a, bin, amount, (bin < split_index(a) : U32)), b)
    case Split{cut, value, a, +b} False{}:
      node(cut, a, deposit_go(b, bin, amount, (bin < split_index(b) : U32)))

def deposit(+row: Row, +bin: U32, amount: F32) -> Row:
  deposit_go(row, bin, amount, (bin < split_index(row) : U32))

def evaporate_row(row: Row, +factor: F32) -> Row:
  match row:
    case Bin{index, value}:
      Bin{index, (value * factor : F32)}
    case Split{cut, value, a, b}:
      node(cut, evaporate_row(a, factor), evaporate_row(b, factor))

def evaporate(table: List<&2, Row>, +factor: F32) -> List<&2, Row>:
  match table:
    case Nil{}:
      []
    case Con{row, rest}:
      evaporate_row(row, factor) <> evaporate(rest, factor)

# Ignore padded load slots: empty REAL bins still participate in the minimum.
def spread(left: Nat, values: List<U32>, low: U32, high: U32) -> U32:
  match left values:
    case 0n _:
      (high - low : U32)
    case 1n+rest Con{+value, tail}:
      spread(rest, tail, U32.min(low, value), U32.max(high, value))
    case _ Nil{}:
      (high - low : U32)

def bump(pair: Array<U32> & U32, bin: U32, weight: U32) -> Array<U32>:
  (loads, value) = pair
  Array.set(U32, loads, bin, (value + weight : U32))

type Ant is Data:
  Ant{path: List<&2, U32>, fitness: U32}

def finish_ant(path: List<&2, U32>, loads: Array<U32>, bins: U32) -> Ant:
  Ant{List.reverse(&2, U32, path),
    spread(U32.to_nat(bins), Array.to_list(~U32, loads), 4294967295, 0)}

def walk(table: List<&2, Row>, +problem: U32, +bins: U32, seed: U32,
  +item: U32, loads: Array<U32>, path: List<&2, U32>) -> Ant:
  match table:
    case Nil{}:
      finish_ant(path, loads, bins)
    case Con{row, rest}:
      +state = next(seed)
      +bin = choose(row, uniform(state), bins)
      loads = bump(Array.get(U32, loads, bin), bin, weight(problem, (item + 1 : U32)))
      walk(rest, problem, bins, state, (item + 1 : U32), loads, bin <> path)

def serial(left: Nat, +index: U32, +table: List<&2, Row>, +problem: U32,
  +bins: U32, +depth: Nat, +seed: U32, +generation: U32) -> List<&2, Ant>:
  match left:
    case 0n:
      []
    case 1n+rest:
      ant = walk(table, problem, bins, ant_seed(seed, generation, index),
        0, Array.new(U32, depth, 0), [])
      ant <> serial(rest, (index + 1 : U32), table, problem, bins, depth, seed, generation)

# Eight balanced ant batches. No shared mutable arrays or pheromone races.
def population(+forks: Nat, +first: U32, +count: U32, +table: List<&2, Row>,
  +problem: U32, +bins: U32, +depth: Nat, +seed: U32, +generation: U32) -> List<&2, Ant>:
  match forks:
    case 0n:
      serial(U32.to_nat(count), first, table, problem, bins, depth, seed, generation)
    case 1n+rest:
      +half = (count / 2 : U32)
      a b = population(rest, first, half, table, problem, bins, depth, seed, generation)
        population(rest, (first + half : U32), (count - half : U32), table,
          problem, bins, depth, seed, generation)
      List.append(&2, Ant, a, b)

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

def best(ants: List<&2, Ant>, acc: Ant) -> Ant:
  match ants:
    case Nil{}:
      acc
    case Con{ant, rest}:
      best(rest, better(acc, ant))

def deposit_path(path: List<&2, U32>, table: List<&2, Row>, +amount: F32) -> List<&2, Row>:
  match path table:
    case Con{bin, tail} Con{row, rest}:
      deposit(row, bin, amount) <> deposit_path(tail, rest, amount)
    case Nil{} _:
      table
    case _ Nil{}:
      []

def reward_amount(quarters: U32) -> F32:
  (100.0 / (U32.to_f32(quarters) / 4.0 + 1.0) : F32)

def reward(ants: List<&2, Ant>, table: List<&2, Row>) -> List<&2, Row>:
  match ants:
    case Nil{}:
      table
    case Con{Ant{path, value}, rest}:
      amount = reward_amount(value)
      reward(rest, deposit_path(path, table, amount))

type Outcome is Data:
  Outcome{final: U32, best: Ant, evaluations: U32}

def iterate(left: Nat, +problem: U32, +bins: U32, +depth: Nat, +seed: U32,
  +ants: U32, +factor: F32, +forks: Nat, +generation: U32,
  +table: List<&2, Row>, +best_ever: Ant, final: U32) -> Outcome:
  match left:
    case 0n:
      Outcome{final, best_ever, (generation * ants : U32)}
    case 1n+rest:
      +paths = population(forks, 0, ants, table, problem, bins, depth, seed, generation)
      +winner = best(paths, Ant{[], 4294967295})
      updated = evaporate(reward(paths, table), factor)
      iterate(rest, problem, bins, depth, seed, ants, factor, forks,
        (generation + 1 : U32), updated, better(best_ever, winner), fitness(winner))

# Count full populations, including the Python original's possible budget overshoot.
def run(problem: U32, +items: U32, +bins: U32, +ants: U32,
  evaporation: F32, +max_evals: U32, +seed: U32, forks: Nat) -> Outcome:
  +depth = {1n+U32.log2((bins - 1 : U32)) : Nat}
  generations = ((max_evals + ants - 1) / ants : U32)
  iterate(U32.to_nat(generations), problem, bins, depth, seed, ants,
    (1.0 - evaporation : F32), forks, 0, table_new(U32.to_nat(items), 0, bins, depth, seed),
    Ant{[], 4294967295}, 4294967295)
