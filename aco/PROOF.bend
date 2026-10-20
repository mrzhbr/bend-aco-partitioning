import Base
import ./core.bend as A
import ./LAWS.bend as Laws

def Laws.evaporation_preserves_choices(row, factor):
  match row:
    case A.Bin{index, value}:
      {==}
    case A.Split{+cut, value, +left, +right}:
      %Laws.evaporation_preserves_choices(left, factor) :
        {Laws.Fork{cut, Laws.shape(A.evaporate_row(left, factor)), Laws.shape(A.evaporate_row(right, factor))}
        == Laws.Fork{cut, _, Laws.shape(right)} : Laws.Shape}
      %Laws.evaporation_preserves_choices(right, factor) :
        {Laws.Fork{cut, Laws.shape(A.evaporate_row(left, factor)), Laws.shape(A.evaporate_row(right, factor))}
        == Laws.Fork{cut, Laws.shape(A.evaporate_row(left, factor)), _} : Laws.Shape}
      {==}

def Laws.unpack_one_block(b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15):
  {==}
