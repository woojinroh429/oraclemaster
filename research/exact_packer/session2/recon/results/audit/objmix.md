# What the objective is actually made of, per instance

Read off the Z1/Z2/Z3 columns that run1.py already prints, against each instance's own weights.
Best run per instance across r2fix, cliff40 and race.

    inst      w1     w2     w3   |    w1*Z1     w2*Z2     w3*Z3
    P6     13333      5    133   |    85.0%      0.3%     14.7%
    P16    13333      3    250   |    66.2%      0.1%     33.7%
    P20     6667      8    150   |    84.4%      0.1%     15.6%
    P25     6667      4    200   |    97.7%      0.0%      2.2%
    P26     6667      1    800   |    62.2%      0.1%     37.7%
    P30    13333      6    125   |    82.5%      1.0%     16.6%
    P34    13333      6    125   |     0.0%      9.1%     90.9%
    P36     6667      1    800   |    93.9%      0.0%      6.1%
    P40     3333      2    800   |    73.4%      0.0%     26.6%

    pooled   w1*Z1 89.0%   w2*Z2 0.1%   w3*Z3 11.0%

## Three things follow

**Z2 is 0.1% of the objective.** Under 1% on eight of nine.  Candidate ranking and operator
payoff are computed on the full _total, so every evaluation that separates two solutions by their
Z2 is separating them on noise.

**The instance set is not one population.**  P34 has Z1 = 0 -- no tardiness at all -- and 91% of
its objective is bay preference.  P36 is the opposite at 94% tardiness.  Both are 300-block
instances, which is why "size does not predict which beam aim wins" kept coming out of the axis
and aim experiments: the thing that differs is the objective mix, not the size.  Every A/B this
session was scored by counting wins across a set that contains both kinds, so a mechanism that
helps one kind and hurts the other reads as noise.

**The polish budget does not follow the mix.**  _z3_improve gets min(20%, 40 s) of every run.  On
P25 that is 20% of the time for 2.2% of the objective; on P36, 6.1%.  On P34 the same 20% is
buying 91%.  The share is fixed and the mix is not, and the mix is readable from prob_info's own
weights plus the incumbent's Z-values -- no instance property has to be guessed.

## And the term nobody targets

Z1 is tardiness, a function of entry_time against due date and nothing else.  Geometry enters the
problem only as a feasibility constraint; x, y and orientation do not appear in the objective.

Everything measured this session -- dispatch order, beam aim, axis sets, rounds, redraws, budget
splits -- changes HOW THE SOLUTION IS CONSTRUCTED.  Nothing re-optimises entry times against a
fixed assignment, so every attractor observed is a greedy-earliest schedule, and an optimally
timed schedule on the same assignment is a solution this search cannot currently produce.  That is
the same shape as the one change that ever clearly won: beam salvage widened the reachable set
rather than redistributing budget within it.

bayrepack has a late-entry ladder for exactly this (OGC_LATEK) and it defaults to 1, which is the
old single-late-window behaviour -- so deliberate delay is barely offered today.
