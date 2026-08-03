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

## First run on the hard end, and how far it is from a bound

Four hardest instances at 300 s, contact bound on. All feasible.

| instance | density | objective | Z1 | Z2 | Z3 |
|---|---|---|---|---|---|
| prob_36 | 2.335 | 86,612,032 | 12,265 | 6,077 | 6,044 |
| prob_13 | 2.278 | 74,996,317 | 10,376 | 1,925 | 7,272 |
| prob_25 | 1.849 | 81,169,672 | 11,932 | 1,357 | 8,068 |
| prob_26 | 1.297 | 26,744,859 | 2,682 | 4,765 | 11,074 |

Z1 carries 67% to 94% of the objective on all four.

### An energetic lower bound on Z1

Space-time is a resource. Up to day *d* the yard offers (total bay area) x *d*; the blocks due by
then demand the sum of (layer-0 bbox area x processing time). Where demand exceeds the offer, some
of those blocks cannot finish on time however they are packed, and keeping the smallest ones
minimises the *count* that must be late. Since

    Z1 = sum_i max(0, EXIT_i - D_i) = sum over shifts s >= 0 of |{ i : EXIT_i > D_i + s }|,

applying that count argument to the deadlines shifted by *s*, and summing over *s*, bounds Z1 from
below. Geometry is ignored throughout, so this is a relaxation and the true optimum is higher.

| instance | Z1 bound | Z1 ours | ratio |
|---|---|---|---|
| prob_36 | 3,371 | 12,265 | 3.64x |
| prob_13 | 2,803 | 10,376 | 3.70x |
| prob_25 | 2,334 | 11,932 | 5.11x |
| prob_26 | 230 | 2,682 | **11.66x** |

Real polygons cannot pack to 100% of the area, so the attainable optimum sits above the bound --
but assuming even 70% packing efficiency raises it only ~1.4x, which does not account for 3.6x to
11.7x.

**The gap grows as density falls.** At 2.3 we are 3.6x off; at 1.3 we are 11.7x off. Where the yard
is saturated nobody can do much, and the ordering is close to forced; where there is slack, that
slack is exactly what we are failing to exploit. Six of the forty final instances sit in the
1.0-1.5 band, and that band is where the most is being left behind.

This is the opposite of where the effort has gone. The sparse-instance work targeted density 0.33,
which does not occur in the final set at all.

## Correction: only three instances are genuinely saturated

Density above 1.0 is a crude test, and it overstated the case. Applying the shifted-deadline
energetic bound to all forty instances gives a sharper answer:

    forces tardiness (bound > 0)      12 of 40
    could in principle reach Z1 = 0   28 of 40

and of the twelve, only three force a substantial amount:

    prob_36  Z1 >= 3,371      prob_18  Z1 >= 125
    prob_13  Z1 >= 2,803      prob_37  Z1 >= 116
    prob_25  Z1 >= 2,334      prob_40  Z1 >=  54
    prob_2   Z1 >=   449      prob_5   Z1 >=  42
    prob_39  Z1 >=   362      prob_14  Z1 >=  10
    prob_26  Z1 >=   230      prob_20  Z1 >=   5

So "ten over-capacity instances, the set is P6-shaped" was too strong. Three are saturated, nine
are barely constrained, and twenty-eight have no forced tardiness at all.

This changes what the set is testing. The bound ignores geometry, so an instance with bound zero
still incurs tardiness in practice -- through packing loss, not through arithmetic. Any Z1 we
produce on those twenty-eight is ours, not the instance's. Most of the final round is decided by
how well the yard is packed and scheduled, which is the opposite of a set where everyone is
equally stuck.

Measured evidence that the headroom is real: on prob_26 the bound is 230 and we produced 2,682.

## Where the tardiness actually comes from

Decomposing one real solution (prob_26, 120 s, 300 blocks, Z1 = 2,710):

    late blocks                       201 of 300 (67%)
    entry delay (entry - release)     mean 10.6, median 5, max 58; 28% enter at release
    slack (due - release - proc)      mean 1.9, median 2
    overstay (exit - entry - proc)    mean 0, max 0, total 0

Two things follow immediately. Slack is tiny, so a three-day delay already makes a block late --
the instance is extremely sensitive to entry delay. And overstay is exactly zero everywhere, so
the "a block may stay longer than needed" freedom is already fully exploited and there is nothing
to win there. Since T_i = max(0, (ENTRY_i - R_i) - S_i), **Z1 is entirely an entry-delay problem**.

### The yard is not full while blocks wait

    peak utilisation                                   66.9%
    mean utilisation while at least one block waits    53.7%
    days with someone waiting and utilisation < 70%    62 of 62

Blocks wait an average of 10.6 days in a yard that is about half empty. We are not capacity-bound.

### Search loss versus structural blocking

For 150 blocks that waited, we rebuilt the bay state on their release day from the actual
residents and asked the engine's own feasibility scan whether they could have entered:

    a legal placement existed      54  (36%)   -- the search simply did not take it
    nothing fitted anywhere        96  (64%)   -- fragmentation or blocked crane descent

This splits the problem in two, and the halves need opposite treatments.

**The 64% is not a search problem.** Half the yard is free and nothing can be lowered into it.
GRASP, BRKGA or any other metaheuristic searches harder over the same placement rule, and it is
the rule that leaves the space unusable. Fixing this means changing the placement objective from
"pack tightly" to "preserve descent access for what comes later".

**The 36% is recoverable now**, and not because the search is weak: no operator in the portfolio
ever tries to move an entry earlier. Balance targets Z2, preference targets Z3, repacking rebuilds
one bay, and the beam only decides entries once, during construction. Nothing attacks entry delay
directly, which is the one quantity Z1 is made of.
