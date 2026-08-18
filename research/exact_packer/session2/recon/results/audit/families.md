# THE TWO HALVES OF THE PORTFOLIO ARE TWO ALGORITHMS FOR TWO PROBLEMS

Decomposing each instance's best known objective into its three terms splits the set in two.
`Z3 sh` is w3*Z3 as a fraction of w1*Z1 + w2*Z2 + w3*Z3 at that solution; `even win` is how often
the m=1 / lst / w3mul=0.5 pair held the minimum, over every WSTAT line logged.

    inst      Z3 sh      n    even win
    prob_12   91.3%     53      56.6%
    prob_34   90.9%     11      63.6%
    prob_3    89.4%     52      65.4%
    prob_1    86.3%    207      91.8%
    prob_4    53.1%     40      82.5%
    prob_16   48.7%    180      20.0%
    prob_26   37.5%     61      21.3%
    prob_24   23.2%     34      17.6%
    prob_30   19.7%     56      19.6%
    prob_20   15.1%    155       5.2%
    prob_6    14.9%    137      50.4%     <- the one that does not fit
    prob_36    7.3%     18       0.0%
    prob_2     1.9%     10      10.0%

    Pearson r = 0.788 over 13 instances

Above 50% Z3 the even pair takes 56-92% of the minima; below 40% it takes 0-21%.

## WHY THAT IS THE RIGHT SPLIT

    even   m=1, ORDER=lst, W3MUL=0.5     for instances that are an ASSIGNMENT problem
    odd    m=2, axis defaults            for instances that are a TARDINESS problem

w3mul=0.5 tells the beam to stop bidding for bay preference and spend its ranking on times and
feasibility, because the polish can solve preference exactly afterwards -- `_assign` pins the entry
times and hands every block's bay to CP-SAT at once.  That is the right division of labour when Z3
is most of the objective and the wrong one when Z1 is.

It also explains a run of results that looked unrelated.  prob_36 is 92.7% Z1 and saturated, so
every ranking edit tried on it returned the identical answer.  prob_1 is 86.3% Z3 and moved only for
the polish reserve and w3mul.  And the 7th submission made ORDER=lst a GLOBAL default -- a
Z3-family setting forced onto the Z1 family -- and regressed.

## THE CIRCULARITY, AND THE FIX

The Z3 share is measured at the best known solution, and that solution came from whichever
configuration won, so the predictor is partly an outcome.  It cannot be used as it stands.

The non-circular predictor is congestion, and it is already in the file: `_demand_ratio_phys` at
line 270, `sum(bbox_area * processing) / (total_bay_area * max_due)`, computed from the input alone.
Above 1.0 tardiness is forced and Z1 dominates; below it Z1 = 0 is reachable and only Z3 is left.
prob_34 is the case that proves the weights alone are not enough: its w3/w1 is the lowest of the
thirteen at 0.009, yet its Z1 share is 0.0% and the even pair wins 63.6%.

Next: correlate `_demand_ratio_phys` against the even-win column.  If it holds, which configuration
gets the workers can be decided from the instance BEFORE any search runs -- a quantity computed from
the input, not a memory of which instance is which.
