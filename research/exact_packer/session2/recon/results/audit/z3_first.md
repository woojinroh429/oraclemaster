# Z3 is a pure bay cost, its aggregate floor is zero, and assigning best-bay-first is 97% better on two instances

## The structure nobody used

The objective is `w1*Z1 + w2*Z2 + w3*Z3` over `(bay, entry_time)`.

  - `Z3` is `sum(max(prefs_i) - prefs_i[bay_i])`.  **No time appears in it.**  It is a pure
    assignment cost.
  - `Z1` is tardiness, `max(0, entry + processing - due)`.  **No bay appears in it.**
  - `Z2` is load balance and is 0.2-4.2% of the score.

So the two terms that matter are functions of DISJOINT parts of the decision, coupled only through
feasibility: a bay can hold only so much at a time.

The beam does not exploit this.  It ranks states by CONTACT -- a packing-density surrogate -- and
the bay a block lands in is a by-product of where the contact score was best.  There is no
construction in the tree that treats preference as the primary objective.

## Z3's aggregate floor is zero

Assigning every block its best bay while respecting each bay's area-time capacity is a
transportation problem.  A greedy pass (largest area-time first, cheapest feasible bay) reaches
**Z3 = 0** on prob_1, prob_6, prob_16 and prob_24, and 1008 on prob_4.  Our solutions pay 612 /
5635 / 4718 / 1666 / 2619.

Preferences do not conflict in aggregate.  What forces Z3 > 0 is WHEN blocks need their bay.

## What Z3 = 0 costs in Z1

Assign every block its best bay, then schedule inside each bay by EDD, entering at the earliest
time its AREA fits alongside the residents.  Geometry ignored -- an estimate, not a solution.

    prob    our w1*Z1     our w3*Z3       our sum     Z3=0 w1*Z1      delta
    P24     1,763,157       999,600     2,762,757         43,329     -98.4%
    P1        113,339       367,200       480,539         13,334     -97.2%
    P4      1,213,212     1,395,927     2,609,139      2,156,451     -17.4%
    P16     2,426,606     1,179,500     3,606,106      4,933,210     +36.8%
    P6      4,453,222       749,455     5,202,677     14,732,965    +183.2%
    P20     7,713,719     1,306,200     9,019,919     44,522,226    +393.6%

And it splits cleanly by where the objective already sits:

    wins    P1 (Z3 is 73.2% of the score)   P4 (53.4%)   P24 (36.0%)
    losses  P16 (32.7%)   P20 (14.5%)   P6 (14.4%)

Which is what it should do.  If preference is most of the score, buying Z3 = 0 pays even at some
tardiness; if tardiness dominates, forcing best-bay wrecks the schedule.

This is not a gate or a tuned threshold -- the split is computed from the instance's own weights
and preference values, which the algorithm can read at load time.

## The caveat, stated plainly

**The estimate ignores geometry entirely.**  It uses area as the resource, and the whole engine
exists because area-feasible is not placement-feasible: polygons must not overlap in a 2D bay and
crane access must hold.  The real tardiness will be higher and 97% will not survive intact.

What makes it worth testing anyway is the size.  prob_1 is a factor of 36; geometry could cost 5x
the tardiness and the direction would still win.  prob_1 also has the loosest occupancy profile
measured (peak concurrent area 59.3% of bay area), so geometry is least likely to bind there.

## The next step, which is cheap and decisive

Take the best-bay + EDD assignment and push it through the engine's real feasibility path
(`check_feasibility`, `find_pos_in_bay`).  Either most of it places -- and this is worth building a
constructor around -- or it does not, and the direction is dead within the hour.  No new machinery
is needed for the test.
