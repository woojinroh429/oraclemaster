# Tardiness is not locally reachable in a finished solution

The case for spending the reserved tail on Z1 was strong on paper: Z1 carries a median 59% of the
weighted objective and, decomposed over four runs of P7, 92% of the run-to-run spread. The
codebase already disagreed -- myalgorithm.py records _pull_early as measured at 0.05% for 22 s and
deliberately unregistered -- but that measurement was taken inside the operator loop, where the
pass competes for budget. The tail is a different setting, so the opportunity was measured
directly: solve normally, then hand the finished solution to _pull_early with the tail's budget.

    inst   solve      objective     Z1        result
    P7      90 s      1,088,155        60     nothing, in 1 s
    P25     90 s     78,565,772    11,552     nothing, in 30 s
    P13     90 s     73,547,018    10,071     nothing, in 27 s

Three of three. On the 300-block instances there are over ten thousand tardy days on the table and
a dedicated half-minute finds no move that survives acceptance on the full objective.

## Why, and what it changes

The yard is a zero-sum space-time resource. Pulling one block's entry earlier occupies cells that
something else needed, so the displaced block goes later; acceptance is on the full objective, so
the trade has to pay, and at the end of a converged run it does not. Tardiness is decided by the
GLOBAL schedule -- by which dispatch order the beam committed to and which bays the repacking
operator rebuilt -- not by slack left lying in the final solution.

So the 92% figure was read the wrong way round. Z1 dominating the variance does not mean Z1 is
where the variance can be attacked; it means the variance in the search's outcome shows up in Z1,
because Z1 is the term the schedule moves. Attacking it needs a different schedule, not a repair.

## What that leaves

The one structural lever still untested is the workers. They are fully independent and combined
only by a final minimum, and on P7 one of the four returned 2,932,676 against the winner's
923,531 -- a factor of 3.2, which is a whole core producing nothing usable for the entire budget.
Sharing the best objective between workers, so that one hopelessly behind restarts from a fresh
seed instead of polishing a dead basin, turns wasted capacity into extra draws, and more draws is
exactly what tightens a minimum.

The risk is the one already documented: this touches the search, so it moves every instance rather
than only the bad ones, and a change that reshuffles the trajectory has been worth -7.7% before.
