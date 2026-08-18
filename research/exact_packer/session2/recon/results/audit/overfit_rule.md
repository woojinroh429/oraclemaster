# What may and may not be done with a per-instance finding

The exchange rate w1/w3 separates experiments that pooled to nothing (exchange.md).  The obvious
next move -- "if w1/w3 >= 50 use aim 0.10" -- must not be made.  The threshold 50 was chosen by
looking at the training data, the evidence behind it is n=3 per band, and it would be applied to
eight hidden instances whose limits and composition are not disclosed.  That is the definition of
the overfitting this project has been told to avoid, and the failure mode is not a small loss: a
wrong branch costs the whole instance.

The shipped build already contains the correct answer to "we cannot know which setting is right":
four workers split across beam aims 0.90 and 0.10, and the answer is their MINIMUM.  A worker on
the wrong side of the split simply loses and is discarded.  The two-phase aim race built earlier
today removed that protection -- it committed to one aim after a short probe -- and lost 5.45% on
prob_34 for exactly that reason.

So a band-specific finding converts into portfolio membership, never into a branch:

    form                                            safe?
    "if condition X then setting A else B"          NO   -- we pick the threshold
    "give one worker setting A, keep the rest"      YES  -- the minimum picks, a wrong arm just
                                                           loses its draw and costs nothing else
    "A is better in every band"                     YES  -- change the default, no rule needed

The second form is what the lst result (2 of 2 in the >=50x band on b240) would justify: run one
worker on lst, let the min decide.  No threshold exists to be wrong about.

This also bounds what aim240 can conclude.  "Use low everywhere" would be a legitimate outcome --
it is a default change, not a rule.  "Use low when the rate is high" would not be, however clean
the split looks.  Its first two pairs are losses for low at 88.9x and 106.7x, so the former looks
unlikely in any case.

The diagnostic value stands on its own and needs no rule: every A/B from here reads by band, which
is why this session kept concluding that arms differ by less than the same arm differs between
draws.
