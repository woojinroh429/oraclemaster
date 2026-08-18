# WITHDRAWN -- THE SPREAD COMPARISON WAS n=2 AGAINST n=5.  SEE THE BOTTOM.

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


## CORRECTION: THE COMPARISON WAS UNFAIR AND THE CONCLUSION IS WRONG

The third 120 s control came in at 3,199,896, and the 120 s span went from 2.5% to 11.2%.  Read at
the SAME sample size:

    n=3   240 s   2,674,298 / 2,902,331 / 2,962,652     span 10.8%
    n=3   120 s   3,199,896 / 3,472,619 / 3,558,783     span 11.2%

The two regimes have the same spread.  The "22.3% against 2.5%" that this document was built on
compared five draws against two, and a wider sample finds a wider span by construction.  The
shorter budget is not quieter and the methodological conclusion above -- run everything at 120 s
first -- has no support.

WHAT STILL STANDS.  The axis director reads +0.95% and +0.26% at 120 s and -7.64% and -12.83% at
240 s.  Four pairs, two regimes, signs split, all inside a spread of about 11% either way.  The
director is not established as helping anywhere; the 240 s pair remain two draws, and so do the
120 s pair.

THIS IS THE THIRD TIME TONIGHT I HAVE QUOTED A SPREAD FROM TWO SAMPLES -- prob_20 "repeats to the
digit", prob_16 "2.1% within this build", and now this -- and the third time the next sample
destroyed it.  Two draws do not measure a spread.  The rule that follows is not about budgets: do
not report a spread at all until n >= 5, and never compare spreads at different n.
