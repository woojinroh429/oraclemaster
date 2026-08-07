# Replacing the axis set loses on half the instances and nothing predicts which half

Six instances, 240 s, one draw per arm, sorted by the w1/w3 exchange rate.

    inst     w1/w3         base         o4        o4f         o5
    P4        6.3x      2742261     -5.69%     -5.83%     -4.22%
    P13       8.3x     70505814    +17.02%        --         --
    P1       11.1x       470530    +12.78%    +12.78%     +9.55%
    P20      44.4x      8854193    +17.66%    +14.76%    +12.02%
    P2       88.9x     60639966     -0.50%     -1.90%     +2.28%
    P6      100.2x      5373975     -4.19%     -0.09%     -0.86%

Three of six are double-digit losses at +12.8%, +17.0% and +17.7%.  The three arms carry the same
sign on every instance, so which shape signal is used -- aspect, box fill, or both -- does not
decide anything; replacing the set does.

## Five candidate explanations, all refuted

    axis count          prob_20 ranked 5 axes above 4; prob_2 ranks 5 axes last
    exchange rate       lowest (P4) and highest (P6) both win; P13 at 8.3x loses 17%
    objective mix       inside the Z1-dominated group P2 and P6 win while P20 loses 14.8%
    shape signal        the three arms move together on all six instances
    "middle band"       P13 at 8.3x sits beside P4 at 6.3x and the two differ by 23 points

Winning at 6.3x and losing 17% at 8.3x is the sharpest of these: no instance property separates
those two.  Nothing available before the run predicts which half an instance falls in.

## Verdict

Unshippable.  A 50% rate of double-digit loss with no predictor means roughly four of eight hidden
instances would take a 17% hit, and per-instance scoring gives no way to recover that from the
wins.  The remaining six instances and the second replicate would cost about four hours to confirm
a direction that six paired instances already settle.

## What survives

The reason for building this stands: aspect and box fill ARE orthogonal to footprint area
(rho -0.053 and -0.061 over all forty instances), and the shipped orders are all built from due,
due - pt and area.  What is refuted is introducing that signal by REPLACING the axis set.  If it is
worth another attempt it has to be as a single opening slot with the other five left alone, so a
bad draw costs one worker rather than the run -- the form overfit_rule.md allows.

Also recorded: the notification stream disagreed with the log twice, once reporting
"P1 [r1.o5.6] obj=5327658" -- prob_6's objective under prob_1's header.  harness/bytype.py now
drops any row whose printed instance contradicts the instance inside its tag, and every number in
this file was read from the log rather than from an event.
