# The final instance set, by the properties that change what the algorithm sees

Read straight from data/stage2.  `maxOr` is len(block['shape']); `%>=3L` is the share of
blocks whose layer-0 orientation has three or more layers; `tight` is the share with
due - release - processing <= 0, i.e. blocks that cannot be on time however they are placed.

```
  p   nb  maxOr  %>=3L     w1  w2    w3  w1/w3  tight%
  1  150     12   0.0    6667   3   600   11.1   12.7
  2  250      8   0.0   13333   4   150   88.9   11.6
  3  200     12   0.0    3333   7   533    6.3    5.5
  4  250     12   0.0    3333   5   533    6.3   14.8
  5  150      8  64.0    3333   9   400    8.3    8.7
  6  250      8   0.0   13333   5   133  100.2   19.6
  7  150      8   0.0   13333   7   150   88.9    7.3
  8  200      8  62.0     333   1    27   12.3   17.5
  9  200      8   0.0    6667   2   600   11.1   14.5
 10  150     12   0.0   13333   4   200   66.7   17.3
 11  250      8   0.0   13333   3   267   49.9   25.6
 12  300      8   0.0     333   1    25   13.3   19.7
 13  300      8   0.0    6667   1   800    8.3   14.3
 14  250      8   0.0     333   1    27   12.3   16.4
 15  250      8  64.8    6667   2   600   11.1   14.4
 16  300      8   0.0   13333   3   250   53.3   15.0
 17  250      8   0.0    3333   8   300   11.1   12.4
 18  200      8  64.5    3390   5   600    5.7   13.0
 19  200      8   0.0   13333   2   300   44.4   12.0
 20  250      8   0.0    6667   8   150   44.4   26.4
 21  150     12   0.0   13333   2   400   33.3   24.0
 22  150      8   0.0     339   1    30   11.3   18.0
 23  300      8  69.3    6667   3   500   13.3   14.7
 24  150      8   0.0    3333   7   600    5.6   14.7
 25  300      8   0.0    6667   4   200   33.3   14.7
 26  300      8   0.0    6667   1   800    8.3   21.3
 27  200     12   0.0    3333   7   533    6.3   14.0
 28  250      8   0.0   13333   5   133  100.2   14.4
 29  200      8   0.0     678   1    13   52.2   16.5
 30  300      8   0.0   13333   6   125  106.7   24.0
 31  200     12  65.0    6667  10   150   44.4   21.0
 32  200      8   0.0     667   1    13   51.3    9.0
 33  150     12   0.0    6667   9   200   33.3   20.0
 34  300      8   0.0   13333   6   125  106.7   19.7
 35  250     12  66.0     333   1    27   12.3   16.4
 36  300      8   0.0    6667   1   800    8.3   16.0
 37  150      8   0.0    6667   9   200   33.3   12.0
 38  200     12  62.5   13559   3   267   50.8   10.0
 39  150      8  73.3   13333   2   400   33.3    6.7
 40  300      8   0.0    3333   2   800    4.2   26.0
```

Twelve orientations: 10 instances -- [1, 3, 4, 10, 21, 27, 31, 33, 35, 38].  The rest have eight, and no instance
mixes the two: the property is per-instance, not per-block.  The preliminary set had none
above eight, so this is a family the preliminary tuning never saw.

Three-or-more layers: 9 instances -- [5, 8, 15, 18, 23, 31, 35, 38, 39] -- at 62-73% of their blocks, and 0% in
every other instance.  Bimodal in the same way.  The preliminary set was 37% of blocks at
three or more layers overall; here it is 13.9%, so the profile did not shrink evenly, it
concentrated into a ninth of the instances.

## Why the weight column is here

The two instances that lost by more than 10% under the aim portfolio, P7 and P22, are both
150 blocks -- the smallest tier -- but they sit at opposite ends of the weight ratio: P7 has
w1/w3 = 88.9 and P22 has 11.3.  Nothing in the instance data separates them from the
fourteen small instances that won, which is the reason replicates were run rather than a
safeguard designed.
