# quality(axis, work), measured with no noise term

Every cell below is one beam draw under `OGC_WORKCAP`, which replaces seconds with the engine's own
work counter in the stop test and in both width controllers.  Three repeats of one configuration
returned an identical objective AND an identical placement digest, so nothing here needs replicates
and every difference is real at the size printed.

For scale: the same instance under the shipped, clock-driven build returns 3,061,389 .. 3,661,692,
a 19.6% band, which is what made every A/B this session unreadable.

    harness/beam1.py <prob> --work N --axis k [--useaxis]
    harness/axwork.sh          the table below
    harness/axworkread.py      reads it and scores allocation policies from it

## The table

    P4     work       axis 0      axis 1      axis 2      axis 3      axis 4      axis 5
           1500      3513389     3733242    2916374*     3574300     4231372     3437421
           3000      3408101     3194487    3028676*     3189844     4343640     3487284
           6000      3205130     3057550    2945225*     3072805     4270310     3433064
          12000      3341993    2953661*     3040249     3014170     4176281     3253535

    P16    1500      6667234     6357993    3247623*     4984622     9255020     6555177
           3000      6671345     6720274    3159373*     4799778     9382627     6610637
           6000      6408684     6214513    2477998*     4876883     9543435     6275935
          12000      6713700     6265165    2816901*     4834176     9420695     6261286

    P24    1500      3462529     3242086     3900130     3637538     3736218    3168404*
           3000     3080029*     3196119     3326701     3637538     3275633     3236366
           6000     2949426*     3196119     3446775     3706135     3438906     3273771

## Four things it says

**1.  More work is not more quality.**  Read down a column.  prob_16 axis 4 goes 9,255,020 ->
9,382,627 -> 9,543,435 -> 9,420,695: monotone worse over a factor of four in budget, then flat.
prob_24 axis 3 and axis 2 also degrade.  In work mode `Bcur = left_work/rem`, so more work is a
WIDER beam, and a wider beam ranks more states by the same myopic contact proxy and can crowd out
the state that completes well.  Beam search is not monotone in width.

This is the clean form of the question that ran through the whole session -- why does 240 s
sometimes lose to 60 s.  Clock noise sat on top of it; it is not the cause.

**2.  The curves are U-shaped and the bottom is per (instance, axis).**  On prob_16: axis 4 bottoms
at 1500, axis 3 at 3000, axes 0/1/2 at 6000, axis 5 is still falling at 12000.  A fixed constant
would be hardcoding.  But a single bottom is cheap to find, which is what makes an adaptive rule
possible at all.

**3.  Production sits at roughly half the optimum, on the instance where it matters.**  A 240 s
worker's draw is ~14 s, and prob_16 measures ~220 expansions/s, so a draw is ~3,000 work.  The
table's 3,000 cell for axis 2 is 3,159,373 and the shipped build returns 3.28M-3.66M -- they agree.
The 6,000 cell is 2,477,998, which is 11.4% below the best result this project has ever recorded on
prob_16 (2,795,643) and 22% below what it returns today.

It is also the exact opposite of OGC_BEAMCAP, which shrinks draws and measured +2.73% here.

**4.  The best axis is instance-specific AND its rank is not stable in work.**  prob_4 and prob_16
favour axis 2 at small budgets, prob_24 favours axis 0.  Worse, on prob_4 axis 2 wins at
1500/3000/6000 and comes THIRD at 12000, because axis 2 is flat there (4.1% across the whole range)
while axis 1 improves monotonically and overtakes it.

That is a harder objection to adaptive axis selection than the usual one.  Probing cheaply to pick
an axis and then concentrating budget on it invalidates the probe: a 1500-work probe on prob_4
picks axis 2, and at 12000 the answer is axis 1.

## What the margins say about a usable policy

    prob_16   axis 2 over the runner-up:  2.05x  2.13x  2.51x  2.22x   never flips
    prob_4    axis 2 over the runner-up:  1.17x  1.05x  1.04x  0.97x   flips at 12000
    prob_24   spread across all axes:     1.23x  1.18x  1.26x          no dominant axis

Where the margin is large the ranking is stable; where it is small the ranking flips, and where it
flips the cost of choosing wrong is small by the same token.  So the policy that fits the data is
not "find the best axis and commit to it" but "concentrate in proportion to the observed margin" --
no threshold, no instance detection, and it degrades to uniform rotation exactly where uniform
rotation is fine.

## Allocation, priced from the table

Scored offline from measured cells, so no further runs were needed.  `conc1` is an ORACLE: it is
told the instance's best axis, so it bounds what any adaptive policy could achieve.

    P16   rotate6 (6 x 3000, W=18000)   3,159,373
          conc1   (1 x 6000, W= 6000)   2,477,998    -21.57% for ONE THIRD of the work

    P4    best oracle gain                            -3.71%
    P24   best oracle gain                            -2.79%

So the ceiling on axis allocation is ~22% on prob_16 and under 4% on the other two.  It is a lever
for instances with a dominant axis and nothing anywhere else.

## What is NOT established

Every number here is ONE BEAM DRAW in work space.  The shipped algorithm is four workers, an
operator loop, and a polish, under a wall-clock budget.  None of this has been shown to survive
that path, and the transfer is where the noise comes back.

The table is also at a fixed B=96, K=4, while `_worker` sizes each draw from the axis's own Bmul
and K -- axis 2 runs at B=67, K=5 in production.  So "axis 2 wins" may be a statement about the
width rather than the scoring.  harness/axwidth.sh pairs the two at equal work to separate them.
