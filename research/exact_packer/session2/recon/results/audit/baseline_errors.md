# I PICKED THE WRONG BASELINE THREE TIMES TONIGHT, THE SAME WAY EACH TIME

    claim                                     baseline I used              what it should have been
    "one draw beats the pipeline by 11.4%"    2,795,643, a stale           2,469,078, production's
                                              "best ever"                  actual best -> production
                                                                           wins by 0.4%
    "the whole pipeline is worth 0.4%"        a seed production never      3,190,472, the seed it
                                              generates (axis 2, w6000)    does generate -> the
                                                                           operators deliver 22.6%
    "pinning axis 2 wins by 27% on prob_16"   3,472,568, the median of     2,674,298, THIS BUILD's
                                              249 runs across many builds  rotation control, run
                                                                           minutes later -> -5.7%

Every one of them compared a fresh measurement against a POOLED HISTORICAL number instead of
against a control from the same build, run at the same time, on the same machine.  Every queue I
wrote tonight pairs its arm with a control for exactly this reason, and then I reached past the
control for a more convenient figure when writing the analysis.

The 27% case is the worst of the three because it was reported as an explanation for the user's
score gap against a friend, and that explanation is now withdrawn: this build's rotation reaches
2,674,298 on prob_16, which is 23% better than the historical median I called typical.

## THE RULE THAT WOULD HAVE CAUGHT ALL THREE

A number from a different build, a different budget, or a different harness is not a baseline.
The only valid comparison is the control cell from the same queue.  If a queue has no control
cell for the comparison being made, the comparison is not available -- not "available with a
caveat".

## WHAT SURVIVES ON prob_16

    ax2  2,521,495     rot  2,674,298     -5.7%, one pair

And this build's prob_16 controls have already read 2,674,298, 2,902,331 and 2,962,652 tonight --
a 10.8% span -- so -5.7% is inside the control spread and is not yet a result.
