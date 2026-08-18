# THE TARGET ON stage2/prob_1 IS 280,000, AND BOTH HALVES OF IT ARE ALREADY ON RECORD

Weights, from the instance file:  obj = 6667*Z1 + 3*Z2 + 600*Z3

Z2 is 4% of the objective and has never mattered.  Z1 costs 6,667 PER UNIT and our runs put it
anywhere from 1 to 55 -- a spread of 360,000 on its own.  Z3 costs 600 per unit and runs 441 to
1,086.  Over 458 recorded runs on this instance:

    Z1 minimum ever    Z1 = 1     that run had Z3 = 741      obj 458,512
    Z3 minimum ever    Z3 = 441   that run had Z1 = 17       obj 402,890
    best objective     392,626    Z1 = 7,  Z3 = 543          both middling

    both minima at once ->  6667*1 + 3*2500 + 600*441  =  278,767

Not one run in 458 has had Z1 and Z3 low together.  The search trades them, and every entry has
been paying for one of them.  278,767 is where the competitor's reported figure sits.

## AND CP-SAT ALREADY PROVED THE Z3 FLOOR IS LOWER STILL

From myalgorithm.py's own comment on the Z3 work: 76.8% of prob_1's objective is the preference
term, CP-SAT says Z3 821 -> 387 is admissible at exact per-slice area capacity, and _regroup showed
the obstruction is the blocks that STAY.

    Z1 = 1 with Z3 = 387  ->  6667 + 7,500 + 232,200  =  246,367

So the ceiling on this instance is not a search-luck question at all.  387 is proven reachable on
the area relaxation and 441 has been reached in practice; 1 has been reached for Z1.  What has
never happened is the two in the same solution.

## WHICH RETIRES EVERYTHING MEASURED IN THIS SESSION

Worker count, round count, axis choice, beam width, config slots, the direction pair -- every one
of them moves WHICH DRAW WINS.  They shuffle the same trade-off curve.  None of them attacks the
reason a solution with Z1 = 1 carries Z3 = 741.

    the question is not "how do we draw better tickets"
    it is "why can no ticket have both"

_regroup's finding names where to look: the obstruction is the blocks that stay put.  That is the
next piece of work, and it is the first thing this session has found that could move the instance
by 25% rather than 5%.
