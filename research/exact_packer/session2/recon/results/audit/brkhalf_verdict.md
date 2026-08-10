# BRKPAR=half IS REFUTED, AND THE REASON IS A DESIGN ERROR IN MY OWN PATCH

    arm        r1        r2        r3       mean      best draw
    off     422,629   499,210   422,629   448,156     422,629
    all     453,039   472,234   413,954   446,409     413,954
    half    492,458   472,234   472,234   478,975     472,234

    all  vs off, paired:  +7.20%  -5.40%  -2.05%   mean -0.09%
    half vs off, paired: +16.52%  -5.40% +11.74%   mean +7.62%

half is the WORST of the three arms on every summary: mean, best draw, and two of three pairs.

## WHY, AND IT IS NOT NOISE

`(wid // 2) % 2 == 0` selects wid 0 and wid 1.  On prob_1, wid 0 is config A and wid 1 is config
B -- the configuration that has never gone below 516,577 in 540 draws.  So half actually does:

    one of the two config-A workers gets brk
    the other brk slot is spent on a worker that cannot win this instance at all

`all` gives brk to BOTH config-A workers.  So on prob_1, half is dominated by construction: it is
strictly less brk than `all` on the workers that matter, and strictly more disturbance than `off`.
The design intent -- "keep one pure restart worker per configuration" -- was implemented correctly
and is meaningless on an instance where one whole configuration is a blank.

## WHAT SURVIVES

The hypothesis that leaving pure workers protects the minimum is NOT supported at n=3.

all vs off is a wash: mean -0.09%, signs +7.20 / -5.40 / -2.05.  brkcal's three prob_1 replicates
gave +0.16% with the same sign scatter.  Six paired replicates now say brk is neutral on prob_1.

The lesson that transfers: DO NOT CUT THE WORKER POOL ACROSS THE CONFIGURATION AXIS.  If the pool
is to be split for an operator, the split has to happen INSIDE the winning configuration -- which
is what PARROUND does, and it is the only reason that patch is still standing.

OGC_BRKPAR stays in the file at its default "all", i.e. no behaviour change, as a record of a
refuted wiring rather than an option to use.
