# The A/B logs were scored across two different problems at once

results/audit/objmix.json classifies all 40 stage-2 instances by what their objective is made of:
30 are 60%+ tardiness, 8 are 60%+ bay preference, 2 are mixed.  P34 has Z1 = 0 exactly; P2 has
Z1 = 98%.  Those are different optimisation problems sharing a solver.

Every A/B this session pooled them and counted wins.  harness/bytype.py re-reads the same logs --
nothing re-run -- asking the question inside each class.

## The cleanest case: aimset, 60 s, baseline `low` = all four workers at aim 0.10

    pair  (= the shipped 0.90,0.10 split)
      Z1-dom  n=4  median +2.95%   better 0 / worse 4    P6+4.3 P16+2.9 P20+0.0 P26+0.4 P30+5.0
      Z3-dom  n=3  median -2.80%   better 3 / worse 0    P1-15.4 P3-2.8 P12-1.1
      POOLED  n=8  median +0.18%   <- reported at the time as no effect

    spread (= 0.90,0.45,0.20,0.10)
      Z1-dom  n=4  median +2.23%   better 0 / worse 4
      Z3-dom  n=3  median -0.75%   better 2 / worse 1

Every instance agrees with its class and the two classes point opposite ways.  Under a sign test
treating it as one consistent split that is p ~= 0.016, and the `spread` arm reproduces the
direction independently.

Read plainly: on tardiness-dominated instances all four workers at aim 0.10 beat the shipped
split; on preference-dominated instances the split wins.

## The same shape elsewhere in logs already called noise

    b240   lst    Z1-dom 3/3 better (-1.64%)   Z3-dom 0/1 (+0.95%)
    b240   a4     Z1-dom 2/3 better (-1.37%)   Z3-dom 0/1 (+13.15%)
    rounds R2     Z1-dom 2/3 mixed             Z3-dom 0/3 worse, P1 +29.5%

An intervention that helps the tardiness-dominated class hurts the preference-dominated one, and
pooling cancels it.  That is the mechanism behind this session's repeated "arms differ by less
than the same arm differs between draws".

## Why this is usable rather than an observation

The class is not an instance property that has to be guessed or gated on.  It is
prob_info["weights"] multiplied by any solution's Z1/Z2/Z3, and _safe_sequential produces a
solution almost immediately at no cost -- so the classification is free, deterministic, and read
off the instance's own numbers.  OGC_AIMSET is already the knob.

## Limits, stated before anyone builds on it

n = 4 and n = 3.  The aimset queue ran at a 60 s limit and the working budget is 240 s.  P20 is
exactly +0.00%, so the Z1-dom count is really 3 of 4 with one tie.  32 of the 40 instances have
never been through this arm at all.  Confirming it at 240 s across the full set is the next
measurement, and it is cheaper than building anything new.
