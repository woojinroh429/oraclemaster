# WHAT stage2/prob_1 ACTUALLY IS, FROM THE INSTANCE RATHER THAN FROM A KNOB

    150 blocks, 3 bays, w1 = 6667, w2 = 3, w3 = 600
    bays 91x21 = 1911, 32x23 = 736, 37x17 = 629      total 3276
    horizon: max due 73, max release+pt 65

Eighteen knob sweeps this session read as noise.  This is the instance instead.

## 1.  Z1's floor is ZERO

    blocks with release + processing_time > due_date : 0 of 150

No block is intrinsically late.  Every tardiness unit we pay is a packing failure, and at 6,667
each a run at Z1 = 54 has burned 360,018 before Z3 is counted.

## 2.  Z2 is worth 1.28 displaced blocks and can be ignored

    Z2 = range of workload x (mean bay area / bay area)
    first-choice assignment  loads 5728 / 6278 / 7794  ->  normalised 3273 / 9315 / 13531  ->  Z2 = 10258
    Z2 = 0 would want          loads 11550 / 4448 / 3802
    whole range 0 -> 10258 costs 3 * 10258 = 30,773
    ONE block displaced to its second choice costs 600 * 40 = 24,300

So the objective on this instance is w1*Z1 + w3*Z3 and nothing else.  Observed runs sit at Z2 =
2276-7703, i.e. BELOW the first-choice value: the search has already collected most of a 30,773
prize while paying 600 * (1009 - 400) = 365,400 for it.

## 3.  Z3 > 0 is FORCED, and only the choice of victim is free

Peak simultaneous minimum-orientation bounding-box area, every block at its first choice, each
running [release, release+pt):

    bay0  cap 1911   peak 1078 at t=33    56%     833 spare
    bay1  cap  736   peak 1083 at t=44   147%     347 over
    bay2  cap  629   peak 1265 at t=33   201%     636 over

About 983 area units must leave the two small bays at the peak.  The crunch is a WINDOW, t ~ 20-48,
not the horizon -- which is why the aggregate-row model in `_bayplan` could not see it.

Every block fits in every bay in some orientation (fit-set = (0,1,2) for all 150), so nothing is
geometrically pinned.  Top choices are near-balanced: 55 / 47 / 48.

## 4.  THE SEARCH PICKS THE WRONG VICTIMS

A real 45 s incumbent, Z1 = 19, Z2 = 5556, Z3 = 1009, obj 748,742:

    22 blocks displaced, median area 74.5 against an all-block median of 46.3
    16 of the 22 go to bay0, 12 of them come from bay2
    worst payers   98, 96, 90, 84, 68, 68, 64, 57, 56, 50 ...
    meanwhile blocks with regret 6, 7, 10 and 16 and MORE area keep their first choice

The seven tardy blocks all WAITED (entry - release = 3..9) and all have due 52-56, i.e. they are
the t~33-45 crunch.

It is not a weighting error.  The cross-bay rank is

    drank = w1*tardy + w3*pen - mu*contact + w2*dobj2,     mu = 1e-3*min(w1,w3) = 0.6

so 600*pen dwarfs contact already.  It is SEQUENTIAL: a block that reaches a full bay can only
compare its own alternatives and can never propose that a cheaper block still to be dispatched
should be displaced instead.

## 5.  DECIDE ALL 150 AT ONCE AND THE NUMBER COLLAPSES

Area relaxation: each bay a cumulative resource of capacity width*height, each block an interval
of length pt starting no earlier than release, demanding its bounding-box area.  Minimise
w1*Z1 + w3*Z3.  Single CP-SAT worker:

    budget    Z1    Z3     w1*Z1 + w3*Z3
      5 s      2   483        303,134
     10 s      1   484        297,067
     20 s      0   425        255,000
     40 s      1   217        136,867
    330 s      1   170        108,667          12 blocks displaced at mean penalty 14,
                                               37 blocks waiting, max wait 9

against the incumbent's 732,073.  A 5 s single-worker solve of the relaxation is already 2.4x
better than the thing we ship 120 s of search on.

This does not contradict results/audit/z3floor.md, which refuted RETROFITTING moves into a built
packing (1 of 15 realisable).  Nothing here is retrofitted.

## 6.  SO 20만대 IS BELOW THE FLOOR AND 25-29만 IS NOT

    proven admissible at exact per-slice area capacity : Z3 = 387  ->  600*387 = 232,200
    plus a realistic Z2 (2276 observed)                 ->  ~6,800
    floor                                               ~239,000 at Z1 = 0

A friend's 260,000 is a few per cent above that floor, i.e. very nearly optimal, and our 473,456
best draw is 1.8x it.  The bottom of 20만 is not reachable; the top of it is.

## 7.  TWO SWEEPS RETRACTED ON READING THE CODE

`prefw` is dead code in the beam.  `best_cell_contact` computes `pen` once per BAY and then takes
an argmin over (orient, ix, iy) INSIDE that bay, so `prefw*pen` is a constant added to every
candidate in the group and cannot change the winner; the cross-bay rank that follows does not read
prefw at all.  Twelve draws at 0/0.5/2/8/32 and a further range-finder at 1e2/1e3/1e4 measured the
tie-break behaviour of `lb_best` and nothing else.

`_bayplan`'s +34% refutation does not test what it says.  It passes its CP-SAT assignment to the
beam as `anchor_bays=ab, anchor_order=ao, stay_w=0.0`, and `_contact_beam` does

    _anchor_w = [0.0] * n
    if stay_w > 0.0: ...

so every anchor weight is zero.  The only thing that experiment changed was `order_ids =
anchor_order`, i.e. release-then-due dispatch.  Its +34% is a measurement of that order.  (The
engine's own note is independently right that a soft anchor cannot bind at all: the weight enters
only `drank`, which sorts a list holding one entry per bay, and topk = K >= n_bays everywhere here.)

## 8.  WHAT IS RUNNING ON IT

`OGC_CPANCH` runs the relaxation and rewrites the bay preferences as pref[j] + toll on the planned
bay -- the one channel that reaches `drank`, the beam's state rank and the rollout together.  The
caller's instance is never mutated, so the grader still scores the true preferences.

    toll 60, alternatives flattened to 0    Z1 17  Z3 964    12 deviations carrying 609 of it
    toll 100, real preferences kept         Z1 41  Z3 641     5 deviations carrying 264 of it

Flattening was wrong: a block forced off plan had nothing left to tell it which bay to take.
Keeping the real preferences under the toll cut deviations to five -- and the beam then bought its
obedience with tardiness, which says the model is optimistic about time because bounding boxes do
not tile a bay.  `OGC_CPCAP` de-rates the capacity to buy that slack in the model, where it is
free, rather than in Z1 at 6,667 a unit.  `harness/cpanch.sh` is the toll x de-rating grid.
