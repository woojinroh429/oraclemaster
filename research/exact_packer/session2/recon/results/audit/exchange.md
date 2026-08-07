# The right axis is the exchange rate w1/w3, not which term is the larger share

objmix.md classified instances by which penalty dominates the total.  That classification is
wrong, and prob_34 is the counterexample that shows why: 91% of its objective is bay preference,
so it was filed as preference-dominated -- but its weights are w1 = 13333 against w3 = 125, so one
unit of tardiness costs 107 units of preference.  Preference dominates the total only because the
solution has ZERO tardiness.  The instant a move buys a tardy unit it is catastrophic.

That is exactly how the aim240 arm lost there:

    base   Z1 0   Z3 1585   ->  222,449
    low    Z1 1   Z3 1562   ->  234,563     +5.45%

It saved 23 units of preference, worth 2,875, and paid 13,333 for one unit of tardiness.

## The rate across the set

    band          n    instances
    < 10x        10    P40 4.2, P24 5.6, P18 5.7, P3/P4/P27 6.3, P5/P13/P26/P36 8.3
    10 - 50x     19    P17/P1/P9/P15 11.1, P22 11.3, P8/P14/P35 12.3, P12/P23 13.3,
                       P21/P39/P25/P33/P37 33.3, P19/P20/P31 44.4, P11 49.9
    >= 50x       11    P38 50.8, P32 51.3, P29 52.2, P16 53.3, P10 66.7, P2/P7 88.9,
                       P6/P28 100.2, P30/P34 106.7

Read off the instance file alone -- no solution needed, nothing to estimate.

## Four unrelated experiments separate on this axis and not on the other

Re-reading logs already on disk, split by band:

    aimset  pair    >=50x  n=3  med +4.35%   0 better / 3 worse   P6+4.3 P16+2.9 P30+5.0
            spread  >=50x  n=3  med +4.73%   0 better / 3 worse   P6+2.0 P16+7.9 P30+4.7
    b240    a4      >=50x  n=2  med -7.64%   2/0     but 10-50x   n=2 med +9.17%  0/2
            lst     >=50x  n=2  med -6.29%   2/0
    newaxis v2      >=50x  n=3  med -5.25%   2/1
    rounds  R2      >=50x  n=3  med -4.55%   2/1     but 10-50x   P1 +29.5%
            R3      >=50x  n=3  med -8.05%   2/1     but 10-50x   P1 +23.0%

The effects live in the high-rate band and reverse in the middle band, so pooling cancels them.
That is the mechanism behind this session's recurring verdict that arms differ by less than the
same arm differs between draws.

Note this also explains the earlier "Z1-dominated 4 of 4" reading: three of those four (P6, P16,
P30) are high-rate instances and the fourth, P20 at 44x, was exactly +0.00%.  The share-based
classification agreed by coincidence.

## Not yet established

aim240 is testing the rule at 240 s and its first two pairs go the other way -- P2 (88.9x) at
+0.76% and P34 (106.7x) at +5.45%, both losses for the arm the rule predicts should win.  Two
pairs out of fourteen, and P34's own spread across four base draws is 4.6%, so this is not
decisive either way.  The two live explanations are that the rule holds and these two draws were
unlucky, or that the 60 s signal does not survive a 4x budget.  The queue covers the whole rate
range including P6, P16 and P30 -- the three the 60 s result rested on -- so it can separate them.
