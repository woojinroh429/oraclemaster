# SPEND THE LEFTOVER ON THE HALF THAT IS WINNING

## The three facts this is built on

1. `results/audit/workers.md` -- the pool holds two configurations, two workers each, and one of
   them supplies 92-100% of the answers.  Which one is instance-dependent: even for prob_1, odd for
   prob_16 / 20 / 24 / 26 / 30 / 36.  The losing pair spends the whole budget 21-41% behind.

2. The long runs do not use their budget.  Measured over every 240 s run logged:

       prob_1    200 s of 240      16.7% idle
       prob_24   220 s of 240       8.3% idle   (min 203, max 239)
       prob_26   228 s of 240       5.0% idle
       prob_16   239 s of 240       0.4% idle

   The cause is at the fill-round gate: `_need = max(8.0, 0.25*_rb)` with `_rb` about 199 demands
   57.8 s of leftover and 32-40 s exist, so the gate never opens on a long budget.

3. Simply opening the gate buys nothing.  `OGC_FILLMIN=1` caps the gate at 20 s and does open it --
   prob_1 goes from 200 s to 232 s -- and four replicates say the extra 32 s are worth nothing:

       off    422,629   438,791   472,330   492,458     mean 456,552
       fill   438,791   438,791   455,218   492,458     mean 456,312

   Because the fill round repeats the same 2+2 split, so half of the extra time goes back to the
   half that was already losing.

## The move

Run the fill round with all four workers on the parity that WON round 0.

Everything needed is already in place.  `wid` alone decides a worker's configuration and its
diversity:

    os.environ["OGC_BEAMAIM"] = _aims[wid % len(_aims)]      # aim
    os.environ["OGC_MCAND"]   = _ms[wid % len(_ms)]          # m = 1 or 2
    DIRSET=2 applies ORDER=lst, W3MUL=0.5 when (wid % 2) == 0
    rng  = random.Random(1234 + wid)                          # seed
    axes = [_AXES[(wid + i) % len(_AXES)] ...]                # axis rotation

and `_pool_round` builds its tasks as

    tasks = [(prob_info, budget, rnd * nw + i, cwd, 1.0 / nw, share_dir) for i in range(nw)]

So handing the fill round the wid list `{4, 6, 8, 10}` gives four workers that all carry the EVEN
configuration with four different seeds; `{5, 7, 9, 11}` does the same for the odd one.  No C++
change, no new environment variable inside the worker, and `maxtasksperchild=1` already guarantees
each task gets a fresh process that re-reads `OGC_MCAND` into its `static const`.

Round 0 already returns per-worker objectives -- that is what the WSTAT line prints -- so the
winning parity is known before the fill round is built.

## What it is worth if it works

On prob_1 the leftover is 32-40 s against a 199 s round, so roughly a fifth of a round, spent as
four draws of the configuration that wins 92% of the time instead of two draws of it and two of the
configuration that wins 8%.  The minimum is over draws, so this is a strictly better use of the same
wall clock than either leaving the time idle or filling it with the current split.

## What would refute it

The obvious failure is that the losing pair is not useless, only usually useless: its 8% of wins on
prob_1 may be exactly the runs where it lands somewhere the winning pair cannot reach, and a
minimum keeps whichever is lower.  If that is what those wins are, concentrating the fill round
removes the tail that produced the best numbers.  The test therefore reads the same way the share
queue does -- how often the run lands in the 422,629-438,791 cluster over six replicates, not the
mean -- and it must be checked on an instance the ODD pair owns (prob_20, where even wins 6%)
before it can ship, since the mechanism is symmetric and the risk is symmetric with it.

## Ordering

After the share queue, and only if the share queue does not already collect this.  The two overlap:
a restarted laggard is also a redirection of wasted capacity, and if restarts alone close the gap
there is no reason to add a second mechanism that does the same thing at the round boundary.
