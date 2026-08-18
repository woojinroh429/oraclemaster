# THE BUILD THAT SCORED 2.6M ON HIDDEN P1 APPLIED lst AND w3mul=0.5 TO EVERY WORKER

Supplied by the user as "the code that got P1 2.6M, but the other values were nearly ruined".
Its myalgorithm.py, lines 1710 and 1713:

    _o = os.environ.get("OGC_ORDER",  "lst")     # default for ALL workers
    _w = os.environ.get("OGC_W3MUL",  "0.5")     # default for ALL workers

The current build reaches the same two values through OGC_DIRSET=2, which applies them to EVEN
wids only; odd wids keep their axis's own order and w3mul.  So the history is:

    2.6M build     lst + 0.5 on all four workers
    current        lst + 0.5 on two of four

That is the shape of the user's own description.  A setting that wins P1 and loses the rest is
exactly what gets narrowed from "everyone" to "half" -- the present code is already the compromise,
and the 2.6M was bought with the other seven instances.

## AND THIS SESSION'S SWEEP HAPPENS TO CONTAIN THAT CONFIGURATION

w3sweep.sh runs uniform workers with DIRSET=0 and ORDER=lst, so its W3MUL=0.5 cell IS the 2.6M
build's configuration.  On stage2/prob_1 at 120 s it is the worst of six:

    0.25   634,510 / 723,199
    0.50   736,293 / 745,782     <- the 2.6M build's setting, and the only cell with Z1 at 36-42
    1.00   674,831 / 612,876
    2.00   507,871 / 621,353
    4.00   485,500 / 521,903
    8.00   630,180

Hidden P1 and stage2/prob_1 are different instances, so this is not a contradiction.  It is a
warning: the two directions point OPPOSITE ways.  2.6M was obtained by nearly ignoring preference;
this sweep says weight it four times harder.

## THE TRAP TO AVOID IS THE ONE THAT BUILD FELL INTO

Whatever the sweep settles, a value tuned on prob_1 alone can win prob_1 and lose the set -- which
is what "P1 2.6M, the others nearly ruined" means.  So the order of work is: finish the sweep to
find out whether 4.0 is real on prob_1, then price 0.5 against 4.0 across a spread of stage2
instances before touching a default.  Nothing ships on one instance.
