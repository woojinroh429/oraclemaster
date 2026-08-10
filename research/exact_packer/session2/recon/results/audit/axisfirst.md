# THE BEAM DOES NOT PRODUCE prob_1's ANSWER, AND THE BEST AXIS IS THE ONE WITH THE WORST BEAM

## Run level: OGC_AXIS pinned, 240 s, one replicate each

    ax0  630,785     ax3  517,814
    ax1  469,427     ax4  468,853
    ax2  515,465     ax5  437,959   <- best pinned axis
                     rot  453,039   <- the shipped rotation

44% between the best and worst axis, which confirms at run level what the file already claimed
(32-210% between configs against 0.0-12.6% repeating one).  Both extremes -- best ax5 and worst
ax0 -- are the two axes that NEVER open a run under the shipped wiring.

## Construction level: 251 DRAW lines, and this is the part that matters

    axis    n      best construction   median construction
    0     152          533,320              946,574
    3      20          541,099              892,710
    1      21          576,367              907,224
    4      22          549,408              944,919
    2      16          781,046              903,770
    5      20          876,079            1,033,770   <- worst constructions

NOT ONE OF 251 CONSTRUCTIONS REACHED 450,000.  The best ever was 533,320.  Runs reach 437,959,
and brkhalf reached 413,954.

So the beam never produces the answer on prob_1; it produces a starting point, and the repair
operators close the last 20%.  And ax5, whose constructions are the WORST of the six by a wide
margin -- median 1,033,770 against ax0's 946,574 -- gives the BEST final answer.  Construction
quality does not predict run quality here; it is inversely related across these six points.

## WHAT THIS INVALIDATES, INCLUDING MOST OF TONIGHT'S REASONING

I modelled a WSTAT draw as "a min over ~12 constructions" and concluded the lever was buying more
of them -- more rounds, more workers on the winning config, PARROUND.  That model is wrong.  The
constructions are not draws from the answer distribution; they are seeds, and 251 of them never
once landed where the run lands.

It also explains, in one mechanism, three separate dead ends measured tonight:

    round 0 saturates at 155 s (248 samples)     the construction finishes in ~8 s; the rest of
                                                 the round is operator time, and the operators
                                                 saturate
    the 73 s fill round moves 4% (53 samples)    a short round buys another seed, not another
                                                 answer
    more rounds lose, parity read inverts        same reason, plus a shorter round reads worse

## WHAT IS ACTUALLY OPEN

Which axis produces the most IMPROVABLE seed, not the best seed.  ax5 is the candidate and it has
one replicate.  The measurement to make is per-axis (construction -> final) improvement, which the
DRAW lines plus the run outcome already support.
