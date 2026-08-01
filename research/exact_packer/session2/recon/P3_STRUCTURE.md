# P3, taken apart

Everything here is measured on the real hidden `prob_3.json`. Retractions are kept in place
rather than deleted, because the wrong version of each was acted on for a while and the reason
it was wrong is the useful part.

## The instance

    200 blocks, 3 bays, 240 s, w1 = 17778, w2 = 5, w3 = 150
    demand ratio 0.327 -- the yard is a third full

    bay   size      cells   u = (mean area)/(own area)
      0   43 x 23     989   2.078
      1   89 x 28    2492   0.825
      2  122 x 22    2684   0.766

    horizon 82 (releases 0..70, dues 5..82)
    blocks whose FIRST choice is bay j:  {0: 77, 1: 60, 2: 63}
    first -> second preference gap: min 0, median 47, mean 46.7, max 100

Z1 is 0 in every solution anything has produced, and stays 0: every block has slack. So the
objective is `5*Z2 + 150*Z3` and **is a function of the bay assignment alone**. Positions,
orientations and entry times appear nowhere in it — they matter only through what they make
feasible.

Bay 0 is the smallest and carries the largest `u`, so it always sets Z2's maximum, and 77 of
200 blocks want it first. Z3 pulls blocks into bay 0 and Z2 pushes them out, over the same bay.
That single tension is the whole instance.

## What every configuration produced

Twenty-odd runs across every knob land on a handful of discrete solutions:

    obj      Z2     Z3    produced by
    87,560   3652   462   conw=0.0 (3 of 4 runs), mum=* (3), pf=0.5 r2
    91,110   2952   509   span2=1.0 (2 of 3)
    92,930   3496   503   conw=0.25 (3 of 3), div conw+span2 (2 of 3)
    94,965   2343   555   span2=1.0 r3
    92,930   3496   503   per-worker conw 0/.25/1/4 (the conw=0.25 solution again)
    96,235   3767   516   per-axis conw diversification (2 of 3)
    96,990   3108   543   base
   100,535   3187   564   per-worker conw, 2 of 4 workers flat
   106,335   4257   567   per-worker conw, 3 of 4 workers flat
   103,795   3419   578   conw=0.0 AND span2=1.0 together (2 of 2)
   106,700   2680   622   base, bad end of its band
   106,940   2518   629   conw=0.0 r2

Z2 and Z3 move in opposite directions down that list, exactly as the bay-0 tension predicts.
The best solutions are the ones that took the trade furthest.

Two things follow that are worth more than the individual numbers:

* **conw and span2 are one mechanism, not two.** Both flatten the packing. Held together the
  result is 103,795 — worse than either alone.
* **conw=0.0 is a REGIME, not a candidate score, and the regime needs the whole pool.** Per-axis
  diversification put conw=0.0 on two of six axes and returned 96,235, level with the base. If
  one flat beam could produce 87,560, best-of over the true objective would have returned it. It
  did not: a beam builds a flat layout and any axis at conw=1.0 repairs it back toward contact
  packing. Axes rotate within a worker by design, so they cannot hold a regime steady — but
  workers can, each keeping its own pool for the entire budget and meeting only at the closing
  best-of. Splitting by worker fails too (100,535 at two of four, 106,335 at three of four), and
  workers were the last unit available. **There is no way to make conw=0.0 safe for a saturated
  instance by splitting it**, so the knob is closed rather than merely unproven.

**Every direction that WEAKENED contact was a dead end** — conw as a constant, span2 (the same
mechanism), per-axis, per-worker. The 17.75% came from re-solving the arrangement with contact
left at full strength, taking nothing away. That is worth stating plainly because the whole
night was spent on the other hypothesis.

## Why a less-full bay takes more blocks

The crane rule: a landing block's layer `k` is refused by anything resting at layer `j >= k` in
the same column. So at a cell of stack height `h`, the layer indices still usable are `k >= h`.
**Occupancy is not the resource; height is.** A one-layer resident is nearly free ground for an
overhang; a four-layer one sterilises its cells against every layer of everything.

That is the common case here, not an edge case:

    layers per (block, orientation):  1:32   2:476   3:552   4:528
    orientations whose upper layers overhang their own layer 0:  1,352 of 1,588  (85%)

And it explains conw. A block always lands on cells that are completely free, so the total
sterilised volume it creates is the same wherever it goes — position changes *where* height is
added, never *how much*. What contact gets wrong is not that it packs tightly, but that it is
indifferent about **whom** it packs against: a four-layer block pressed against a one-layer
block scores exactly as well as against another four-layer one, and leaves a height cliff where
a broad low plateau could have been. Overhangs need the plateau. `conw=0.0` fixes this by
abandoning tightness outright, which is precisely why it is the best P3 setting measured and
the worst P4 one (+25.9%).

`hmatch` in `ogc_fast.cpp` charges the mean `|my height - neighbour's height|` over the boundary
cells that touch something. The block still wants to nestle; it only picks a neighbour of its
own height.

## How much room is actually there

`harness/p3bound.py`, a capacity-aware lower bound. Assign blocks to bays minimising
`w2*Z2 + w3*Z3` subject to each bay's `cells x horizon` covering the `area x time` it holds.
Both sides relax safely — capacity over-estimates (no crane rule, perfect tiling), demand
under-estimates (true polygon area, minimised over orientations) — so its optimum is a valid
lower bound on the real objective.

    bay 0 first-choice demand / capacity   0.48
    bay 1                                  0.12
    bay 2                                  0.15
    proven lower bound                     36,765   (Z2 6633, Z3 24)
    our best                               87,560   (+138%)

**Area is not binding.** Neither 80,000 nor 70,000 is excluded by it. The bound assumed 100%
packing and bay 0 runs at 54% peak area occupancy, so the entire 138% gap is packing efficiency
under the crane rule.

> RETRACTED: an earlier estimate of mine put bay 0's ratio at 1.11 and concluded that ~8 blocks
> must structurally leave bay 0. It used bounding-box area maximised over orientations, which
> over-states demand on both counts. The correct figure is 0.48 and nothing is forced out.

## What cannot fix it

* **Single-block eviction from bay 0** — proven exhausted. Break-even needs `gap/workload <
  0.0948`; the cheapest resident is 0.145. Every single move loses, which is why `_balance`,
  the only Z2/Z3 repair operator, is structurally dead here.
* **Pairwise swap** — 98 improving exchanges exist, worth −26.98% priced exactly, and 0 of 7
  are seatable as pairs against the incumbent arrangement.
* **Re-timing** — of the 25 most valuable would-be entrants to bay 0, 2 fit at their own entry
  time, 0 fit at some other tardiness-free time, and 23 fit nowhere in their window.
* **prefw** — structurally dead. It enters the per-cell score, where the bay penalty is
  constant and cannot change which cell wins, and the per-bay `drank`, which is sorted and then
  truncated to top-K with K >= the bay count on every instance. 0.0, 2.0 and 8.0 returned
  byte-identical objectives.

Every one of those tests holds bay 0's residents at the positions the pipeline gave them. A
block that does not fit around one arrangement has been told nothing about a different one —
which is what `harness/p3bay0.py` and the `bayrepack` operator exist to ask.

## Throughput, and why it is also a variance question

`_total` is the file's only selection criterion, so it runs once per operator invocation. It
calls `check_feasibility`, which does two jobs: it re-derives `w1*Z1 + w2*Z2 + w3*Z3`, which is
arithmetic over (bay, entry, exit), and it re-validates every crane path, which is polygon work.

    check_feasibility      173 ms
    the arithmetic alone   0.13 ms      -- and equal to the grader's number to the last digit

Every random draw in the worker loop is seeded, so what differs between two runs of one arm is
how many operator calls fit in the budget. That is where the spread comes from, and verification
is a large, noisy share of it — so removing it narrows the band as well as raising the ceiling.
`OGC_FASTOBJ` screens on the arithmetic objective and verifies for real only what could beat the
incumbent.

## The one thing that worked

`bayrepack` -- lift every block out of the most-pressed bay that something wants to enter, add
the outsiders that would most improve the objective, and let `cranepack` seat maximum VALUE
under the descent rule. Residents are weighted by what evicting them would cost, outsiders by
what admitting them gains, so it trades rather than merely adds. Displaced blocks are rehomed
for real -- each must find a legal seat in another bay at its own unchanged times against the
finished new state -- and a block that cannot kills the repack.

Paired against its own control, same base and same build, three reps against three:

    rep    brk on     brk off     delta
    r1     82,180      96,990    -15.27%
    r2     86,550     106,700    -18.88%
    r3     86,550     106,700    -18.88%
    mean   85,093     103,463    -17.75%

    brk  82,180 - 86,550     width  4,370
    ctl  96,990 - 106,700    width  9,710

> RETRACTED, on more data: **brk does not halve the spread.** A later queue ran the same arm
> twice more and got 90,545 and 88,720, so over five samples the band is 82,180-90,545, width
> 8,365 -- effectively the control's own 9,710. Checked the obvious explanations and neither
> holds: `bayrepack`'s only change in between was the env override, a no-op when `BRK_*` are
> unset, and there was no contention (one run family, load 4.19 on 4 cores). It is variance, and
> three samples were not enough to see it. This matters more than a usual retraction, because
> narrowing the band for a shorter finals budget was one of the reasons to want the operator.

What survives on six samples against three:

    brk   82,180 / 86,550 / 86,550 / 90,545 / 88,720 / 91,670   mean  87,703   width 9,490
    ctl   96,990 / 106,700 / 106,700                            mean 103,463   width 9,710

    -15.2% on the means; bands still disjoint -- brk's worst (91,670) is 6,445 under the
    control's best (96,990); widths effectively equal.

### A caution about where the samples came from

The six brk-only runs split cleanly by queue, with no value in common:

    queue12  82,180 / 86,550 / 86,550    (01:04-01:20)
    queue16  90,545 / 88,720 / 91,670    (02:20-02:45)

`bayrepack` was diffed across the interval and its only change is the env override, a genuine
no-op when `BRK_*` are unset; there was no contention either (one run family, load 4.19 on 4
cores). With n=3 apiece this can be coincidence, but a split that clean is worth recording
rather than explaining away — and it is exactly why every claim here is paired against a control
run in the same queue. queue16's own control was measured alongside its arm, so its verdict
stands regardless of what the level difference turns out to be.

### hmatch on top of brk: suggestive, not established

    rep    brk+hmatch2    brk only      delta
    r1        84,555        90,545      -6.6%
    r2        90,580        88,720      +2.1%
    r3        88,910        91,670      -3.0%
    mean      88,015        90,312      -2.5%

Two pairs of three favour the stack. But one reverses, and 2,297 points sits well inside brk's
own 9,490 run-to-run spread, so this does not carry on its own.

Z3 = 443 on the best run, at Z2 = 3146. Nothing else this session got Z3 under 462, and that
only by paying Z2 up to 3652. Improving both terms at once is exactly what p3max proved no
single move can do, which is why `_balance` -- the only Z2/Z3 repair operator the pipeline had
-- is structurally dead here.

### What it cost to get right

The gain nearly died four times, each time to something that fails silently rather than loudly:

* the operator first REJECTED any repack that could not re-seat every resident -- and the
  winning repack displaces three
* rotating the target bay across calls to avoid re-deriving one answer sent call two to a bay
  with no profitable entrant, which returned None in 0.0 s and cut -15.27% to -2.31%
* a container restart left `ogc_fast.so` older than `mkbase.py`, so every generated arm passed
  one argument too many, pybind raised TypeError into a bare `except`, and four queues reported
  the greedy floor (2,488,352,313) as an ordinary result with `feas=y`
* `BRK_STEP/NOUT/NENT` read as sweepable knobs while the tier table overrode them
  unconditionally, so a sweep would have measured one setting three times

All four are now asserted or reported, and each guard was negative-tested against the failure it
is for. `harness/brksmoke.py` exists because a `None` inside a 240 s arm is indistinguishable
from "the operator found nothing worth doing".

## A note on how this file's numbers were arrived at

Four claims in this session were made on two or three samples and then broken by the next run:

    hmatch "monotone"          3 points   broken by the 4th
    brk "halves the spread"    3 runs     the width matched the control once n grew
    brk "widens the spread"    one arm    the paired control said the opposite
    FASTOBJ "width 1/10"       2 runs     broken by the 3rd

Each was written with a sentence acknowledging the sample was too small, and then asserted
anyway. That acknowledgement is an alibi, not a reservation.

The rule adopted after the fourth: **under three reps, record the numbers and say nothing about
direction.** Where a claim here rests on fewer, it says so and stops.

The one result that has never moved is `brk`, and it is the one measured six runs against
three, paired inside a single queue, with disjoint bands.

## Throughput: measured, and it does nothing

    FASTOBJ  101,935 / 100,935 / 106,700   mean 103,190  width 5,765
    control   96,990 / 106,700 / 106,700   mean 103,463  width 9,710

`_total` costs 173 ms against 0.13 ms for the same number by arithmetic, and it is the file's
only selection criterion, so screening it looked like free throughput. Over three runs it moves
the mean by 273 points -- 0.26% -- and the width claim did not survive either. Whatever governs
the spread on this instance, verification time is not a large part of it.

## The BRKGA line, closed for a new reason

The old reason it was removed -- `st3dtcs.st_best` at 5-7 s per decode, so about two generations
in a 15 s budget -- is genuinely fixed. `ogc_fast.Engine.greedy_rollout` takes `prio`, a float
per block, which is already a BRKGA chromosome, and decodes in **42.7 ms**: 5,625 decodes in a
240 s run single-core, 22,500 across four workers.

Two measurements then closed it again.

**Random keys are the wrong space.** Spearman rho between the cheap decoder's ranking and the
beam's was **+0.220** over twenty chromosomes, under the 0.5 bar set before the data arrived.
And a 10 s beam on a random order returns 136,340 at its best over twenty tries, against 96,990
for the base and 87,703 for brk -- random order space is 55% worse than where we already stand.

**The local gradient is not measurable with this instrument.** `brklocal` perturbed each designed
order by 1-32 adjacent swaps and reported 22 wins in 96, best -9.34%. Then the control:

    the SAME order, six evaluations, nothing changed
    edd        [191128, 165295, 165295, 165295, 165295, 165295]   spread 25,833
    lst        [148650, 148650, 148650, 160775, 157315, 166500]   spread 17,850
    big_first  [188260, 188260, 188260, 166605, 188260, 188260]   spread 21,655
    defer_big  [164970 x 6]                                       spread      0

Every gain brklocal reported is inside that floor.

The shape is explained too. `defer_big` is perfectly deterministic; `edd`'s FIRST call is 191,128
and the next five are 165,295 -- a cold first call getting a narrower adaptive width. `brklocal`
evaluated each seed once, so a cold seed inflates the baseline and everything after it looks
like a win. `defer_big`'s 3-of-4 at ONE swap, its best cell anywhere, is exactly that: seed
175,200 against a repeated 164,970, so 10,230 of that "13,185 improvement" was warm-up.

**Carry this forward:** a single evaluation of a fixed order carries up to 15.6% of noise on this
instance. Nothing may be compared on one beam call.

## The tier rule: what `brk` was actually short of

`harness/brkcost.py` handed the repack operator a range of slices and measured both what it
took and what it bought. Both columns are step functions:

    slice   took   ratio      obj     gain
       8s   20.3s   2.5x   105,430   -1.19%
      12s   18.9s   1.6x   105,430   -1.19%
      20s   21.0s   1.1x   105,430   -1.19%
      35s   77.0s   2.2x    91,670  -14.09%
      60s   78.5s   1.3x    91,670  -14.09%
     100s   81.0s   0.8x    91,670  -14.09%

**Time is set by the problem, not the budget.** Every small-tier call costs ~20 s and every
large-tier call ~78 s whatever it was asked for -- `cranepack` runs its own search to completion
and treats the deadline as advisory. Handing it 100 s instead of 35 buys nothing.

**So is the gain.** -1.19% small, -14.09% large, nothing between and nothing above.

That exposed the bug. The old rule picked a tier from the SLICE, gating the large one at 40 s --
and `brk`'s opening slot is `worker_budget * 0.20`, which is 39.8 s on a 240 s run. Just under.
Deflating by the observed overrun ratio pushed it further under. So the operator spent the whole
session in the -1.19% tier with -14.09% one threshold away, and that is also why handing it the
entire budget changed nothing: a bigger slice still bought the same small problem.

The rule now takes the largest tier whose MEASURED cost fits the RUN's remaining time, with that
remaining time passed in -- a 40 s slice with 190 s left and a 40 s slice with 45 s left want
opposite tiers, and the slice alone cannot tell them apart. Per-tier costs are learned from what
actually happens.

Measured against the rule it replaced, interleaved inside one queue:

    rep    tier NEW    tier OLD    delta
    r1       87,070      88,720    -1.9%
    r2       90,365      94,980    -4.9%
    r3       86,665      97,185   -10.8%
    mean     88,033      93,628    -6.0%

Three pairs, all favouring the new rule. Less than the step function suggested -- repeated
small-tier calls appear to recover some of it inside a run -- but that is an explanation and not
a measurement.

## The ceiling of free repacking, and why 70,000 is not behind it

`harness/p3ceil.py` removed the clock entirely and swept every bay, repacking each freely, until
a full pass improved nothing:

    round  bay      obj       delta    secs
        1    0    92,740     -9,195     202
        1    1        --         --       0
        1    2        --         --     333
        2    0        --         --     136
        2    1        --         --       0
        2    2        --         --     302

    101,935 -> 92,740  (-9.02%), two rounds, 973 s

**The idea is spent, and the operator already beats it.** `brk` inside a 240 s run averages
87,703 -- below the ceiling a patient, unbounded sweep reaches. The pipeline does better because
`brk` is called repeatedly with a rotating seed while other operators change the state between
calls, which explores more than one thread walking the bays in order.

Bay 1 returns instantly every time: nothing wants to enter it, so there is nothing to repack
profitably however loaded it is. Bay 2 spends 333 s and finds nothing.

    lower bound                36,765
    ceiling of free repacking  92,740
    brk in a 240 s run         87,703
    target                     70,000

So the gap between the bound and where we are cannot be closed by repacking. Repacking moves
blocks into a bay by re-solving that bay; it has now done everything it can do. Reaching 70,000
would need the assignment and the packing solved together rather than one after the other, which
is a different program, not a further knob.
