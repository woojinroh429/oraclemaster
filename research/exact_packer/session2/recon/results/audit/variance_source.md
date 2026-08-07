# Run-to-run variance is a property of the INSTANCE, not of the clock-driven controllers

The premise this session worked from: every RNG in myalgorithm.py is constant-seeded
(Random(1234+wid), Random(20260731), Random(90001+7919*wid)), so two runs of one build on one
instance at one budget differ in exactly one input -- time.time() -- and the controllers that read
it (the per-level beam width, adaptive K, operator selection by gain/seconds) amplify that jitter
into different answers.

Measured directly, by repeating the identical configuration inside one queue:

    inst  arm      rep1         rep2        run-to-run
    P24   adapt    2,809,182    2,809,182     0.00%
    P24   pinned   2,631,837    2,631,837     0.00%
    P24   det      2,631,837    2,565,882     2.57%
    P16   adapt    3,271,186    3,612,529    10.40%
    P16   pinned   2,795,643    3,574,878    27.90%

Two things follow and both contradict what was expected.

## The controllers are not the explanation

prob_24 reproduces TO THE DIGIT with the adaptive width fully live -- the same controller that
recomputes Bcur from elapsed()/work at every one of ~250 levels.  If wall-clock jitter drove the
answer, that could not happen.

And pinning the width (OGC_ADAPTB=0) did not reduce the variance where there is any: prob_16 went
from 10.4% to 27.9%.  The arm built to remove the amplifier is the least reproducible one.

## OGC_DET was not deterministic

det is the only arm that moves on prob_24, and the reason is in its own implementation: it charges
each operator the slice it was GIVEN, `_ask = max(1.0, min(left - 1.0, slot[k]))`, and `left` is
`budget - elapsed`.  The "deterministic" accounting reads the clock through `left` and then
accumulates it into `spent`, which drives selection.  It moved the clock dependence rather than
removing it.

## What actually varies

The same code reproduces exactly on one instance and swings 10-28% on another, in the same queue,
minutes apart.  The difference is the instance's own landscape.  prob_16's recorded 240 s draws sit
on at least eight distinct attractors (2,795,643 / 3,043,376 / 3,262,325 / 3,271,186 / 3,281,165 /
3,286,759 / 3,574,878 / 3,612,529 / 3,813,686), several of them repeating exactly across unrelated
configurations.  prob_24 appears to have one basin wide enough that timing never pushes a run out
of it.

So the variance is sensitivity, not noise injection: how close the search path runs to a boundary
between attractors on THAT instance.  Removing a clock-driven controller does not change where the
boundaries are.

## What this rules out

Chasing determinism.  Two arms were built for it (OGC_ADAPTB=0, OGC_DET) and neither reduced the
spread; one increased it.  The remaining clock reads are stops -- the budget is real time and they
have to be there.

## What it leaves

Monotonicity instead of determinism.  Nothing forces obj(240s) <= obj(60s): a long run does not
start from what a short run found, and it is not even the same search, since the beam width is
derived from the budget.  prob_16 reaches 2.79M at 60 s and reached it once in ten 240 s draws.
A beam that ran a narrow configuration first, kept it, and only replaced it when a wider one beat
it would make the curve non-increasing by construction, for the cost of one cheap beam.

That is the same shape as beam salvage -- the one change on this project that clearly worked --
which was "finish the partial instead of discarding it".  This is "compare instead of discarding".
