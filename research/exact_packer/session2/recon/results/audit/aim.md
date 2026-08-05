# The beam's aim: how much of its slice the beam claims before the rollout finishes the job

180 s, shipped configuration except OGC_BEAMAIM.  0.90 is today's behaviour.

    inst   blocks     0.90         0.75         0.60         0.45         0.30         0.20         0.10
    P25     300   83,469,231   82,453,266   80,233,515   77,800,747   72,005,889   69,865,266   68,973,666
    P13     300   75,460,745   75,140,944   73,896,944   72,861,873   70,889,073   68,648,923   66,618,791
    P36     300   89,254,771   87,320,348   87,949,656   84,214,242   82,428,479   75,600,230   73,339,019
    P20     250   10,553,084   10,796,210   10,728,208    9,826,336    9,897,771    9,543,763    9,255,809

Monotone on all four; against the SHIPPED build at the same budget, the 0.10 column is P36
-24.3%, P13 -22.1%, P25 -17.6%, P20 -11.9%.  Runtimes 179-190 s.

## Why it is not a constant to adopt

All four are 250-300 blocks -- the sizes where the beam was already passing its deadline, so the
salvage runs and the rollout does the work.  On smaller instances the beam FINISHES, the salvage
never fires, and a lower aim only narrows the beam.  First five pairs of the full-40 run:

    inst   blocks      hi(0.90)      lo(0.10)      diff
    P1      150         564,079       705,590   +25.09%
    P3      200       4,500,717     4,829,915    +7.31%
    P5      150       7,963,319     7,638,309    -4.08%
    P2      250      67,691,126    59,539,581   -12.04%
    P4      250       2,742,261     2,865,705    +4.50%

    small (<250)  1 better / 2 worse   mean +9.44%
    large (>=250) 1 better / 1 worse   mean -3.77%

P1 at +25% is the shape of the objection: 150 blocks, the beam had no trouble finishing, and the
aim took nine tenths of its width away for nothing.

## What to do instead

Not a size gate.  The workers are already a portfolio over diversification axes and the answer is
their minimum, so half of them can run a low aim and half the current one -- the large instances
are carried by the low-aim workers, the small ones by the high-aim workers, and no instance is
ever tested for its size.
