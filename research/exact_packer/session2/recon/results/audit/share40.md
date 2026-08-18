# Restarting a hopelessly-behind worker: stopped at 23 of 80 runs

A worker more than 50% behind the best other rebuilds from a fresh seed, once, between 30%
and 60%% of its budget.  The mechanism works -- every restart hit a worker 1.5x or more
behind the leader, and on the P7 confirmation run the restarted worker went from 3,254,019
to 1,738,762.  What it does not do is move the set.

```
inst           fixed         share    change
P1           470,530       470,530    +0.00%
P2        59,488,787    59,489,611    +0.00%
P3         4,435,497     4,471,163    +0.80%
P4         2,775,626     2,723,328    -1.88%
P5         7,688,772     7,797,298    +1.41%
P7         1,128,124       953,242   -15.50%
P13       68,172,643    67,363,586    -1.19%
P20        8,908,086     8,908,086    +0.00%
P22            5,378         6,061   +12.70%
P25       69,659,489    70,175,674    +0.74%
P36       73,339,019    76,712,212    +4.60%

  11 pairs   3 better / 6 worse / 2 identical   median +0.00%   mean +0.15%
```

## Why it was stopped at 23 of 80

The restart fired 3 times in 23 runs.  Whatever it is worth when it fires, it can touch
at most that fraction of the set, so it cannot produce a broad improvement -- and the
measured direction is not even positive.

The instances it never touched are the informative ones.  P1, P2 and P20 returned the same
value in both arms: no restart, deterministic run.  P5 (+1.41%), P25 (+0.74%) and P36
(+4.60%) moved with no restart either, which is by definition unrelated to the feature and
therefore the noise floor.  The overall median sits inside it.

Kept behind OGC_SHARE (default off).  The channel itself -- one file per worker, each
writing only its own, torn reads treated as no information -- is sound and reusable if a
later idea needs workers to see each other.
