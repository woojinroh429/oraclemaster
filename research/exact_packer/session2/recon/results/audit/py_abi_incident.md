# The interpreter changed under us, and the fallback said nothing

## What happened

`/usr/local/bin/python3` is now 3.11.15.  When the 16-instance late-window sweep ran an hour
earlier it was 3.12.3.  Extension modules carry the interpreter ABI in their filename
(`ogc_fast.cpython-312-x86_64-linux-gnu.so`), so under 3.11 `ogc_fast` and `cranepack` do not
exist as far as the import system is concerned.  `myalgorithm` catches the ImportError and takes
its pure-Python path, which returns a **feasible** solution.

    prob_36  python3 = 3.11, no extensions   obj = 4,023,023,953   Z1 = 603,423   Z3 = 0     feas=y
    prob_36  python3.12, extensions present  obj =    87,632,418   Z1 =  12,516   Z3 = 5,232  feas=y

45x worse, printed in the ordinary format, no warning on any stream.  It was noticed only
because the first line of a replicate study was absurd; a smaller degradation would have been
read as a result.

## What was changed

1.  `harness/run1.py` imports `ogc_fast` and `cranepack` before anything else and **exits** with
    the interpreter version and the ImportError if either is missing.  Measuring the Python
    fallback by accident is now impossible.
2.  Every result line ends with `py3.x`, so a log states the engine it was made on.
3.  Both extensions are built for **3.10, 3.11, 3.12 and 3.13** and committed.  The ABI tag is
    in the filename, so all four coexist and whichever interpreter the container comes back with
    finds a matching one.

## Why (3) also matters for the submission

The algorithm zip shipped the 3.12 `.so` alone.  The rules state the evaluation server does not
compile, and `build.txt` records Ubuntu 24.04 / Python 3.12 as the stated environment -- but if
that were off by one minor version our submission would not have failed loudly, it would have
scored the fallback.  On prob_36 that is 4.0e9 against 8.8e7.  Shipping every ABI costs 3 MB and
removes the failure mode entirely.

## What it invalidated

*   The prob_36 "loss" (+0.69%) that this study set out to investigate.  Two `latewin=0` runs of
    the same instance on the same engine returned 88,211,571 and 87,632,418 -- a spread of
    **0.66%**, the same size as the effect.  The single pair resolved nothing.

*   The prob_34 "win" (-7.67%) already committed.  `_late_by` is `int(w3 * regret / w1)`; on
    prob_34, w1 = 13,333 and w3 = 125, so a block needs a preference regret of 107 for the
    formula to reach even one day, and the largest regret in the instance is 98.  The mechanism
    **cannot fire on prob_34 at all**, so the 225,946 -> 208,624 difference was run-to-run noise
    being read as an effect.  The commit message also has two instances backwards: it says
    prob_31 cannot fire (it can, d = 2) and credits prob_34 with the improvement (it cannot).

One pair per instance cannot resolve a 0.7% effect against a 0.7% spread.  Everything measured
from here uses three replicates per arm.
