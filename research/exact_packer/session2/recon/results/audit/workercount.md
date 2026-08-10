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
