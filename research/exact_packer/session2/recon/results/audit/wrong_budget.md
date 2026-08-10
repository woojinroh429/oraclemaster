# WITHDRAWN -- SEE THE CORRECTION AT THE BOTTOM.  THE BUDGET IS NOT ESTABLISHED.

# EVERY EXPERIMENT TONIGHT RAN AT TWICE THE REAL BUDGET

    def algorithm(prob_info, timelimit=60):

and PROJECT.md, from an earlier session:

    "grader 머신이 로컬 컨테이너보다 ~2배 빠름.  prob_20 TL sweep: 로컬 60s=177111,
     120s=105274, 200s=91120.  grader 60s=114950 ≈ 로컬 ~110s.  즉 grader 60초 ≈ 로컬 30초.
     모든 로컬 60초 측정이 grader보다 저성능 -- 로컬 A/B 해석 시 반드시 감안."

So the grader gives 60 s on a machine about twice as fast as this container, which makes the
faithful local proxy about 110-120 s.  Every cell I ran tonight was 240 s.

## WHAT THAT DOES TO TONIGHT'S FINDINGS

    "round 0 saturates: 155 s and 228 s are the same over 248 samples"
        At the grader-equivalent budget round 0 is about 70 s, which is BELOW where I measured
        saturation.  The saturation result may be true and irrelevant.

    "the parity-directed fill round moves the answer 2 times in 53"
        Measured at 240 s, where round 0 already had 155 s.  At half the budget the fill round is
        a different proposition entirely.

    "more rounds lose; at 40 s rounds the parity read inverts"
        40 s rounds came from splitting 120 s.  At the real budget the whole round structure is
        different and this was never the comparison being asked.

    "brk is neutral on prob_1 over seven paired replicates"
        All at 240 s.  brk's floor is 8 s and its slices ran 17-68 s; at half the budget it
        competes for a much scarcer resource.

    the axis director, -10.2% over two pairs at 240 s
        Its own comment says the effect should be LARGER when draws are scarce: "at the 60 s the
        hidden set gives its early instances it is closer to one each, so the axis that would have
        won gets a single draw".  I measured it in the regime where it should matter LEAST.

## WHY THIS WAS AVOIDABLE

The budget is the first line of the entry point and the note is in the project's own记录.  I ran
sixty-plus cells without checking which regime the score is decided in, and the whole night's
recurring symptom -- clean local measurements that do not transfer to the submission -- has an
obvious candidate explanation that was sitting in the file.

## WHAT CHANGES NOW

Local 120 s is the proxy, not 240 s.  It also halves the cost of a cell, which is the only way to
fight prob_16's 22.3% control spread with enough replicates to read a 10% effect.


## CORRECTION, WRITTEN MINUTES AFTER THE ABOVE

The claim "every experiment tonight ran at twice the real budget" is NOT SUPPORTED and is
withdrawn.  My two pieces of evidence were both weak:

    `def algorithm(prob_info, timelimit=60)`     a DEFAULT.  harness/run1.py passes T explicitly
                                                 and so, presumably, does the grader.  A default
                                                 says nothing about what the caller passes.

    PROJECT.md's "grader 60초 ≈ 로컬 110초"        from a stage whose objectives were 100k-150k.
                                                 The current hidden P3 is 5,581,976.  Different
                                                 problem set, so the timing note may not carry.

And there is evidence pointing the other way, in myalgorithm.py's own comments:

    "Traced on the real hidden P6 at 300s"
    "P6 at its real 900s went 29396046 -> 30898889"

Hidden instances at 300 s and 900 s.  Those objectives (29M) do not match the current P6 either
(928,753), so they may also be from an earlier stage -- which is exactly the point: the evidence
is ambiguous in both directions and I picked the direction that made a tidy story.

I do not know the final's per-instance budget.

## WHAT THE dir120 QUEUE IS, GIVEN THAT

Not "the correct regime".  A BUDGET SENSITIVITY test.  The director read -7.64% and -12.83% at
240 s; if the effect grows at 120 s then its value rises as the budget falls, which is usable
whatever the real budget is, and if it shrinks then the 240 s reading was specific to that regime.
Either answer is worth having without knowing the number.

Until the number is known, prefer changes whose sign does not depend on it.
