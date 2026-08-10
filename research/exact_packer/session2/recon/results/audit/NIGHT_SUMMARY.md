# What this night actually established

Thirteen arms measured, one shipped.  The shipped change is real but small and rests on two of the
forty finals instances; the more useful output is the methodological fault below, which applies to
all thirteen.

## The two training sets, and which one counts

`report/techreport_ko.md` table 2 separates them:

                      preliminary median / range     finals median / range
    blocks n          200   100-300                  225   150-300
    bays m            3     2-5                      3     2-5
    tardiness Z1      0     0-2,306                  480   1-10,536
    Z1 = 0 count      21 / 40                        0 / 40
    objective         99,408                         5,005,623

    data/train    prob_2 = 100 blocks, Z1 = 0 in every run   -> PRELIMINARY
    data/stage2   prob_1 = 150, prob_16 = 300, Z1 > 0 always -> FINALS

`HIDDEN_SET.md` describes the PRELIMINARY hidden set (P1-P6 at 60-900 s) and says so in its first
line.  That round is over.  Late in this session its analogue table was read as current, the
measurements were moved onto `data/train`, and P1/P2/P3 came back byte-identical -- which is what
easier instances with Z1 already 0 do.  Two conclusions were published on that basis and are
retracted here: that the 37 pairs stood in for nothing, and that the spread being chased does not
exist where it counts.  Both were drawn from preliminary data.  Every A/B before that point was on
`data/stage2`, which is correct.

## The fault that does apply to all thirteen arms

The tech report states the house convention for judging a change on the finals set:

> all 40 finals instances, paired, at 180 s, judged by SIGN COUNTS OVER THE SET rather than per
> instance -- because one instance answers the same question with about 3% of spread, and
> unchanged code moved 8.4% between two runs an hour apart.  No single pair can resolve an effect
> of this size.

This session did the opposite: two instances out of forty, judged per instance, with replicates.
That design cannot separate an arm from the machine, and it is why twelve arms produced signs that
flipped on the next draw.  The correct experiment for any of them is 40 pairs at 180 s and a sign
count -- roughly four hours per arm, and the only way the answer means anything.

## What was shipped, and its honest status

`myalgorithm.py`: `nw = cpu - 1` when `cpu >= 4` and `timelimit <= 240`, else unchanged.
`WORKERS=n` overrides; `WORKERS=4` restores the previous behaviour byte for byte.

    finals prob_1 / prob_16, 60-240 s   worst draw -11.0% mean over 6 cells, span tighter in 5/6
    finals prob_1 / prob_16, 480 s      span advantage gone entirely -- hence the gate
    the gate fires at 180 s, which is the budget the house A/B convention uses

Measured on the right set, at four budgets, 37 pairs.  Measured on TWO instances, which the tech
report says is not enough to judge a change.  So: plausibly positive, not established.  The 40-pair
sign count at 180 s is what would establish or kill it.

## The error pattern, recorded because it repeated

Six claims were published in this session and overturned by later evidence:

    "60 s reverses the 120 s win"           one pair; three pairs averaged -0.85%
    "240 s reverses it"                     one pair; five pairs averaged -4.25%
    "control spread is 1.3%"                two draws; the third made it 13.0%
    "worst draw improves in all cells"      n=3 cell; n=5 moved it +3.12% -> -0.49%
    "saturation explains where w3 pays"     predicted prob_16 winning at 480 s; it lost
    "the 37 pairs measure nothing scored"   read the preliminary hidden set as current

The first five are the same mistake: a directional claim at two or three draws, against spreads of
11-33%.  The sixth is worse -- it discarded correct data and redirected an hour of machine time
onto a finished round.

## What to do first next session

1. Judge the shipped worker count properly: all 40 `data/stage2` instances, paired, 180 s,
   `WORKERS=3` vs `WORKERS=4`, sign count over the set.  ~4 hours.  Keep it or drop it on that.
2. Any future A/B uses the same protocol.  No arm gets a verdict from replicates on one or two
   instances, whatever the effect size looks like.
3. `HIDDEN_SET.md` should carry a header saying it is the preliminary round, so it cannot be
   mistaken for current again.
