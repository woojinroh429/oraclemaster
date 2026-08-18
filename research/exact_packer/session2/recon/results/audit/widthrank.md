# prob_1's AXIS RANKING IS A (WIDTH, K) RANKING, AND ONE AXIS IS INSENSITIVE TO WORK ENTIRELY

Deterministic, one answer per (axis, work), placement digests printed.

    axis  Bmul/K   B/K used      w1500       w3000       w6000      w12000
    2     0.7/5     67/5       686,238     684,687     573,634        ...
    3     0.7/5     67/5       823,207     737,578     727,038        ...
    0     1.0/4     96/4     1,569,183   1,174,681   1,243,617   1,121,887
    4     1.4/3     96/3     1,487,811   1,403,609   1,280,565        ...
    1     1.0/4     96/4     1,323,041   1,323,041   1,323,041   1,323,041
    5     0.5/6     48/6     1,628,890   1,350,271   1,464,281        ...

## THE ORDERING IS (B, K), NOT THE FIELDS THE AXES WERE DESIGNED AROUND

The top two are the only two sharing 0.7/5, and third place is 1.7x behind them.  Yet axes 2 and 3
differ in nearly everything else the table does not show:

    axis 2   order=lst   pos_lam 0.15   fut_beta 0.0   w3mul 3.0
    axis 3   order=edd   pos_lam 0.05   fut_beta 1.5   w3mul 1.0

Whatever they share that wins, it is not order, not pos_lam, not fut_beta and not w3mul.  What
they share is the width and the branching factor.

OGC_AXSET=bk67 is the direct test: give every axis Bmul 0.7 and K 5, change nothing else, keep all
six orders and weights.  If the six converge on the winners' scores, the axis policy question was
a two-number question all along.

## AXIS 1 RETURNS THE SAME PLACEMENT AT EVERY WORK LEVEL

    w1500  w3000  w6000  w12000     obj 1,323,041 and digest 89db34b8dbfdfe48 at all four

An eightfold range of work, and the placement is identical to the byte, while the wall time goes
11.6 s -> 22.4 s -> 44.5 s -> 91.9 s.  So it is not stopping early: it spends the work and arrives
at the same answer.

That is the myopic-proxy story stated as a measurement.  The width controller turns a larger
budget into a WIDER beam rather than a longer one; a wider beam ranks more states by the same
proxy, and if the proxy's preference order is stable then more width changes nothing at all.  On
axis 1 it changes nothing at all.

It also means "give the draw more work" is not one lever with one sign.  Over 1,500 -> 6,000:

    axis 2   -16.4%      axis 3   -11.7%      axis 4   -13.9%
    axis 5   -10.1% but non-monotone (worse at 6,000 than at 3,000)
    axis 0   -20.7% but non-monotone (worse at 6,000 than at 3,000)
    axis 1     0.0%, digest-identical

I called this lever dead twice tonight, once from axis 1's flatness and once from axis 0's
non-monotonicity, and axis 2 refuted both.  The shape is per-axis and no single axis settles it.
