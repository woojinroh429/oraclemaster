# WHAT A 260,000 ON stage2/prob_1 MUST CONTAIN, AND WHY WE DO NOT GET IT

The weights are w1=6667, w2=3, w3=600, so obj = 6667*Z1 + 3*Z2 + 600*Z3 and 260,000 pins the
components almost exactly:

    Z1 = 1, Z2 ~ 3000, Z3 ~ 407   ->   6,667 + 9,000 + 244,200 = 259,867

So a 260k solution holds Z1 at about 1 AND Z3 at about 407 at the same time.  We have produced
Z1 = 1 (once) and Z3 = 441 (once) and never together, over 458 recorded runs.

## WE ALREADY HAVE THE MACHINE THAT REACHES Z3 ~ 445

From this session's own brk record on prob_1:

    brk off   492,458   Z1 = 2    Z2 = 2708   Z3 = 785
    brk on    428,809   Z1 = 22   Z2 = 5045   Z3 = 445    -12.9%

bayrepack cuts Z3 by 43% and 445 is the lowest this project has recorded.  It also revives the
exact CP-SAT assignment pass, which returned gain 0 in the control and 72,673 once brk had
repacked a bay.

## AND brk IS NOT DOING ANYTHING WRONG

bayrepack.py line 313 scores w1*z1 + w2*(...) + w3*z3, so it prices tardiness properly, and the
trade it took is correct arithmetic:

    Z1 cost   6667 * 20  = 133,340
    Z3 gain    600 * 340 = 204,000
    net                    -70,660

It is optimising the objective it was given.  The Z1 rise is the PRICE of the Z3 gain, not a bug.

## SO THE 260k IS NOT A DIFFERENT TRADE-OFF POINT.  IT IS A BETTER SOLUTION.

Z1 = 1 with Z3 = 407 is not somewhere on the curve we are riding -- it is off it.  It says an
arrangement exists that takes the preference gain WITHOUT paying tardiness, and myalgorithm.py's
own note says where that comes from:

  > CP-SAT says Z3 821 -> 387 is admissible at exact per-slice area capacity, and _regroup showed
  > the obstruction is the blocks that STAY.

387 is an assignment-level bound.  A solver that decides the bay assignment exactly, and only then
places geometry, lands near it by construction.  Our pipeline runs that solver as `bay`, a RESCUE
operator inside the improvement loop, which by construction can only touch what the beam already
built and -- as the brk record shows -- finds no move at all until something else clears space
for it.

## WHICH MAKES THE NEXT STEP AN ORDERING CHANGE, NOT A PARAMETER

Everything measured in this session moves a weight, a count or a width inside the existing
pipeline: construct with the beam, then repair.  The gap to 260k is that the exact assignment
should be part of CONSTRUCTION rather than a late rescue.  That is a different shape of change
from all sixteen arms tried tonight, and it is the one the numbers point at.

## MEASURED: THE EXACT ASSIGNMENT CANNOT MOVE Z3 AFTER THE FACT EITHER

_assign -- the CP-SAT bay pass -- run directly on a finished 60 s beam solution with budgets far
beyond what the operator loop ever gives it:

    beam          obj 664,943   Z1 17   Z2 6468   Z3 887
    _assign 30 s  obj 664,730   Z1 17   Z2 6397   Z3 887     converged in 18 s
    _assign 90 s  obj 664,730   Z1 17   Z2 6397   Z3 887     identical

Z3 does not move by one unit.  The solver converges in 18 seconds and the only thing it finds is
71 units of Z2.  Tripling the budget changes nothing.

So exact assignment as a REPAIR is closed, alongside z3_reassign and ruin_tardy.  Every pass that
operates on a placed solution is blocked by the same thing _regroup named: the obstruction is the
blocks that STAY, and once geometry is fixed there is no assignment freedom left to solve for.

## WHICH SHARPENS WHAT THE 260k ROUTE MUST BE

CP-SAT's 387 bound is stated at exact per-slice AREA capacity -- it is a bound on the assignment
problem, before geometry.  A pipeline that fixes the assignment first and then places geometry to
match it inherits that bound by construction.  Ours does the reverse:

    now      beam constructs geometry and assignment together, then assignment is repaired
    needed   assignment is solved, then geometry is placed to realise it

The repair slot is where we put a solver that can only pay off in the construction slot.  That is
one ordering change, and it is the only direction left that every measurement tonight points at:
three repair passes inert, six scoring-knob families absorbed by the attractor, width a U near its
peak, and now the exact solver itself finding nothing downstream of the beam.
