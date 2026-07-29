# The hidden set, and what it means for what to measure

From the preliminary final report.  Six problems, not forty.

    Problem  Time limit (s)  Bays  Blocks       w1   w2   w3
    P1                   60     3     100   21,622   10  150
    P2                  120     2     150    8,000    4  200
    P3                  240     3     200   17,778    5  150
    P4                  480     3     150   13,333    7  150
    P5                  600     4     200   13,333    7  133
    P6                  900     3     250    6,667    8  150

## Training instances that stand in for each

Matched on bays AND block count; the ones listed first also match w2 and w3 exactly.

    P1   60s   prob_2, prob_3            (also prob_21, prob_24)
    P2  120s   prob_8                    (also prob_27, prob_30)
    P3  240s   prob_9, prob_35           (also prob_32, prob_33)
    P4  480s   prob_26 -- w1, w2 and w3 ALL match; also prob_5, prob_6, prob_7
    P5  600s   prob_10, prob_11, prob_12
    P6  900s   prob_37, prob_38, prob_39

## What this changes

**The budgets.** Everything here has been validated at 60s.  Only P1 runs at 60s; the mean
hidden limit is 400s and P6 gets 900.  Whether this algorithm converts a larger budget into a
better answer is no longer a side question, it is the main one.

**Which instances count.** Fifteen of the forty match no hidden shape at all -- prob_1,
prob_4, prob_13..20, prob_22, prob_23, prob_25, prob_36, prob_40.  That includes every n=300
instance, since the hidden set stops at 250.  prob_18, the +34.8% loss that a night was spent
chasing, is one of them.

**Where the losses actually matter.** prob_11 and prob_12, where v2 loses by 24-27% at 60s,
are P5 analogues -- and P5 is a 600s problem.  Losing at 60s and losing at 600s are different
claims and only the second one counts.

**What is over-fitted.** Five-bay tuning is wasted (the hidden max is 4).  n=300 tuning is
wasted.

## Ablation: the repair operators do not earn their budget

Full roster against beam+regrow alone, on the real instances at their real limits:

    P3  240s    103825  vs   101535     search alone is 2.2% BETTER
    P4  480s   2586438  vs  2586438     identical to the digit -- Z1, Z2 and Z3 all equal
    P6  900s  29712782  vs 30011799     full roster 1.0% better, inside P6's ~4% noise

P4 is the sharpest. It is where v2 beats the submitted algorithm by 9.87%, and four repair
passes plus the CP-SAT assignment produced not one improvement in 480 seconds.  That win is
entirely the beam's.

P3 shows them being actively harmful, and why: with the repair passes on, Z2 comes out 2375
and Z3 613; with only the search, Z2 is 4377 and Z3 531.  They trade one against the other
and lose on the exchange.  The server's own solution has BOTH low -- Z2 2299 and Z3 527 --
which neither of our configurations reaches.

That is not something a post-pass can fix.  Getting both at once requires the beam to weigh
them while placing, and it cannot today: for each block it generates the earliest feasible
slot and nothing else, so there is no alternative for the rank to choose between.  The rank
already carries w1*tardy + w3*pen -- what is missing is a second candidate to apply it to.

## Does conceding tardiness buy preference?  Not on P3.

The arithmetic invites it: w1=17778, w3=150, so one unit of tardiness is repaid by 118.5 of
Z3, and our Z3 is 527.  Measured on the beam's own P3 solution, 27 of 200 blocks pay a
preference penalty.  Trying each one in the bay it wants at successively later entry times:

    3 of 27 would pay -- and all three at wait 0, meaning the bay had room and the beam
    simply did not use it.  Total gain 1650 on an objective of 154510.

The other 24 cannot enter their preferred bay at ANY time within eight units of waiting.
Preferred bays are saturated, so conceding tardiness does not open the door.

Via Z2 it is arithmetically impossible: one unit of tardiness needs 3556 of Z2 back and our
entire Z2 is 3391.

Caveat worth keeping: the probe moved one block at a time.  If the opening requires several
blocks to shift together it would not show up here -- the same blind spot that limited
single-block bay moves to 0.56-3.47% earlier.
