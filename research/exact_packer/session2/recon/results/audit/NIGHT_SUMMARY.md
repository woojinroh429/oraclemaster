# What this night actually established

Thirteen arms measured, one shipped, and the shipped one turns out to be inert on everything that
is scored.  The useful output of the session is not the change; it is the two facts below, which
invalidate the method every one of those thirteen arms was measured with.

## 1. Every measurement was taken on instances that stand in for nothing

`HIDDEN_SET.md` records the hidden set and which training instances match it, keyed to
`data/train`.  The shapes confirm the table exactly:

    hidden problem        data/train             shape
    P1   60 s             prob_2, prob_3         3 bays 100 blocks
    P2  120 s             prob_8                 2 bays 150 blocks
    P3  240 s             prob_9, prob_35        3 bays 200 blocks
    P4  480 s             prob_26                3 bays 150 blocks
    P5  600 s             prob_10, 11, 12        4 bays 200 blocks
    P6  900 s             prob_37, 38, 39        3 bays 250 blocks

Every A/B in this session ran on `data/stage2`, where the same filenames are different instances:

    stage2/prob_1    150 blocks, 3 bays    carries P4's shape, whose budget is 480 s
    stage2/prob_16   300 blocks, 5 bays    the hidden set stops at 4 bays and 250 blocks,
                                           so it stands in for no hidden problem at all

The budgets used (60/120/240/480 s) were chosen sensibly and happen to match the ladder.  The
shapes were never checked.  Bay count and block count are exactly what search depth interacts
with, so an effect measured at the right budget on the wrong shape transfers by assumption only --
and when it was finally tested, it did not transfer.

## 2. The variance being chased does not appear on the instances that are scored

The premise of the night was run-to-run spread: the same input, run twice, giving different
answers, with the worse run setting the tier.  On stage-2 prob_1 and prob_16 that spread is real
and large -- 11% to 33% depending on budget.  On the hidden analogues, at their own budgets:

    P1   60 s   six draws   all 3,690    identical Z1, Z2, Z3
    P2  120 s   six draws   all 11,252   identical
    P3  240 s   two draws   all 50,485   identical, and this one spends 236 s of its 240

Zero spread, including on the one that exhausts its budget.  If P5 and P6 behave the same way
(being measured now at 600 s and 900 s), then no variance-reduction arm could ever have paid on
the hidden set, and thirteen failures need no further explanation.

## What was shipped, and its honest status

`myalgorithm.py`: `nw = cpu - 1` when `cpu >= 4` and `timelimit <= 240`, otherwise unchanged.
`WORKERS=n` overrides; `WORKERS=4` restores the previous behaviour byte for byte.

    on prob_1 / prob_16, 60-240 s     worst draw -11.0% average over 6 cells, span tighter in 5
    on prob_1 / prob_16, 480 s        span advantage gone entirely, hence the gate
    on P1, P2, P3 analogues           byte-identical output, no effect at all
    on P4, P5, P6                     gate is off, byte-identical to the previous submission

So: harmless, and worthless.  Nothing needs reverting.  Nothing was gained.

## The error pattern, recorded because it repeated five times

Five separate claims were written in this session at two or three draws per arm and overturned by
the next draw:

    "60 s reverses the 120 s win"          one pair; three pairs averaged -0.85%
    "240 s reverses it"                    one pair; five pairs averaged -4.25%
    "control spread is 1.3%"               two draws; the third made it 13.0%
    "worst draw improves in all cells"     n=3 cell; n=5 moved it from +3.12% to -0.49%
    "saturation explains where w3 pays"    predicted prob_16 winning at 480 s; it lost

In every case the correction was written promptly, which is the right half of the behaviour.  The
wrong half is that the claim was made at all: at these spreads, two or three draws settle nothing,
and the rule of five pairs before a directional claim was set early and then broken repeatedly
under the pull of an interesting-looking first result.

## What to do first next session

1. Finish P5 (600 s) and P6 (900 s) spread measurements -- `harness/nwfin.sh`, w4 only.
2. If their spread is zero, stop building variance-reduction arms.  The remaining lever is raw
   objective on P5/P6, which are three orders of magnitude above P1-P3 in score
   (10,128,108 and 32,366,596 against 11,280 / 31,368 / 93,395).
3. Any future A/B: `data/train`, the analogue for the hidden problem being targeted, at that
   problem's own budget, five pairs minimum before any directional claim.
