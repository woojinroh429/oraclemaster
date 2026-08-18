# WORKER COUNT IS THE FIRST LEVER TONIGHT WHOSE ARMS DO NOT OVERLAP

    prob_1, local 120 s, five draws per arm

    arm    draws                                                   mean      worst     span
    w8    671,556  669,301                                        670,429      --       --
    w6    701,633  653,806                                        677,720      --       --
    w4    584,609  594,521  660,870  584,609  584,609             601,826   660,870   13.0%
    w3    537,403  467,527  500,196  518,803  518,803             508,546   537,403   14.9%
    w2    515,188  458,512  485,018  458,512  458,512             475,148   515,188   12.4%

    w3 vs w4   mean -15.5%   worst -18.7%
    w2 vs w4   mean -21.0%   worst -22.0%

Fifteen draws separate w4 from both low-worker arms with no overlap at all: w4's best draw
(584,609) is worse than w3's worst (537,403).  Every other arm tonight -- twelve of them -- had
distributions that overlapped, which is why their signs kept flipping across replicates.

## THE SPAN DID NOT MOVE, AND THAT IS FINE

w3's span is 14.9% against w4's 13.0%; w2's is 12.4%.  Reducing worker count does NOT tighten the
run-to-run spread, contradicting the prediction written here earlier that a min over two draws
would be strictly noisier -- it is not, but it is not quieter either.

What moves is the whole distribution.  The worst draw falls 18.7% (w3) and 22.0% (w2), and on a
per-instance score it is the worst run that sets the tier.  Lowering the floor achieves the goal
by a different route than narrowing the band.

## THE RESULT IS STILL CONFOUNDED, AND prob_16 IS THE TEST

Worker `wid` opens on `_AXES[(wid + 1) % 6]`, so worker count decides which axes run at all:

    w4    axes 1, 2, 3, 4
    w3    axes 1, 2, 3
    w2    axes 1, 2

prob_1's axis ranking from tonight's deterministic sweep is axis 2 (686,238) < axis 3 (823,207)
< axis 1 (1,323,041) < axis 4 (1,487,811).  Dropping to w2 discards prob_1's WORST axis, so the
gain may be axis selection rather than cores per worker -- two explanations with opposite reach:

    cores    applies to every instance, adopt globally
    axes     applies to prob_1 only, and reverses wherever the axis ranking differs

prob_16 ranks its axes differently and is queued next.  If w2 wins there too it is cores; if it
loses it is the axis mix, and nothing here generalizes.

## prob_16 SPLITS THE TWO ARMS: w3 IS THE VARIANCE KILLER, w2 IS A GAMBLER

    prob_16, local 120 s, four draws per arm

    w4    3,199,896  3,558,783  3,199,896  3,558,783     span 11.2%   worst 3,558,783
    w3    3,199,896  3,199,896  3,199,896  3,199,896     span  0.0%   worst 3,199,896
    w2    3,251,561  2,926,166  3,495,836  2,828,835     span 23.5%   worst 3,495,836

w4 leaks to its bad attractor on half its draws.  w3 landed the good one four times out of four
and never beat it -- it does not find a better solution here, it removes the bad one.  w2 is
bimodal: it set the two best values ever recorded for this instance (2,828,835 and 2,926,166,
against a previous best of 3,199,896 over 24 runs) and also drew the worst of the three arms.

    w3 vs w4 over nine pairs across both instances    7 wins, 2 ties, 0 losses

w2's mean looks better on prob_1 and worse on prob_16, and its span is the widest of the three on
prob_16.  A per-instance score is set by the run that actually happens, so an arm that sometimes
sets a record and sometimes loses to the control is the wrong trade.  w3 is the candidate.

## BUT EVERY ONE OF THOSE NINE PAIRS IS AT 120 s, AND THIS FILE RECORDS WHAT THAT IS WORTH

From the reserve-fraction comment in myalgorithm.py, a change measured on this same instance:

    240 s   old 501,758  ->  422,629   -15.8%
     60 s   old 636,140  ->  774,699   +21.8%

A 15.8% win at the long budget was a 21.8% loss at the short one.  The hidden set gives its early
instances 60-120 s and its late ones ~500 s, so 120 s alone validates nothing that is scored.

w3's mechanism is depth -- 1.33 cores per worker instead of 1.00 -- and depth only pays if the
deeper search completes inside the budget.  At 60 s it may not, and then w3 is just a draw thrown
away.  harness/nwbud.sh runs 60 s first for that reason.  NOT SHIPPING UNTIL IT HOLDS.

## THE BUDGET CHECK PAID FOR ITSELF: THE 120 s WIN DOES NOT SURVIVE TO 240 s

    w3 vs w4, mean per cell

              prob_1              prob_16

     60 s      -0.85%  (3 pairs)   -10.1%  (3 pairs)
    120 s     -15.5%   (5 pairs)    -5.0%  (4 pairs)
    240 s      +3.6%   (1 pair)     +5.2%  (1 pair)

Both instances cross to w4 at 240 s, with matching sign.  The mechanism accounts for it: w3's
gain is depth bought with cores, and at 240 s a four-way split already has time to reach the deep
solutions, so the extra cores buy nothing and the lost draw is a straight cost.  At 60 s nobody
gets deep and the arms tie.  The win lives in the middle.

    240 s prob_1 w4    422,629    the value the reserve note records as needing three knobs
    240 s prob_16 w4 2,740,666    a new best for the instance, 3.1% under w2's 120 s record

Both controls drew well at 240 s, which is the point: given time, w4 gets there by itself.

## SO GLOBAL ADOPTION IS OUT, AND ONLY A BUDGET GATE REMAINS

The hidden set runs its late instances at ~500 s and they carry the score.  A 240 s trend already
favouring w4 cannot be extrapolated past it, so shipping WORKERS=3 unconditionally would trade a
measured mid-budget gain for an unmeasured long-budget loss on the instances that matter most.

    timelimit <~ 150 s   ->  3 workers
    timelimit  >  150 s   ->  4 workers, unchanged

UNLIKE EVERY GATE THAT FAILED TONIGHT, THIS ONE READS AN ARGUMENT.  brk needed to predict which
instance would benefit and no feature predicted it; the axis gate needed the same.  `timelimit` is
passed into algorithm() directly -- there is nothing to infer.

WHAT IS STILL MISSING IS THE CROSSOVER.  -15.5% at 120 s and +3.6% at 240 s bracket it, but the
gate needs a number, and 150 is a guess sitting between two measured points.  180 s is queued.

## SETTLED, AND SHIPPED: THREE WORKERS ON FOUR CORES

The 240 s "reversal" written above was one lucky control draw.  Filling the cell to five pairs
removed it, and the same thing had already happened at 60 s.  Twice tonight a single pair was
read as a result and twice the next pair overturned it -- the same error the twelve failed arms
were built on.  Final table, 23 pairs:

    cell            w4 mean     w3 mean    mean  |  w4 worst   w3 worst   worst  | span w4->w3
    prob_1   60 s    736,689     730,442  -0.85% |   806,160    788,145   -2.2%  | 20.0 -> 12.4
    prob_1  120 s    601,844     508,546 -15.50% |   660,870    537,403  -18.7%  | 13.0 -> 14.9
    prob_1  240 s    460,000     440,445  -4.25% |   564,221    469,427  -16.8%  | 33.5 ->  9.5
    prob_16  60 s  3,632,782   3,379,142  -6.98% | 3,848,784  3,379,142  -12.2%  | 13.9 ->  0.0
    prob_16 120 s  3,379,340   3,199,896  -5.31% | 3,558,783  3,199,896  -10.1%  | 11.2 ->  0.0
    prob_16 240 s  2,816,305   2,843,269  +0.96% | 3,100,804  2,911,676   -6.1%  | 18.9 ->  6.4

    mean better  5/6 cells, -5.32% overall
    WORST better 6/6 cells, -11.02% overall   <- no exception, including the cell the mean loses
    span tighter 5/6 cells

No budget gate is needed: nothing has to be predicted, because there is no cell where w4 is
ahead on the quantity that sets the tier.  That is what separates this from brk and from the
axis gate, both of which died needing a feature that would say in advance which instance
benefits.

    myalgorithm.py   nw = cpu - 1 when cpu >= 4, unchanged below that.  WORKERS=4 restores the
                     previous behaviour byte for byte.
    submit_build/submit_recon.zip   rebuilt, 8 files, verified from the zip contents: the
                     unpacked package runs n=3 and returns feas=y.

WHAT THIS DOES NOT ESTABLISH.  Two stage-2 instances, three budgets, one four-core box.  The
hidden set runs P1-P6 at up to ~500 s and none of them were measured -- 240 s is the longest
budget any of this covers.  The mechanism (a fifth runnable process on four cores) does not
depend on the instance, which is the reason for shipping it, but that is an argument and not a
measurement.

## THE 480 s CHECK BREAKS THE CLAIM THE SHIP WAS BUILT ON, IN ONE CELL

nw480.sh was queued to close the gap the ship note names: the hidden set runs its expensive
instances at ~500 s and nothing here went past 240 s.  Three pairs on prob_1:

    480 s        r1        r2        r3       mean    span    worst
    w4      442,451   405,381   426,604    424,812    9.1%  442,451
    w3      392,626   402,890   456,249    417,255   16.2%  456,249
             -11.26%    -0.61%    +6.95%     -1.78%          +3.12%

r1 was a new best for the instance at any budget (392,626) and was reported as w4 stalling where
w3 kept descending.  r2 held.  r3 undid the part that mattered: w3's WORST draw is now 3.1% above
w4's worst, and its span is the wider of the two.

THE SHIP NOTE SAYS "the worst draw improves in all six cells" AND THAT IS NO LONGER UNIVERSAL.
Eight cells now exist and seven of them still improve, by 2.2% to 18.7%, against one that
degrades by 3.1%.  The mean at 480 s is still -1.78%.  The change is not being reverted on a
three-pair cell -- reverting would rest on exactly the evidence quality that produced the error --
but the cell is being filled to five pairs, because 480 s is where the points are.

This is the fifth time tonight a two-draw read was overturned by the third draw.  The pattern is
not that the arms are bad, it is that two draws never settled anything at any point in this
session, and every claim written at n=2 has had to be withdrawn.

## FINAL: GATED AT timelimit <= 240 s, AND THE GATE IS ABOUT THE SPAN

37 pairs, eight cells, two instances, four budgets, one four-core box:

    cell             n      mean     worst   w4 span   w3 span
    prob_1    60s    3    -0.85%    -2.23%     20.0%     12.4%
    prob_1   120s    5   -15.50%   -18.68%     13.0%     14.9%
    prob_1   240s    5    -4.25%   -16.80%     33.5%      9.5%
    prob_1   480s    5    -2.36%    -0.49%     13.1%     16.2%
    prob_16   60s    3    -6.98%   -12.20%     13.9%      0.0%
    prob_16  120s    4    -5.31%   -10.08%     11.2%      0.0%
    prob_16  240s    3    +0.96%    -6.10%     18.9%      6.4%
    prob_16  480s    5    +1.61%    +8.62%     10.6%     29.8%

    <= 240 s   6 cells   mean 5/6   worst 6/6   SPAN 5/6   avg mean -5.32%  avg worst -11.02%
     > 240 s   2 cells   mean 1/2   worst 1/2   SPAN 0/2   avg mean -0.38%  avg worst  +4.06%

Above the boundary the mean is a wash and the span advantage is gone completely.  Narrowing the
band is the entire reason this arm was adopted, so the gate is cut where that reason stops.  The
earlier draft of this note put the case on the worst draw instead; the final prob_1 480 s pairs
moved that column from 0/2 to 1/2 and the span column did not move at all.  The span is the claim.

WHY THE LONG BUDGETS BEHAVE DIFFERENTLY, from the worker traces: round-0 worker-to-worker spread
is 53.4% at 480 s (three workers) and 59.6% at 300 s (four workers).  When the workers land that
far apart, which ones you have decides the answer, so dropping one draw costs real objective.  At
60-240 s they finish closer together and the extra core per worker dominates.

    myalgorithm.py   nw = cpu - 1 when cpu >= 4 AND timelimit <= 240; otherwise unchanged.
                     WORKERS=n overrides; WORKERS=4 restores the previous behaviour byte for byte.
    submit_recon.zip rebuilt and verified FROM THE ZIP'S OWN CONTENTS:
                       60 s -> WSTAT n=3, feas=y      300 s -> WSTAT n=4

STILL NOT ESTABLISHED.  Two stage-2 instances on one four-core box.  The gate boundary is the last
budget where the cells agree, not a located crossover -- nothing between 240 and 480 was run.  The
hidden P1-P6 were never measured at all; the mechanism (a fifth runnable process on four cores)
is instance-independent, but that is an argument, not a measurement.

## THE 37 PAIRS WERE MEASURED ON INSTANCES THAT STAND IN FOR NOTHING

HIDDEN_SET.md carries the real ladder, and its analogue table is keyed to data/train.  The shapes
confirm it exactly; every queue above used data/stage2, where the same file names mean other
instances:

    hidden shape          data/train             data/stage2 (what was actually measured)
    P1  60 s  3b 100blk   prob_2  (100, 3)       prob_1  = 150 blk, 3 bays  -> P4's shape
    P2 120 s  2b 150blk   prob_8  (150, 2)       prob_16 = 300 blk, 5 bays  -> nothing
    P3 240 s  3b 200blk   prob_9  (200, 3)
    P4 480 s  3b 150blk   prob_26 (150, 3)       the hidden set stops at 4 bays and 250 blocks,
    P5 600 s  4b 200blk   prob_10/11/12          so a 5-bay 300-block instance matches no hidden
    P6 900 s  3b 250blk   prob_37/38/39          problem at all

So of the two instances behind every number in this file, one carries P4's shape and the other
carries none.  The budgets were chosen correctly; the shapes were never checked.

TWO THINGS SURVIVE THAT.  First, the gate boundary is right by luck: 240 s is P3's limit and 480 s
is P4's, so the untested 240-480 interval contains no scored instance.  Second, stage-2 prob_1 IS
P4's shape, and at P4's budget of 480 s it measured mean -2.36% with a WIDER span -- which is the
side of the gate that turns the change OFF.  The one accidental shape match agrees with the gate.

WHAT DOES NOT SURVIVE is the claim that the gate-ON budgets were validated.  Bay count and block
count are what a worker's search depth interacts with; an effect measured at the right budget on
the wrong shape transfers by assumption only.  harness/nwreal.sh re-runs the ladder properly --
prob_2 at 60 s, prob_8 at 120 s, prob_9 at 240 s, prob_26 at 480 s, all from data/train.

## ON THE INSTANCES THAT ARE ACTUALLY SCORED, THE SHIPPED GATE DOES NOTHING

Re-run on data/train at each hidden problem's own budget:

    P1   60 s  train/prob_2   100 blk 3 bays   6/6 identical   3,690     spent 60% of budget
    P2  120 s  train/prob_8   150 blk 2 bays   6/6 identical  11,252     spent 64%
    P3  240 s  train/prob_9   200 blk 3 bays   2/2 identical  50,485     spent 98%

Byte-identical: same objective, same Z1, Z2, Z3 under three workers and under four.  P3 is the
one that settles it -- it is starved, 236 s of 240, and starvation is the only condition under
which extra cores per worker can buy anything.  It bought nothing.

The gate fires only at timelimit <= 240, so P4, P5 and P6 are byte-identical to the previous
submission by construction.  THE SHIPPED CHANGE CANNOT MOVE ANY SCORED PROBLEM.  It is harmless
and it is worthless, and both halves of that need saying: nothing has to be reverted, and nothing
was gained.

## AND THE SPREAD THIS WHOLE NIGHT WAS SPENT ON MAY NOT EXIST WHERE IT COUNTS

Every hidden analogue measured so far has a run-to-run spread of exactly zero.  The 11-33% spread
that defeated thirteen arms tonight was measured on stage-2 prob_1 and prob_16 -- one of which
carries P4's shape, the other nothing at all, being 5 bays and 300 blocks against a hidden
maximum of 4 and 250.

If P5 and P6 behave like P1-P3, the variance being chased is a property of two unrepresentative
instances, and no variance-reduction arm could ever have paid on the hidden set.  That would
explain the entire night's yield in one sentence.  If they DO vary, it is the first honest
sighting of the reported problem, at the budgets carrying three orders of magnitude more score
than P1-P3 combined.  harness/nwfin.sh measures exactly that: prob_10 at 600 s, prob_37 at 900 s,
w4 only, three draws each -- w4 being what will actually run there.

P4 was cancelled: 96 minutes to characterise a cell where the gate is off and no decision hangs
on the answer.
