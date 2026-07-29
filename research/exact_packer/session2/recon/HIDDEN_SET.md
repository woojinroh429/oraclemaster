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
