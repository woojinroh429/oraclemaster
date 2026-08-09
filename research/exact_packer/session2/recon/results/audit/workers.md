# WHICH HALF OF THE POOL ANSWERS, PER INSTANCE

Collected from every `WSTAT round=0` line this project has logged, paired with the objective line
that follows it.  For each run: which worker index held the minimum, and how far behind each worker
sat relative to that minimum.  n is the number of runs, not the number of cells.

    inst      n     even (w0+w2) wins   odd (w1+w3) wins
    prob_1    200        92%                  8%
    prob_16   180        20%                 80%
    prob_20   156         6%                 94%
    prob_26    61        21%                 79%
    prob_30    56        20%                 81%
    prob_24    35        20%                 80%
    prob_36    18         0%                100%

    mean deficit against the winning worker
    prob_1     w0  5.3%   w1 36.5%   w2 10.3%   w3 41.4%
    prob_16    w0 22.9%   w1  6.9%   w2 28.3%   w3 18.6%
    prob_20    w0 21.1%   w1  3.2%   w2 22.8%   w3  3.4%

## WHAT THE SPLIT IS

`wid % 2` carries three knobs at once, so the pool holds TWO configurations, two workers each:

    even (w0, w2)   OGC_MCAND=1   OGC_ORDER=lst   OGC_W3MUL=0.5   aim[0]
    odd  (w1, w3)   OGC_MCAND=2   axis defaults                   aim[1]

## THREE THINGS THIS EXPLAINS

1. THE PORTFOLIO IS EARNING ITS PLACE.  The even configuration exists for prob_1 and essentially
   nothing else; the odd configuration answers every other instance measured.  That is the
   "never loses, sometimes wins large" profile the m-portfolio and dir2 were adopted on, and this
   is the table behind it.  Neither half can be deleted.

2. HALF THE POOL IS WASTED ON EVERY RUN, AND WHICH HALF IS NOT KNOWABLE IN ADVANCE.  On prob_20 the
   even pair spends the full budget 21-23% behind and wins 6% of the time; on prob_1 the odd pair
   spends it 36-41% behind and wins 8%.  Every attempt this project has made to "drop the useless
   operator" has failed for this reason: the useless half is instance-dependent, so it can only be
   identified at run time.

3. IT EXPLAINS WHY THE KNOB SWEEPS READ AS NOISE.  The answer is a minimum over four draws, but it
   comes from ONE pair in ~90% of runs, so the effective sample is two.  A knob the winning pair
   cannot hear -- OGC_THRUHZ on prob_1, where the m=1 half wins and m=1 makes wb_hz1 nearly constant
   across a level's children -- has an effective sample of zero.  Three multipliers returned
   bit-identical objectives there.

## WHAT FOLLOWS

The deficits are the reason OGC_SHARE exists: a worker more than OGC_SHAREGAP behind the best other
worker abandons its basin and restarts.  The measured deficits are 21-41%, and the shipped gap is
0.5, so on the instances above the mechanism NEVER FIRES.  That is what the sharerate queue tests:
gap 0.5 against gap 0.3, six replicates on prob_1, then a no-harm pass on the instances the odd
pair owns.
