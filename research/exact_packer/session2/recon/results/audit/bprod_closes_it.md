# THE MEASUREMENT GAP I DIAGNOSED DOES NOT EXIST, AND THAT DECIDES bk67

## 1. `_beam_once` IS deterministic under OGC_WORKCAP

    p1.ax0.w3000  rep=0  obj=1,174,681  digest=38cfdfb2850e4afa
    p1.ax0.w3000  rep=1  obj=1,174,681  digest=38cfdfb2850e4afa
    p1.ax0.w3000  rep=2  obj=1,174,681  digest=38cfdfb2850e4afa

The worry was that `_beam_once` splits its budget by reading `budget` in SECONDS, so the work cap
might not reach the split.  Three repeats, identical placement.  The production seed generator is
measurable without noise.

## 2. AND IT RETURNS EXACTLY WHAT beam1 RETURNS

    axis      beam1 (_contact_beam, step=1)     beamprod (_beam_once)
    0                   1,174,681                    1,174,681
    1                   1,323,041                    1,323,041
    2                     684,687                      684,687
    3                     737,578                      737,578
    4                   1,403,609                    1,403,609
    5                   1,350,271                    1,350,271

All six identical.  The two-rung structure COLLAPSES to the fine rung: step 1 succeeds, the
function returns, and the step-2 reserve is never used on this instance.

I diagnosed the beam1/production difference as a measurement gap, wrote beam1_gap.md around it,
and used it to argue that the deterministic axis table "ranks a search production never runs".
That was wrong.  It runs exactly that search.  Withdrawn.

## 3. WHICH SETTLES WHAT bk67's FAILURE MEANS

Two readings were open:

    (a) 0.7/5 improves production's seed and the score is insensitive to seed quality
    (b) 0.7/5 does not improve production's seed, so bk67 never tested (a)

(b) is dead.  Production's seed generator IS the fine rung, and on it axis 2 (Bmul 0.7, K 5)
returns 684,687 against axis 0's 1,174,681 -- 1.7x, at the work level production actually uses.
bk67 gave every axis that setting, so it did improve the seed.

(a) stands.  Seven pairs, mean +1.50%, signs split on all three instances, and prob_20 r2
identical to the digit in both arms.

    A 1.7x to 2.6x improvement in seed quality produces no readable change in the score.

## 4. AND IT CONFIRMS THE 40%

If step 1 always succeeds on prob_1 -- which is what "identical to beam1 on all six axes" means --
then the step-2 reserve is never consumed, and the 40% of the slice it holds is unreachable by
anything.  That is not an inference from reading the loop any more; it is what the measurement
shows.  OGC_FINEFRAC is the only arm tonight aimed at compute no consumer can currently reach.
