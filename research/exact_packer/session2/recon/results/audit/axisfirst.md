# THE BEAM DOES NOT PRODUCE prob_1's ANSWER, AND THE BEST AXIS IS THE ONE WITH THE WORST BEAM

## Run level: OGC_AXIS pinned, 240 s, one replicate each

    ax0  630,785     ax3  517,814
    ax1  469,427     ax4  468,853
    ax2  515,465     ax5  437,959   <- best pinned axis
                     rot  453,039   <- the shipped rotation

44% between the best and worst axis, which confirms at run level what the file already claimed
(32-210% between configs against 0.0-12.6% repeating one).  Both extremes -- best ax5 and worst
ax0 -- are the two axes that NEVER open a run under the shipped wiring.

## Construction level: 251 DRAW lines

    NOT ONE OF 251 CONSTRUCTIONS REACHED 450,000.  The best ever was 533,320.  Runs reach 437,959,
    and brkhalf reached 413,954.

So the beam never produces the answer on prob_1; it produces a starting point, and the repair
operators close the last 20%.  That claim is about the pooled minimum and does not depend on how
the draws are grouped, so it stands.

## A CLAIM I MADE HERE AND HAVE TO WITHDRAW

I wrote that ax5 has the WORST constructions (median 1,033,770) and the BEST final answer, and
called construction quality inversely related to run quality.  That was an artifact of pooling:
the per-axis table mixed config-A and config-B workers and mixed the pinned cells with the
rotation cell, and config B's constructions are much worse on this instance.  Read per cell, over
config-A workers only:

    cell        draws   best seed    med seed      final    seed -> final
    r1.ax0        34     687,209     936,201     630,785        8.2%
    r1.ax1        43     576,367     941,001     469,427       18.6%
    r1.ax2        34     587,906     886,482     515,465       12.3%
    r1.ax3        33     541,099     899,368     517,814        4.3%
    r1.ax4        34     533,320     962,988     468,853       12.1%
    r1.ax5        38     539,626     968,575     437,959       18.8%
    r1.rot        35     541,099     925,493     453,039       16.3%
    r2.ax0        38     602,487   1,004,051     469,650       22.0%

ax5's best seed is 539,626, mid-field, not worst.  There is no inversion.  What the table does
show is that the seed-to-final improvement ranges 4.3% to 22.0%, i.e. the operators' contribution
varies by a factor of five between cells.

## AND THE AXIS RANKING ITSELF IS NOT YET SAFE

ax0 has two replicates: 630,785 and 469,650.  That single axis spans 25%, which covers almost the
whole 44% gap I reported between the best and worst axes at one replicate each.  The r1 ranking
cannot be trusted until r2 is complete, and I should not have led with the 44%.

## THE FIRST ACTIONABLE SIGNAL OF THE NIGHT: IT IS THE SEED TAIL, NOT THE SEED

Over nine pinned-axis cells, correlating each cell's construction statistics against its final
run objective:

    r(best seed in the cell,   final) = +0.846
    r(median seed in the cell, final) = -0.328

The final answer tracks the BEST construction the cell produced and not the typical one.  The
operators improve whatever they are handed by roughly a fixed fraction -- the seed-to-final column
runs 4.3% to 22.0% -- so the answer comes out of the LEFT TAIL of the seed distribution.  Lifting
the median is worthless (r = -0.33); deepening the tail carries straight through (r = +0.85).

And the tail's spread is amplified:

    best seeds  532,420 .. 687,209   29%
    finals      422,629 .. 630,785   49%

## WHY THIS IS DIFFERENT FROM EVERY DEAD END TONIGHT

Round count, short rounds, brk, PARROUND, BRKPAR=half were all either "buy more draws" or "polish
the incumbent harder".  Both were wrong for the same reason: the draw is a seed, and polishing
acts on whatever seed it gets.  Deepening the seed tail is the one axis that has not been tried
and the one the correlation supports.

The axis knob is that lever -- each _AXES entry gives a different seed tail.  The RANKING is not
yet safe (ax0 alone spans 25% over two replicates), which r2 settles.

## FOUR CORRELATIONS, ONE STORY (nine cells)

    r(best seed,            final) = +0.846
    r(median seed,          final) = -0.328
    r(number of seeds,      final) = -0.354    more seeds -> better answer
    r(seconds per seed,     final) = +0.658    cheaper seeds -> better answer

    cell        seeds  mean s   best seed       final    Bmul
    r1.ax0        34     8.4     687,209     630,785     1.0
    r1.ax1        43     7.2     576,367     469,427     1.0
    r1.ax2        34     8.7     587,906     515,465     0.7
    r1.ax3        33     8.0     541,099     517,814     0.7
    r1.ax4        34     7.6     533,320     468,853     1.4
    r1.ax5        38     6.6     539,626     437,959     0.5
    r1.rot        35     7.8     541,099     453,039      -
    r2.ax0        38     7.6     602,487     469,650     1.0
    r2.ax1        35     7.6     532,420     422,629     1.0

The best r1 cell (ax5, 437,959) has the cheapest seeds at 6.6 s, the second-most of them, and the
narrowest beam at Bmul 0.5.  The worst (ax0, 630,785) has the most expensive seeds at 8.4 s and
the fewest.  The chain that fits is: narrower beam -> cheaper construction -> more seeds -> deeper
left tail -> better final.

## WHAT WOULD MAKE IT MORE THAN A STORY

Bmul is a continuous parameter, not an axis name, so if the chain is real it can be tested
directly with OGC_BEAMCAP without choosing an axis at all -- which would be a far more general
lever than picking one of six configs, and would not be fitted to prob_1.

RESERVATIONS, STATED BEFORE THE SWEEP FINISHES.  Nine points.  ax1 is Bmul 1.0 and won twice
(469,427 and 422,629), so Bmul alone does not explain the ranking.  Seed count and final are both
downstream of the axis, so the correlation may be covariance rather than cause.  And ax0 spans
25% by itself, which is most of the range being ranked.

## THE SEED-COUNT HALF OF THE STORY WAS ALREADY REFUTED, IN work_mode.md

Two of the four correlations above cannot be causal, and the file says why:

    "Splitting a budget into more than six draws.  With no clock in the search, one (axis, work)
     pair has exactly one answer.  `_worker` draws `axes[gen % 6]`, so a worker can produce at
     most six distinct results per work level; the seventh draw re-derives one it already holds.
     In production they differ only because the clock perturbs them.  Structural, not empirical."

    "OGC_BCAP (raise the beam width ceiling) ... Once work is the budget the adaptive controller
     makes a width ceiling inert: narrowing the beam leaves work unspent and `Bcur` grows back.
     Work is the currency, width is only how it is spent."

So a cell's 34 constructions are not 34 seeds.  They are at most six distinct answers plus clock
perturbation, which is exactly why r(median seed, final) is -0.33 while r(best seed, final) is
+0.85 -- the "best" is the best of about six real configurations and the rest are re-derivations.

r(seed count, final) = -0.354 and r(seconds per seed, final) = +0.658 are therefore covariance
with the axis, not a lever.  My "narrower beam -> cheaper seeds -> more seeds -> deeper tail"
chain is refuted on both of its middle links.

## WHAT IS NOT REFUTED, AND THE TOOL THAT SETTLES IT

WORK PER DRAW.  prob_16's productive axis returns 3,159,373 at work 3,000 and 2,477,998 at 6,000
-- 21.6% for doubling one draw.  No such table exists for prob_1.

And OGC_WORKCAP makes the measurement exact: three runs of prob_16 at work 4,000 returned
obj=6,684,986 with digest 00e0c6a4b5d1da5e every time, against a 19.6% band in production.  The
axis question I have been spending 240 s cells on, fighting a 25% spread, is answerable with no
noise at all by harness/beam1.py.

Also recorded because it is the largest single number in the file: on prob_16 ONE beam draw at
work 6,000 on axis 2 returns 2,477,998, while this project's best ever full run on that instance
is 2,795,643 and today's 240 s runs return 3.28M-3.66M.  A single draw beats the whole pipeline by
11.4% there.  Nothing has ever explained that.

## THE AXIS SWEEP FINISHED AND THE ANSWER IS NO

    axis     r1        r2        mean       spread
    ax0   630,785   469,650   550,218      25.4%
    ax1   469,427   422,629   446,028      11.1%   best mean
    ax4   468,853   445,860   457,357       5.2%
    ax5   437,959   482,013   459,986      10.1%
    ax3   517,814   437,484   477,649      18.4%
    ax2   515,465   515,465   515,465       0.0%
    rot   453,039       -

NO PINNED AXIS BEATS THE ROTATION.  The best mean, ax1 at 446,028, is 1.5% under the rotation's
single cell, and the pinned axes span 5-25% between their own replicates, so 1.5% is inside the
noise.  And the lowest value recorded all night -- 413,954 -- came from the ROTATION, in brkhalf's
`all` r3.  Twelve pinned cells never went below it.

I said after r1 that ax5 looked like the best axis at 437,959.  r2 returned 482,013.  That was a
draw, and withdrawing it is the third time tonight a one-replicate axis reading has reversed.

## WHAT THE SWEEP DID BUY: AXES DIFFER IN VARIANCE, NOT ONLY IN MEAN

    ax2   0.0%   515,465 twice, to the digit
    ax4   5.2%
    ax0  25.4%

On a per-instance score the worst case sets the tier, so low variance has value by itself.  The
rotation mixes all six, so its variance is contaminated by gamblers like ax0.  "Mix only the
low-variance axes" is a different proposal from "pin the best axis" and it is not closed -- but it
would need the variance ranking to hold on more than two replicates, and two replicates is exactly
what has misled me three times today.

## AND THE METHOD IS THE REAL FINDING

Fourteen 240 s cells -- 56 minutes of four cores -- produced "cannot separate, and negative".
Nothing below the 5-25% replicate spread is visible this way, and the effects worth having are
smaller than that.  Every remaining question goes to OGC_WORKCAP, where one (axis, work) pair has
one answer and a digest to prove it.
