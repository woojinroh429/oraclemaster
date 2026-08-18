# WHERE THE NIGHT ENDED UP

## CLOSED, WITH EVIDENCE

    brk                     NEUTRAL on prob_1 over seven paired replicates (+0.16% over three in
                            brkcal, -1.90% over four in brkhalf).  On prob_16/24/20 it reports gain
                            0 on 126 worker-rounds, before AND after the calibration fix, so there
                            it is pure cost.  One paired gain survives anywhere: prob_3, -2.55% and
                            -0.17%, both draws under both controls.
                            The -6.52% that justified shipping zip D was a draw.

    BRKPAR=half             REFUTED at n=4, +7.99% against off.  (wid//2)%2 cuts ACROSS the
                            configuration axis, so on prob_1 it spends a brk slot on config B --
                            which has never gone below 516,577 in 540 draws.

    more rounds / draws     CLOSED.  The parity-directed fill round already buys four extra
                            config-A draws and moves the answer 2 times in 53.  Round 0 length 155s
                            and 228s give the same draw distribution over 248 samples.  At 40s
                            rounds prob_1's parity read INVERTS, so PARROUND misfires exactly where
                            short rounds live.

    axis pinning            NEGATIVE in production.  No pinned axis beats the rotation (best mean
                            ax1 446,028 vs rot 461,233, inside a 5-25% replicate spread), and the
                            night's best value, 413,954, came from the rotation.

## THE MODEL I HAD WAS WRONG, TWICE

A WSTAT draw is not one construction: each worker runs 8-13, rotating six axes.  And those are not
independent seeds either -- work_mode.md shows at most six distinct answers per work level, the
rest being clock perturbation.  Both halves of "buy more seeds" were structurally dead before I
measured them.

## THE NUMBER THAT REFRAMES EVERYTHING

    one construction, prob_16 axis 2, work 6,000, 32 s, ONE core    2,477,998
    the full run, 240 s x 4 workers = 960 core-seconds              2,469,078

The entire pipeline is worth 0.4% over a single good seed.  Every arm measured tonight moves
seconds INSIDE that 0.4%, which is why they all landed in the noise -- the space is small, not the
noise large.

Meanwhile choosing the axis at fixed work is worth 2.3x on prob_1 and 2.6x on prob_16, and the
ordering is by (B, K): the two 0.7/5 axes are first and second on both instances at every work
level tested, reproducing an earlier session's numbers to the digest.

## OPEN

    bk67          does the (B,K) advantage reach the SCORE?  Running now.  It may not: pinned
                  axis 2 is already 67/5 and finished sixth of seven in production.
    beamquits     the beam uses 49% of its allowance (median over 520 draws); 78% of draws use
                  under 60%.  The run declines compute rather than spending it badly.
    beamprod      beam1 is the fine rung alone; production's _beam_once is two rungs with a
                  reserve.  Until that gap is closed the deterministic table cannot be read as a
                  statement about production.

## WHAT I WOULD SUBMIT RIGHT NOW

Zip B, the one already chosen, or C.  NOT D on the strength of anything measured tonight: D ships
brk on, and brk is neutral where it was supposed to win and costs where it provably finds nothing.
D is not harmful -- its measured effect is inside noise everywhere -- but the reason given for it
did not survive.
