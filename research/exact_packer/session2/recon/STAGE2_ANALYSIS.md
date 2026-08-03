# The final-round practice set is a different problem from the preliminary one

Measured on the 40 stage-2 instances, against the 40 preliminary training instances and the six
hidden instances we have been tuning on all along.

Density here is demand over capacity: the sum over blocks of (layer-0 bounding-box area x
processing time), divided by (total bay area x horizon). Above 1.0 the yard cannot hold the work,
so tardiness is forced rather than avoidable.

| set | n | bays | density | density > 1 |
|---|---|---|---|---|
| stage-2 (final practice) | 150-300 | 2-5 | 0.38 - 2.33, median 0.72 | **10 of 40** |
| stage-1 (preliminary) | 100-300 | 2-5 | 0.19 - 1.04, median 0.40 | 1 of 40 |
| hidden P1-P6 | 100-250 | 2-4 | 0.17 - 1.14, median 0.51 | 1 of 6 |

The median density rises by 1.8x and the number of over-capacity instances goes from one to ten.
On the preliminary set, Z1 was exactly zero on half the instances; that slack has largely gone.

## The tail is much worse than anything we have tuned against

    prob_36   density 2.335   n=300  bays=2   w1=6,667  w3=800
    prob_13   density 2.278   n=300  bays=2   w1=6,667  w3=800
    prob_25   density 1.849   n=300  bays=2   w1=6,667  w3=200
    prob_26   density 1.297   n=300  bays=2   w1=6,667  w3=800

Hidden P6 -- the instance that has cost us the most effort -- is density 1.137 with 250 blocks in
three bays. The worst four here are 300 blocks in **two** bays at up to twice that density.

## What this changes

**The instance we have been optimising is not represented.** Hidden P3, where the 80,795 work has
gone, is density 0.327. The sparsest instance in the entire final practice set is 0.381, and its
median is more than twice P3's. Time spent making a 0.33-density instance reproducible buys
nothing here.

**It reverses the contact-bound decision.** The bound is worth 545,561 on P6 (about 1.8%) and
2.2% on P5, against 7.7% on P3. That trade was close when the set was one P6 against one P3. With
ten P6-shaped instances and nothing P3-shaped, it is not close.

**A combination the preliminary set never contained.** w3 reaches 800 here against 600 before,
and the instances with the highest w3 are also the densest -- prob_13, 26 and 36 all pair w3=800
with density above 1.3. Preliminary instances split cleanly into "Z1 is zero, preference is
everything" and "Z1 is everything". These are both at once, and no operator has ever been
measured on that combination.

## Unchanged

No block is individually impossible: due - release - processing is non-negative for every block
in all 40. Layer counts (mean 1.8, or ~2.9 on the three-layer instances) and orientation counts
(7.5 typical, 12 on some) are in the same ranges as before, so the geometry engine faces nothing
new -- only more of it, in less space.
