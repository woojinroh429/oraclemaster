# The "spread law" was an artifact of its own definition.  Withdrawn.

This session reported eight times that worker spread and answer quality move together, and treated
it as the one mechanism that had been confirmed independently.  It is not a mechanism.

    spread = (max - min) / min        and        the answer IS min

One worker drawing low lowers the objective and widens the spread in the same stroke: min is both
the thing being reported and the denominator.  The correlation is forced.

Measured over the 17 instances in results/audit with 5 or more runs:

    rho(spread, min worker)      -0.64      wider spread, better answer -- as reported all session
    rho(spread, MEDIAN worker)   +0.09      nothing

The median worker is not in the definition of spread, and against it the relation vanishes.  A wide
spread means one worker got lucky, not that the search became more diverse.

## What it cost

Every reading built on it has to go back:

    w3grid   raising w3mul "narrows the spread and hurts"
    nobrk    removing brk "widens the spread and helps"
    headroom more budget "converges the workers"
    mcand    m=2 and m3w "win because they widen the spread"

None of those are established.  Some may still be true on their own numbers; none of them are
supported by the spread.

## The replacement

Report min AND the median worker.  A real improvement moves both.  An arm that improves only the
min drew a good ticket with the same lottery.

prob_24 at 240 s, five arms, beam-side:

    arm     min       vs ship     median worker   vs ship
    ship    2,724,873   +0.00%      2,838,115      +0.00%
    m1      2,809,182   +3.09%      2,905,468      +2.37%
    m3w     2,719,686   -0.19%      3,022,940      +6.51%
    m4w     2,822,173   +3.57%      2,894,344      +1.98%
    m6w     2,759,915   +1.29%      2,969,213      +4.62%

m3w is the arm this session called a win.  Its min is 0.19% better and its median worker is 6.51%
worse.  All four arms lose to the shipped build on the median, 4 of 4.

n=1, one instance whose own draw range is about 4%.  But four arms agreeing is harder to get by
chance than one, and the direction is against everything reported today.
