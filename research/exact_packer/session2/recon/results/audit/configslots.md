# HALF OF ROUND 0 CANNOT WIN, AND EVERY POOLED DRAW STATISTIC SO FAR MIXED IT IN

prob_1, 240 s, every round-0 WSTAT line on disk, split by slot.  Configs index on wid % 2, so
slots 0 and 2 are config A (aim 0.90, m=1) and slots 1 and 3 are config B (aim 0.10, m=2).

    WORKERS=4 (A B A B), 194 runs
      config A  388 draws   min 413,954   p25 438,791   median 492,458   P(<=450k) = 0.273
      config B  388 draws   min 516,577   p25 693,359   median 740,964   P(<=450k) = 0.000
      P(run min <= 450,000):  predicted 1-(1-0.273)^2 = 0.47    observed 0.46

    WORKERS=3 (A B A), 10 runs
      config A   20 draws   min 428,809   p25 437,484   median 469,427   P(<=450k) = 0.350
      config B   10 draws   min 619,234                                  P(<=450k) = 0.000
      P(run min <= 450,000):  predicted 1-(1-0.350)^2 = 0.58    observed 0.70

CONFIG B IS 0 FOR 388.  Not rare -- absent.  Its minimum over 388 draws is 516,577, and it never
approaches the threshold the run is decided at.  This independently reproduces shortdraws.md's
540-draw reading, and it means half of round 0 is spending a core on a ticket that cannot pay.

## WHICH SETTLES THE OBJECTION TO THE SHIPPED GATE

The argument against WORKERS=3 was that a minimum over three draws beats a minimum over four less
often.  Split by slot, three workers and four workers hold the SAME NUMBER of useful draws -- two
-- and the discarded slot is a config-B one worth zero.  The trade is not "one fewer ticket for
more depth", it is "the same two tickets, each with a better probability":

    four workers   2 tickets at p = 0.273   ->  0.47
    three workers  2 tickets at p = 0.350   ->  0.58

Twenty draws is still thin on the w3 side and the observed 0.70 over ten runs is above its own
prediction, so the size is not settled.  The DIRECTION no longer has a competing explanation.

## AND IT CORRECTS EVERY p PUBLISHED IN THIS SESSION

    p1lottery.md        0.25    24 draws, pooled across slots
    p1draws_prior.md    0.071   56 draws, axis-pinned, pooled
    w3_draws.md         0.137   772 draws, pooled
    this file           0.273   388 config-A draws; config B is a separate population at 0.000

The first three averaged a live population with a dead one, so they answer no question.  A pooled
p cannot be put through 1-(1-p)^k either, because k is not the number of draws -- it is the number
of config-A draws.

## THE NEXT ARM, AND THE TRAP IN SETTING IT UP

Three useful draws instead of two, keeping four workers.  `_aims[wid % len(_aims)]` takes a list
of any length, but the aim is only half the config: `_ms` indexes wid % 2 over [1,2] separately.
Lengthening AIMSET alone makes wid 3 (aim 0.90, m=2) -- an untested hybrid, not a third config A.
Both lists have to grow:

    OGC_AIMSET=0.90,0.10,0.90,0.90   OGC_MSET=1,2,1,1   ->   wid 0,1,2,3 = A B A A

harness/p1a3.sh runs it.  The comparison it buys, all in the same units:

    four workers, stock    2 useful draws at 1.00 core    p = 0.273   ->  0.47
    three workers          2 useful draws at 1.33 cores   p = 0.350   ->  0.58
    four workers, 3+1      3 useful draws at 1.00 core    p = ?       ->  0.61 if p holds at 0.273

The open question is whether a third config-A worker degrades all three, since they now contend
where two did.  That is readable inside the arm: slot 3 becomes an A draw, so its distribution
against slots 0 and 2 answers it without a separate control.

## TEN-RUN CHECKPOINT ON WORKERS=3, AND THE DECISION QUANTITY CORRECTED

A run's answer is NOT the minimum of its round-0 draws.  w3.r8 drew 487,067 / 652,268 / 499,210
and returned 469,427 -- the fill round and the polish improved on every draw in round 0.  So the
quantity that decides anything is P(FINAL <= T), and P(round-0 min <= T) is only the mechanism
behind it.  Both, at T = 450,000:

    WORKERS=4 (A B A B)   194 runs
      config A draws  388   min 413,954   p25 438,791   median 492,458   p = 0.273
      predicted 1-(1-p)^2 = 0.47      observed P(round-0 min <= T) = 0.46
      FINAL             min 413,954   median 455,218   P(final <= T) = 0.48

    WORKERS=3 (A B A)      15 runs
      config A draws   30   min 428,809   p25 437,484   median 469,427   p = 0.333
      predicted 1-(1-p)^2 = 0.56      observed P(round-0 min <= T) = 0.67
      FINAL             min 428,809   median 437,484   P(final <= T) = 0.73

The median final falls 3.9% and the chance of landing under 450,000 goes from about half to about
three quarters, with the same two config-A slots and each of them 4.7% better at the median.  The
mechanism and the outcome agree.

TWO THINGS AGAINST READING IT AS SETTLED.  Fifteen runs puts 0.73 at roughly 0.45-0.92, which
clears 0.48 only just.  And the best value ever seen on this instance is still w4's 413,954
against w3's 428,809 -- 194 runs against 15, so that is expected, but w3 has not yet reached the
floor w4 reaches occasionally.

## NEXT: THE SAME FOUR CORES SPENT ON COUNT INSTEAD OF DEPTH

    four workers, stock    2 config-A draws at 1.00 core     p = 0.273   ->  0.47
    three workers          2 config-A draws at 1.33 cores    p = 0.333   ->  0.56
    four workers, 3+1      3 config-A draws at 1.00 core     p = ?       ->  0.61 if p holds

WORKERS=3 made two slots better.  3+1 makes it three slots.  Nothing measured so far says which
is worth more, and the open risk is that three A workers contending where two did degrades all
three -- readable from slot 3's distribution inside the arm itself.
