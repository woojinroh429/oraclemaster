# WHICH OPERATORS PAY, MEASURED ON SIXTEEN INSTANCES

`OGC_OPSTAT=1`, 60 s, four workers, `OGC_DIRGATE=0` so this is the stock pipeline.  Gains are
summed over the four workers.  `pref` is `_z3_improve`, `bay` is `_assign`, `grow` is `_regrow`.

    inst   peak_util  blocks | calls |   pref gain     /s   | zero-gain / polish sec
    P22      0.68     150   |   30  |       16669    604  |    0.0 / 100.2    0%
    P34      0.98     300   |   28  |       84562   4888  |    0.0 / 108.9    0%
    P1       1.02     150   |   28  |      574101  20726  |    0.0 / 100.4    0%
    P27      1.13     200   |   23  |      824607  36487  |    2.9 /  84.0    3%
    P16      1.23     300   |   18  |      236944  12808  |   77.3 /  95.8   81%
    P7       1.27     150   |   24  |      125657   5536  |    0.2 / 101.6    0%
    P4       1.35     250   |   16  |      699933  54682  |    0.4 /  98.1    0%
    P9       1.44     200   |   24  |      874532  35406  |   21.3 /  97.6   22%
    P30      1.58     300   |   21  |       29687   1571  |    0.0 /  92.2    0%
    P20      1.75     250   |   18  |       65273   4352  |   37.2 / 103.7   36%
    P8       1.90     200   |   25  |       19184    830  |    0.0 / 113.8    0%
    P6       2.05     250   |   17  |       64334   4911  |    0.0 /  86.1    0%
    P26      2.22     300   |   18  |      830001  46629  |   65.7 /  83.5   79%
    P2       3.29     250   |    4  |           0      0  |    0.0 /  76.7    0%
    P36      4.66     300   |    5  |      391028  79802  |   29.0 /  33.9   86%
    P25      6.26     300   |    0  |           0      0  |    0.0 /   0.0    0%

    zero-gain polish seconds: 234 of 1376 (17%)

## 1.  The polish is NOT inert.  That claim was instance-local and is corrected here.

`results/audit/improvers_are_inert.md` recorded `_z3_improve`, `_z1_improve` and `_assign`
returning their input, measured on stage2/prob_1.  Across sixteen instances `pref` books 16,669 to
874,532 -- on P27 and P26 the same order as the whole objective.  What is true is narrower: those
passes return their input **on the solutions and instances that were sampled there**, not in
general.

## 2.  Nothing predicts the payoff.

pref gain per second, ordered by peak_util: 604, 4888, 20726, 36487, 12808, 5536, 54682, 35406,
1571, 4352, 830, 4911, 46629, 0, 79802.  No monotone relation, and none against block count, bay
count or Z3 share either.  Two mechanisms were proposed from partial data during the run and both
were refuted by the next instance:

  - "the polish works inside DIRGATE's band and idles outside" -- refuted by P4 at 1.35, outside
    the band and a measured LOSER of the DIRGATE configuration, which booked the second-largest
    gain of the set;
  - "the polish does almost nothing anywhere" -- an artefact of dividing by `beam`'s gain, which
    measures nothing-to-a-solution and is not a denominator.

This is the third time this project has failed to find an instance feature that says in advance
where an operator pays; `brk`'s own gate died the same way.  **So DIRGATE remains empirically
justified and mechanically unexplained.**

## 3.  Time allocation is already adaptive, and mostly right.

The roster selects on measured return and grows the winner's slot:

    k = max(elig, key=lambda i: gain[i] / spent[i])
    slot[k] = min(budget * 0.45, slot[k] * 1.5)

Overall waste is 17% of polish seconds, not the 80% a "each operator burns 20% of budget to prove
itself" reading of `slot = budget * 0.20` would suggest.  `slot` is a ceiling, operators usually
do not spend it, and losers are dropped quickly.  Ten of sixteen instances waste nothing at all.

## 4.  The waste that does exist tracks CALL COUNT, which tracks size.

    <=200 blocks   n=6    median 24 calls   waste  4%
    >200 blocks    n=10   median 18 calls   waste 27%

The adaptive rule needs samples.  At 60 s a 300-block instance gives each worker four or five
operator invocations -- P2 gives four in total and `pref` books zero, P36 gives five, and P25 -- 300 blocks at
peak_util 6.26 -- gives ZERO: the polish never runs at all there, so its 60 s is entirely
construction -- so an
operator that will never pay can consume several large slots before the rule can rank it.

Unlike peak_util this is a legitimate conditioner: block count is known before the solve and the
mechanism is explicit (fewer calls -> less evidence -> slower elimination).

**BUT IT IS NOT MEASURED AND THE WITHIN-GROUP SPREAD IS ENORMOUS.**  Inside `>200 blocks`: P34 0%,
P30 0%, P16 81%, P26 79%.  Ten points with that spread do not establish the relation, and the
median call counts differ by only 24 against 18.  Shrinking the initial slot on large instances is
a reasonable next experiment; it is not a finding.

## What this closes and what it leaves

Closed: gating the polish on an instance property, and any hope that the roster is misallocating
time in a way a constant would fix.

Left: the call-count hypothesis above, and the fact that a good instance-level explanation for
DIRGATE still does not exist -- which is the honest limit on claiming it generalises to the hidden
set.
