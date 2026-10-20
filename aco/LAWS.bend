import Base
import ./core.bend as A
import ./fast.bend as F

# Erase pheromone magnitudes but retain every bin label and decision boundary.
type Shape is Data:
  Leaf{index: U32}
  Fork{cut: U32, left: Shape, right: Shape}

def shape(row: A.Row) -> Shape:
  match row:
    case A.Bin{index, value}:
      Leaf{index}
    case A.Split{cut, value, left, right}:
      Fork{cut, shape(left), shape(right)}

# Evaporation may change probabilities, never the available decisions or labels.
law evaporation_preserves_choices:
  for row: A.Row
  for +factor: F32
  {shape(A.evaporate_row(row, factor)) == shape(row) : Shape}

# Packed paths must retain all sixteen bin choices in their original order.
law unpack_one_block:
  for +b0: U32
  for +b1: U32
  for +b2: U32
  for +b3: U32
  for +b4: U32
  for +b5: U32
  for +b6: U32
  for +b7: U32
  for +b8: U32
  for +b9: U32
  for +b10: U32
  for +b11: U32
  for +b12: U32
  for +b13: U32
  for +b14: U32
  for +b15: U32
  {F.flatten([F.Choices{b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15}], [])
    == [b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15] : List<&2, U32>}
