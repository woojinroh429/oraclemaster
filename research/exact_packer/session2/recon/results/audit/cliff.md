# The budget cliff: below a size-dependent minimum the answer is the floor, not a worse solution

Measured, shipped configuration, one run per cell.  A tick is a normal answer; a cross is
`_safe_sequential`, the floor every worker produces before it tries anything.

    blocks           60s   90s  110s  130s  150s  180s      cliff between
    prob_36  300      X     X     X     ok    ok    ok       110 - 130 s
    prob_20  250      X     X     ok    ok    ok    ok        90 - 110 s
    prob_24  150      ok    ok    ok    ok    ok    ok       under 60 s

    prob_36  at 110s  4,023,023,433   against    96,871,459 at 130s     42x
    prob_20  at  90s  1,858,390,507   against    12,970,522 at 110s    143x

## Why it is a cliff and not a slope

The beam either finishes or returns nothing -- `if elapsed > deadline_s: return None` in the
construction loop.  Under its own minimum every worker comes back with only the floor, so the
portfolio has nothing to rank and the floor IS the answer.  Degradation is 42x-143x, not a few
percent.

## Why it matters for the submission

The hidden per-instance time limits are not disclosed; the report says so.  The eight hidden
instances all returned sane values, so the limits have been sufficient so far.  But the margin on
a 300-block instance is 50 s of 180 s, and this machine's own speed moved 8.4% within an hour
today.  A slower grader, or a larger hidden instance, does not cost a few percent on that
instance -- it costs the instance.

## The fix this points at

The beam already completes partial states by rollout at every level; that is how it ranks
survivors.  Returning the best completed partial when the budget runs out, instead of None, turns
the cliff into a slope and needs no new machinery.
