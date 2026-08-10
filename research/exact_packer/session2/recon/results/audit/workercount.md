# OVERSUBSCRIBING FOUR CORES COSTS 14-15%, AND IT IS THE FIRST RESULT TONIGHT READABLE AT n=2

    prob_1, local 120 s

    arm    r1        r2        vs w4
    w4    584,609   592,251    --          control spread 1.3%
    w6    701,633   653,806    +20.0%  +10.4%     mean +15.2%
    w8    671,556   669,301    +14.9%  +13.0%     mean +14.0%

Both arms lose on both replicates, and the effect is 8-15x the control arm's own spread.  Every
other arm tonight was a 2-10% effect measured against an 11-22% spread; this one is a 14-15%
effect against 1.3%, which is why two replicates settle it and sixty cells settled nothing.

The remaining three replicates were cut: they would narrow the size, not the sign.

## AND w6 IS THE ONLY SETTING WHERE ALL SIX AXES OPEN

Workers open on `_AXES[(wid + 1) % 6]`, so with four workers axes 5 and 0 never open a run.  Six
workers is the first configuration where they do -- and it still loses by 15%.  Whatever those two
axes are worth, it is smaller than the cost of splitting the cores.

## WHAT THE SLOPE IMPLIES, AND WHAT IS BEING RUN NEXT

Cutting each worker's share of a core from 1.00 to 0.67 costs 20%.  A slope that steep makes the
other direction worth pricing: three workers get 1.33 cores each, two get 2.00.

    the gain    each draw is better, by a quantity the 0.67 measurement says is large
    the cost    the score is a MIN over the workers, so w2 halves the number of draws it is taken
                over, and prob_1's draws sit on a heavy left tail (456 distinct values in 1,176)

AND w2 RAISES RUN-TO-RUN VARIANCE BY CONSTRUCTION -- a minimum over two is more variable than a
minimum over four.  Reducing that variance is the stated goal, so an arm that wins on the mean and
loses on the span is the wrong trade for a per-instance score where the worst run sets the tier.
harness/nw2.sh reports mean, worst cell and span per arm for exactly that reason.
