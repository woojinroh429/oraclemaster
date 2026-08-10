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

## CORRECTION: PAIRING BY WORKER MEASURES THE MEDIAN, AND THE SCORE IS THE MINIMUM

harness/pairw.py was added tonight to get four observations per cell instead of one, by pairing an
arm against its control worker by worker.  That is four times the data and it does cancel
between-run variance -- but the statistic it produces is a count of per-worker wins, which tracks
the MEDIAN worker.  The objective is a minimum over workers.

An arm that lifts the median while lowering the minimum scores well on that count and badly on the
scoreboard.  The file already knew this and says so at the polish-reserve note:

    "the median worker improved and the minimum got worse, so the arm goes the wrong way" -- the
    argument used, correctly, to reject OGC_BEAMCAP

which is exactly the arm pairw ranked second (cap20 +29% over 24 pairs, cap12 +17%).  The screen
was reading the rejection reason as a recommendation.

So the pairw numbers -- lst +25% over 80 pairs, cap20 +29%, cap12 +17%, share +33% -- are not
adoption evidence and are biased in a known direction for this objective.  Nothing was adopted on
them: both packaged builds rest on direct minimum comparisons over replicates.

What pairw is still good for: arms that cannot change the between-worker spread, i.e. ranking
knobs applied identically to every worker.  It is wrong for anything that changes pool
composition, worker configuration, or draw width.
