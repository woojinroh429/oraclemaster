# THE 240 s REGIME IS NINE TIMES NOISIER THAN THE 120 s ONE, AND I SPENT THE NIGHT IN IT

    prob_16 control draws, same build, same machine

    240 s   2,674,298  2,902,331  2,962,652  2,971,117  3,271,810      span 22.3%   (n=5)
    120 s   3,472,619  3,558,783                                       span  2.5%   (n=2)

## WHAT THAT DID TO THE AXIS DIRECTOR

    240 s   r1  -7.64%   r2  -12.83%      against a 22.3% control span
    120 s   r1  +0.95%   r2  +0.26%       against a  2.5% control span

At 240 s the director looked like the largest effect measured all night.  At 120 s, where a 1%
difference is readable, it is zero.  So the 240 s pair were two draws from a wide distribution,
not an effect.

This is the fifth two-replicate reading to reverse tonight, and the first to reverse for a reason
other than "run it again".  It reversed because the question was asked somewhere quieter.

## WHY THE SHORTER BUDGET IS QUIETER

At 240 s a run passes through round 0, a parity-directed fill round, and the tail polish, and each
of those is a branch point that can send the answer to a different basin -- the attractor table
shows 456 distinct values over 1,176 prob_1 worker results.  At 120 s the structure is shorter and
the run lands in the same place.

## THE METHODOLOGICAL COST

Sixty-plus 240 s cells tonight, roughly four hours of four cores, against effects of 2-10%.  In
that regime nothing under about 20% is readable on prob_16 and nothing under about 16% on prob_1.
The same questions asked at 120 s cost half as much per cell AND have an order of magnitude less
noise to fight.

Every future A/B here should be run at the shorter budget first, and only re-checked at the longer
one if the arm is adopted -- not the other way round, which is what I did all night.
