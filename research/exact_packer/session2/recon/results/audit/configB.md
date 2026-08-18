# WORKERS=3 DOES NOT THROW A TICKET AWAY.  IT THROWS AWAY THE ONE THAT NEVER WINS.

The worry raised against the shipped gate was arithmetic: the answer is a minimum over draws, so
three workers buys three tickets where four buys four, and 1-(1-p)^3 < 1-(1-p)^4.  That treats all
four draws as interchangeable.  They are not.

    myalgorithm.py 2693   _aims = [0.90, 0.10]   ->  _aims[wid % 2]
    myalgorithm.py 2779   _ms   = [1, 2]         ->  _ms[wid % 2]

Even wids get aim 0.90 with m=1 (config A), odd wids get aim 0.10 with m=2 (config B).  So:

    WORKERS=4   wid 0,1,2,3   ->   A B A B   two config-A draws, two config-B
    WORKERS=3   wid 0,1,2     ->   A B A     two config-A draws, ONE config-B

Both config-A draws survive.  What the third worker was doing is the second config-B draw, and
shortdraws.md already priced that:

    config B has never gone below 516,577 in 540 draws, against config A's median of 530,650

On prob_1 a config-B draw cannot be a winning ticket -- 516,577 is above every threshold that
matters, and the run's answer is a minimum.  Dropping one costs nothing in tickets and returns its
core to the two draws that can win.  The compounding argument was applied to a pool that is half
inert, and the correction is not that the arithmetic is wrong but that p is not the same for every
slot.

This also predicts what was already observed about two workers: wid 0,1 is A B, which loses a
config-A draw.  w2 was the volatile arm on prob_16 -- widest span of the three, setting both the
instance record and a draw worse than the control.  Same mechanism, one step further.

## AND IT NAMES A BETTER MOVE, AVAILABLE WITH NO CODE CHANGE

`_aims[wid % len(_aims)]` reads a list of any length from OGC_AIMSET, so:

    OGC_AIMSET=0.90,0.10,0.90,0.90   with WORKERS=4   ->   wid 0,1,2,3 = A B A A

Four workers, three of them useful.  shortdraws.md proposed exactly this split -- "making round 0
3+1 instead of 2+2 would take prob_1 from 2 long config-A draws to 3, i.e. P(<= 450,000) from 0.30
to 0.41" -- and shelved it because acting on it required predicting the instance family before
round 0, from a threshold fitted to thirteen points with two known misses.

WORKERS=3 gets part of the same effect WITHOUT that prediction, because dropping the last worker
happens to drop a config-B slot on any instance.  The two are different trades:

    WORKERS=3            2 config-A draws, deeper (1.33 cores each)
    3+1 at WORKERS=4     3 config-A draws, shallower (1.00 core each)

Both are worth measuring in draw-distribution terms, and the second has never been run.
