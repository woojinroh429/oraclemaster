# WHAT brk'S OWN ACCOUNTING SAYS, AND WHY prob_20 WAS NEVER EVIDENCE

Measured on the brkcal queue, i.e. WITH the calibration guard in place.

## The objective shares, computed from each run's own Z terms and the instance's own weights

    prob_3    Z1  11.0%   Z2 1.0%   Z3 88.0%
    prob_1    Z1  13.4%   Z2 0.3%   Z3 86.3%
    prob_16   Z1  51.0%   Z2 0.3%   Z3 48.7%
    prob_24   Z1  76.5%   Z2 0.3%   Z3 23.2%
    prob_20   Z1  84.7%   Z2 0.1%   Z3 15.2%

## The result on each

    prob_3    Z3 88.0%   r1 -2.55%  r2 -0.17%   BOTH brk draws below BOTH control draws
    prob_1    Z3 86.3%   -6.52% over three replicates (measured with the bug live)
    prob_16   Z3 48.7%   +2.14%
    prob_24   Z3 23.2%   +1.84%
    prob_20   Z3 15.2%   see below -- NOT a result

## prob_20 IS NOT A DATA POINT, AND I REPORTED IT AS ONE TWICE

Two things kill it.

The controls do not repeat.  r1 off = 8,850,352 and r2 off = 8,769,505, which is 0.91% apart,
and the whole claimed brk effect was 0.91% and 0.45%.  Effect over spread is about 1.  The reason
8,769,505 appeared as both r1's brk and r2's control is that this instance lands in discrete
basins, not that the instance is deterministic -- which is what I asserted when I built the queue.

And brk's own opstat says it did nothing.  Sixteen worker-rounds across the two brk cells:

    r1  5.7  13.4  0.8  7.6  1.4  2.0  1.4  1.7   gain 0 on every one   (34.0 s)
    r2  7.7   8.3 17.7 14.7  1.4  1.3  0.0  0.6   gain 0 on every one   (51.7 s)

The operator never improved its worker's incumbent once.  Whatever moved the objective, it was
not brk; it was the beam being handed a different number of seconds.  So prob_20 measures the
COST of brk (34-52 worker-seconds) and nothing else, and the cost is real.

Contrast prob_3, where the same column is non-zero:

    r1  4.6  8.5 37.0  0.3 | 7.4  0.6 18.6  0.6    gains  0  0  69,766  0 | 0  0  14,111  0
    r2 37.5 35.2  5.4 38.6                         gains 39,641 12,565  0  0

## WHAT THIS DOES TO THE Z3 GATE

The gate drafted in scratchpad/z3gate.py put the crossover in the 48.7-86.3 gap on the strength of
prob_1 alone above it.  prob_3 at 88.0% is now a second instance above the gap, measured after the
calibration fix, with a 4/4 ordering against its controls.  Three instances sit below it and all
three lose.  The threshold is still FITTED -- five labelled points cannot derive one -- but it is
no longer fitted to a single positive case.

## THE DECIDING TABLE: brk's OWN GAIN COLUMN, EVERY CELL EVER LOGGED

Not a comparison of draws.  This is what the operator reported about its own effect on its own
worker's incumbent, summed over every brk worker-round in results/audit/*.log.

    prob   Z3 share   worker-rounds   paying   pay rate   brk seconds   raw gain
    3        88.0%              40        8       20%           599.3    202,603
    1        86.3%              80       44       55%         2,005.2  1,291,476
    16       48.7%              46        0        0%           391.6          0
    24       23.2%              24        0        0%            92.2          0
    20       15.2%              48        0        0%           234.2          0

**118 worker-rounds on the three low-share instances and not one of them returned a gain.**  718
worker-seconds spent, zero collected.  Against 52 of 120 paying on the two high-share ones.

This is a different kind of evidence from everything quoted for the gate before it.  The five
end-of-run objectives were draws, and prob_1's controls alone span 437,484 to 492,458, so a
five-point ordering of draws is close to meaningless.  A 0-of-118 against a 52-of-120 is not a
draw ordering; it is the operator saying, on every single occasion, that it found nothing.

WHAT IT DOES TO THE DOWNSIDE.  The objection to any fitted threshold is that it might switch the
operator off where it would have earned.  On these three instances there is nothing to switch off:
gating them costs the microseconds of _obj_shares and the 718 seconds come back to the beam.  The
risk is entirely on the other side -- switching it off where it DOES earn -- and that is not
governed by the threshold's placement in the 48.7-86.3 gap but by whether the MID-RUN share the
gate actually reads lands on the same side as the finished run's.  Which is what brkgate measures,
and until it has, the gate stays off.

## prob_1 SPLIT BY WHETHER brk ACTUALLY RAN (opstat tried > 0, not by tag name)

    brk ON    n= 11   reached 422,629  4 (36.4%)   median 437,484   worst 538,936
    brk OFF   n=305   reached 422,629 15 ( 4.9%)   median 518,803   worst 822,149

The minimum is 422,629 in BOTH arms.  brk does not find a floor the search cannot reach; it
reaches the existing floor far more often.  The median moves 518,803 -> 437,484 (-15.7%) and the
worst case 822,149 -> 538,936, and on a per-instance score the worst case is what sets the tier.

CAVEAT, RECORDED BECAUSE I OVERSTATED IT ONCE.  I priced two consecutive 422,629 hits against a
4.3% base rate and called it p = 0.002.  r3's CONTROL then returned 422,629 on its own.  The 4.9%
figure is over 305 runs of many different builds; the current build (rf35 + POLCAP 5) reaches that
basin more often than the historical average, so the true null for THESE replicates is higher than
4.9% and the p-value is optimistic.  n = 11 on the brk side is small.  The 0-of-118 gain column
remains the stronger evidence because it is not a comparison of draws at all.

## r3 REVERSES prob_1, AND EXPLAINS WHY THE GAIN COLUMN IS NOT THE SCORE

Three paired replicates, same build, calibration guard live:

    r1   off 492,458   brk 422,629   -14.18%
    r2   off 437,484   brk 422,629    -3.40%
    r3   off 422,629   brk 499,210   +18.06%
                                     -------
                              mean    +0.16%

prob_1 is NEUTRAL.  The -6.52% recorded before the fix and the -14.18% recorded after it were both
draws, and the spread (16-18%) swamps any effect, which is exactly the effect-over-spread test I
adopted after the prob_20 flip-flopping and then failed to apply to prob_1's first two cells.

THE MECHANISM, WHICH IS THE PART WORTH KEEPING.  In r3 brk paid on seven of eight worker-rounds:

    32,560   34,808   52,446   11,062   5,037   5,037   6,200      total 147,150

and the run still finished 18% WORSE than its control.  The beam's try count over round 0 went
12/8/11/8 = 39 in the control to 5/4/8/6 = 23 with brk on, a 41% cut.

So brk improves the incumbent it is handed, and the score is not the incumbent -- it is the minimum
over four workers, and what reaches prob_1's good basin is the beam RESTARTING, not any incumbent
being polished.  brk climbs the hill it is standing on while taking away the restarts that find a
different hill.

WHAT THIS DOES TO THE 0-OF-118 / 52-OF-120 TABLE.  Only half of it survives.

    "brk finds nothing on prob_16/24/20"     STANDS.  0 of 118 worker-rounds, 718 seconds, no
                                             gain.  There it is pure cost, and gating it off can
                                             lose nothing.
    "brk helps prob_1's score"               DOES NOT FOLLOW.  52 of 120 paying worker-rounds and
                                             a neutral paired result are consistent, because a
                                             per-worker gain is not a per-run gain.

The only paired gain left standing anywhere is prob_3: -2.55% and -0.17%, both brk draws below both
control draws, control spread 0.12%.

CONSEQUENCE FOR SHIPPING.  Unconditional brk is not justified by anything measured.  It is neutral
where it was supposed to win and costs 2% where it provably finds nothing.  The gate is not an
optimisation on top of an adopted operator any more -- it is the only configuration the evidence
supports: keep brk where a paired gain exists (prob_3) and where it is at worst neutral (prob_1),
remove it where 118 worker-rounds say there is nothing to find.

## THE NOISE FLOOR, MEASURED BY ACCIDENT ON prob_24

    r1   off 2,745,804   brk 2,635,539   -4.02%
    opstat brk gain, all eight worker-rounds:  0  0  0  0  0  0  0  0   (46.6 s spent)

An apparent 4% gain with a gain column of exactly zero.  Z3 did move, 1425 -> 1130, but the beam
moved it -- brk collected nothing and said so eight times out of eight.

TWO THINGS FOLLOW.

prob_24's 0-of-24 was NOT a calibration artifact.  It is 0-of-8 again with the guard live, so
"brk finds nothing where Z3 is a minority of the objective" now holds on post-fix data.

And this is the noise floor for every paired single replicate quoted tonight.  A 4% end-of-run
difference is available with zero causal contribution, which puts -2.55% (prob_3 r1), -0.91% and
-0.45% (prob_20), and a good part of -14.18% (prob_1 r1) underneath it.  The method of comparing
one run against one run does not work on these instances, whatever the arm.

The only column that is not a draw is opstat's gain, because it records what the operator did to
the incumbent it was given rather than where the run happened to land.  Read that way:

    prob_16 / 24 / 20    126 worker-rounds, gain 0, before AND after the fix
    prob_1 / 3           gains are real, but r3 showed a per-worker gain is not a per-run gain

which is why brkhalf asks a structural question -- does leaving two workers pure protect the
minimum -- instead of another draw comparison.

## THE RIGHT STATISTIC WAS IN THE LOGS ALL NIGHT: PER-WORKER OBJECTIVES

Every run prints WSTAT with all four workers' round-0 objectives.  Comparing those instead of the
run minimum gives four times the sample per run and does not depend on which worker got lucky.
P below is the fraction of (brk worker, off worker) pairs the brk one wins; 0.5 is no effect.

    prob_1    off n=12  min 422,629  med 599,592  max 866,567   spread 105%
              brk n=12  min 422,629  med 571,400  max 735,244   P = 0.559
    prob_3    off n= 8  min 4,363,763 med 4,622,402 max 4,980,388  spread 14%
              brk n= 8  min 4,281,933 med 4,473,967 max 4,717,037  P = 0.719
    prob_20   off n=12  min 8,769,505 med 9,773,904 max 12,777,493 spread 46%
              brk n= 8  min 8,769,505 med 9,958,913 max 12,638,642 P = 0.458
    prob_24   off n= 8  min 2,814,291 med 2,896,470 max 3,185,622  spread 13%
              brk n= 4  min 2,761,894 med 2,971,946 max 3,166,922  P = 0.484

prob_3 is the only clear win.  prob_20 and prob_24 are slight losses.  prob_1 is 0.559 -- brk does
lift the typical worker there, by 4.7% at the median -- AND IT DOES NOT MATTER, because the score
is the MINIMUM and prob_1's workers span 422,629 to 866,567.  Both arms have the same minimum.

## WHICH GIVES THE MECHANISM A SECOND HALF

brk helps a run only when BOTH hold:

    1. it finds something          -- Z3 must be a large share, else the gain column is 0
                                      (prob_16/24/20: 126 worker-rounds, zero, before and after
                                      the calibration fix)
    2. the minimum is set by per-draw QUALITY, not by the NUMBER of draws
                                      -- prob_1's worker spread is 105%, so min-of-N is dominated
                                      by the luckiest worker and a 4.7% median lift is invisible;
                                      prob_3's spread is 14%, so quality is what the min sees

prob_3 satisfies both.  prob_1 satisfies only the first, and brk actively harms it by spending the
restarts that produce the draws -- 39 beam tries to 23 in r3.  prob_16/24/20 satisfy neither.

STATED AS AN OVERFIT RISK, BECAUSE IT IS ONE.  That is two conditions fitted to five instances,
and I will not put either into the code as a predictor.  What it is good for is explaining why
BRKPAR=half should work without any predictor at all: leaving two workers pure keeps the draw
count that condition 2 is about, while brk supplies the quality on the other two.  The wiring
satisfies both conditions structurally instead of testing for them.

## brkcal, COMPLETE

    instance  rep   off          brk          paired   opstat gain (paying/rounds)
    prob_20   r1    8,850,352    8,769,505    -0.91%   0/8
              r2    8,769,505    8,730,149    -0.45%   0/8
    prob_3    r1    4,368,877    4,257,472    -2.55%   2/8   69,766 + 14,111
              r2    4,363,763    4,356,312    -0.17%   2/4   39,641 + 12,565
    prob_1    r1      492,458      422,629   -14.18%   7/8
              r2      437,484      422,629    -3.40%   5/8
              r3      422,629      499,210   +18.06%   7/8
    prob_24   r1    2,745,804    2,635,539    -4.02%   0/8
              r2    2,683,866    2,686,142    +0.08%   0/8

    paired means:  prob_20 -0.68%   prob_3 -1.36%   prob_1 +0.16%   prob_24 -1.97%

READ BY THE PAIRED MEANS ALONE, brk LOOKS GOOD ON THREE OF FOUR INSTANCES.  That reading is wrong,
and the queue contains its own refutation: on prob_20 and prob_24 the operator reports zero gain
on every one of 32 worker-rounds, so a -0.68% and a -1.97% mean were produced by an operator that
demonstrably did nothing.  Those are draws.  The per-worker statistic agrees -- P = 0.458 and
0.484, i.e. very slightly the wrong way.

What survives brkcal:

    prob_3    brk works.  Gains on 4 of 12 worker-rounds, P = 0.719 per worker, and both draws
              below both controls against a 0.12% control spread.
    prob_1    brk lifts the median worker 4.7% and does not change the minimum, which is the
              score.  Neutral at best; r3 says it can cost 18% when it eats the restarts.
    prob_16   nothing to find (0 of 46), and it was excluded from this queue because its controls
    prob_24   span 2,519,071-3,030,292 and every arm of the previous queue reversed sign.
    prob_20   nothing to find (0 of 24, 0 of 48).

CONSEQUENCE.  One instance of five is a win.  Unconditional brk -- what zip D ships -- is not
supported, and I recommended it on a -6.52% that this queue shows was a draw.
