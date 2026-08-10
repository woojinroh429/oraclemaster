# THE BEAM STOPS ITSELF AT HALF ITS ALLOWANCE, AND THAT IS WHERE prob_1's MISSING 11% IS

520 production draws on prob_1, from OGC_DRAWSTAT, comparing the seconds each beam was ALLOWED
against the seconds it USED:

    took / ask      median 0.49      p10 0.22      p90 0.70
    used >= 95% of its allowance      1% of draws
    used <= 60% of its allowance     78% of draws

    first draw of a worker    ask median 31.0 s   took median  8.9 s
    later draws               ask median 14.7 s   took median  6.0 s

The budget is not what stops the beam.  It leaves half its time on the table on nearly every draw.

## AGAINST THE DETERMINISTIC CURVE

    production axis 2                        stops itself around 9 s
    deterministic axis 2, work 12,000        51 s, and still improving 8.9% over work 6,000
                                             686,238 -> 684,687 -> 573,634 -> 522,683

One 51 s construction on axis 2 returns 522,683.  The best of THIRTY-FOUR production
constructions on the same pinned axis returned 587,906.  The single big draw wins by 11%.

## A DIAGNOSIS I GAVE ONE MESSAGE AGO AND HAVE TO CORRECT

I said production "starves its best axis by about 6x" and that the fix was bigger slices.  Wrong
cause: the slices are already about three times what the beam consumes.  Nothing is being starved;
the beam declines the food.

So more budget cannot buy this.  The thing to look at is the stopping rule.

## WHY THE SAME CONTROLLER BEHAVES DIFFERENTLY IN THE TWO MODES

`_beam_once` splits its budget between a fine rung (step 1) and a coarse rung (step 2) held in
reserve, and the engine's adaptive width controller sizes each level from `left / (per * rem)`
where `per` is measured SECONDS per state.  Under OGC_WORKCAP the same three places read the work
counter instead.

Time-driven, the controller sees seconds-per-state on a loaded four-core box, decides it cannot
afford more width, and converges early.  Work-driven, it has a fixed expansion budget and spends
all of it.  That is the whole difference between a 9 s draw returning 587,906 and a 51 s draw
returning 522,683.

This is a controller question, not a parameter question, and it is the first thing tonight that
identifies compute the run is DECLINING TO USE rather than spending badly.

harness/beamprod.py measures `_beam_once` itself under WORKCAP with repeated digests, which is the
experiment that separates "the reserve split is the cause" from "the width controller is".
