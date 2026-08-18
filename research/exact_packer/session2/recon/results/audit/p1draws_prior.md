# THE DRAW PROBABILITY p1lottery.md USED IS 3.5x TOO HIGH, AND THE RECORDS ALREADY HELD THE FIX

No new runs.  The axis phase of p1draws.sh left 14 runs x 4 workers = 56 round-0 draws on training
prob_1 at 240 s with WORKERS=4 -- the same conditions p1lottery.md characterised from 24.

    quantity              p1lottery (24 draws)    this reading (56 draws)
    min                        422,629                 422,629
    p25                        489,878                 486,096
    median                     571,400                 650,024
    p75                        722,186                 735,244
    P(draw <= 450,000)            0.25                    0.071

The median is 13.8% worse and the tail probability is off by 3.5x.  24 draws was not enough to
place a 7th-percentile threshold.

## WHAT THAT DOES TO THE ARITHMETIC THE WHOLE P1 ARGUMENT RESTS ON

p1lottery.md wrote, from p = 0.25:

    4 draws   P(some draw <= 450,000) = 1 - 0.75^4 = 68%
    8 draws                            = 1 - 0.75^8 = 90%

From p = 0.071:

    4 draws   26%      (observed over the 14 runs: 29%)
    8 draws   45%
    16 draws  69%

THE INDEPENDENCE MODEL ITSELF CHECKS OUT, which is the part that matters.  Predicted against
observed run minima over the same 14 runs:

    T = 450,000   predicted 0.26   observed 0.29
    T = 470,000   predicted 0.54   observed 0.57
    T = 500,000   predicted 0.76   observed 0.71

So draws behave as independent samples and the count converts into probability exactly as the
lottery framing assumed.  What was wrong was the ticket price, not the mechanism.

## WHICH MAKES R=2 WORTH MORE, NOT LESS

The shipped structure buys four long draws and hits 450,000 about a quarter of the time, not two
thirds.  Doubling the draw count takes that to 45% -- a larger absolute gain than p1lottery
predicted, because 0.26 has more room above it than 0.68 does.

The condition is unchanged: a 120 s draw must come from the same distribution as a 228 s one.
shortdraws.md measured 155 s and 228 s as identical over 248 samples, so the saturation point is
below 155 s; whether it is below 120 s is exactly what R=2 reads.

## AND THE SWEEP HAD TO BE PINNED TO WORKERS=4

The shipped default gates to three workers at timelimit <= 240, so the first resumed R=1 cell came
back `WSTAT round=0 n=3`.  Every comparison target -- these 56 draws, shortdraws.md's 248, and the
four submitted entries -- is four workers.  harness/p1draws.sh now pins WORKERS=4 for the rounds
phase.
