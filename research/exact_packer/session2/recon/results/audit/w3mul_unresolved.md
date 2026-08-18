# w3mul: TWELVE DRAWS PER CELL AND THE STATISTICS DISAGREE.  CLOSED AS UNRESOLVABLE.

stage2/prob_1 at 120 s, uniform config-A workers (DIRSET=0, AIMSET=0.90, MSET=1, ORDER=lst) so
contention is constant and w3mul is the only free variable.  Round-0 draws pooled, three runs each:

    w3mul  draws       min       p25    median   run mean
     0.25     12   634,510   710,235   723,199    685,198
     0.5      12   533,575   736,293   760,310    671,883
     1.0      12   612,876   702,161   745,782    663,289
     2.0      12   507,871   679,906   745,782    587,715
     4.0      12   521,903   694,406   745,782    659,454
     8.0      12   630,180   737,546   745,782    690,850

    min       best 2.0    worst 0.25
    p25       best 2.0    worst 8.0
    median    best 0.25   worst 0.5
    run mean  best 2.0    worst 8.0

The four statistics disagree on both ends, and the median is degenerate: four of six cells report
exactly 745,782, an attractor rather than a location.

## THE EIGHT-DRAW READ DID NOT SURVIVE TWELVE

At eight draws this file's predecessor recorded "0.5 is worst on min, p25 and median
simultaneously -- the first result tonight where three statistics agree at once".  Four more draws
per cell moved 0.5 to SECOND BEST on min.  A signal that inverts when the sample grows by half was
not a signal, and that is the twelfth such reversal in this session.

2.0 leads three of the four statistics, which is weak evidence rather than none, but it is nowhere
near enough to move a default -- and the whole point of the pre-registered rule was to stop reading
orderings out of noise.  RULE APPLIED AS WRITTEN: statistics disagree -> unresolvable -> close it.

## WHY THE SHIPPED CHECK IS SKIPPED TOO

w3ship.sh was queued to test 0.5 against 2.0 and 4.0 in the real 2A+2B portfolio at five pairs.
That rig is strictly noisier than this one -- the answer there is a minimum over two config-A
workers instead of four, and config B's cost varies between arms.  An effect that twelve draws in
the quiet rig cannot resolve will not be resolved by five pairs in the loud one.  Skipped.

## WHAT THIS LEAVES

The direction pair (order=lst, w3mul=0.5) is worth 2.03x on draw quality -- a worker carrying
neither drew a median of 993,027 against 482,866 and 489,878 for two carrying both.  If w3mul
carries little of that, order carries nearly all of it, and order is the larger space: eight
qualitatively different dispatch policies rather than six points on a scalar.  ordsweep.sh runs
lst / edd / defer_big / big_first / rank / sac3 / aspect / boxfill, all verified to produce
distinct sequences on this instance before queuing.
