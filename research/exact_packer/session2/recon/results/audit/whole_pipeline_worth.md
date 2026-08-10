# THE WHOLE PIPELINE IS WORTH 0.4% OVER ONE 32-SECOND CONSTRUCTION, AND THE AXIS IS WORTH 2.6x

## The deterministic harness reproduces across sessions and builds, digest included

    work_mode.md, an earlier session        this run, a different build
    prob_16 axis 0 w6000   6,408,684        6,408,684
    prob_16 axis 1 w6000   6,214,513        6,214,513
    prob_16 axis 2 w6000   2,477,998        2,477,998  digest 973cef52e3c7c256 both times

So the famous single-draw number is real.  Only the baseline it was compared against was stale.

## THE COMPARISON THAT MATTERS

    one construction, axis 2, work 6,000, 32.2 s, ONE core        2,477,998
    the full run, 240 s x 4 workers = 960 core-seconds            2,469,078
                                                                  -----------
    what the entire pipeline buys over one good seed                   0.4%

Thirty times the compute for four tenths of a percent.  And at the same work, choosing the axis is
worth this instead:

    axis 2  (B 67, K 5)   2,477,998
    axis 1  (B 96, K 4)   6,214,513
    axis 0  (B 96, K 4)   6,408,684        2.6x

## WHAT THAT SAYS ABOUT EVERYTHING MEASURED TONIGHT

brk, round count, RESFRAC, POLCAP, PARFILL, PARROUND, BRKPAR, axis pinning -- every one of them
moves seconds around INSIDE that 0.4%.  That is why they all landed inside the noise: the noise
was not unusually large, the space those arms operate in is unusually small.

The (B, K) structure operates outside it, at 2.6x on prob_16 and 2.3x on prob_1, on two instances
from two objective families, reproducible to the digit.

## THE CAVEAT THAT STOPS THIS BEING A CONCLUSION

All of that is the SEED space.  Seed quality has already failed to reach the score once tonight:
pinned axis 2 -- which is 67/5 -- finished at 515,465 on prob_1, sixth of seven, while the
rotation finished at 461,233.  The operators appear to wash out a large part of the seed
difference.

If a 2.6x seed advantage is worth nothing at the finish, that is the single most important fact
about this algorithm and it deserves to be stated plainly rather than worked around.  bk67 is the
test: same six orders and weights, one width and one K, portfolio intact.
