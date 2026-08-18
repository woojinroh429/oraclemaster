# Removing brk is safe and quality-neutral on the training set

The submission build unregisters bayrepack's operator by default (OGC_BRK=1 restores it).  The
question before shipping was not "is it better" -- that is what the hidden set is being asked --
but whether it can lose badly.  Six paired instances at 240 s, spanning the full w1/w3 exchange
rate range, same build with only the operator toggled.

    inst     w1/w3        withbrk          nobrk     delta
    P4        6.3x        2621290        2621290    +0.00%
    P13       8.3x       68409114       67837347    -0.84%
    P26       8.3x       24715400       24559522    -0.63%
    P20      44.4x        9449113        9449113    +0.00%
    P2       88.9x       60515077       60722175    +0.34%
    P6      100.2x        5124123        5237234    +2.21%

    n=6  median +0.00%  mean +0.18%  better 2 / worse 2 / tie 2  worst +2.21%

Every run feasible, no hang, no crash.  The worst case is +2.21% against +17.7% for the axis-set
replacement and +5.69% for raising the w3mul grid, both measured today.

The prob_6 pair is not clean: its withbrk draw at 5,124,123 is the lowest prob_6 value on record
across six draws, while nobrk's 5,237,234 repeats an earlier draw exactly.  The arm got a typical
value and the control got a lucky one.  The number stands as measured.

## What brk was actually doing

It works, but mostly where it cannot help.  On prob_4 removing it cost the LOSING workers 1.7-4.7%
while the minimum-producing worker was unchanged to the digit -- so its gain never reached the
answer.  Two of six pairs are byte-identical for that reason.

Twice it appears to have hurt by removing diversity.  On prob_13 with brk, workers 1 and 3 both
returned exactly 68,409,114; without it they separated to 67,851,879 and 69,187,075, spread went
11.9% -> 17.6%, and the minimum fell 0.84%.  That is the same direction w3mul_dynamics.md found
over four grid settings: wider workers, better minimum.

## What this does not establish

That brk is worthless.  Six pairs with a median of exactly zero cannot separate a small positive
from a small negative, and the training set is not the hidden set -- the whole point of shipping
this build is that the hidden instances are a different problem (1.8x median density, ten over
capacity, preference worth 3.6x more relative to tardiness).  What it establishes is that the
build is safe to submit and that whatever the hidden scores show is not going to be explained by
brk alone: this submission also carries the segfault fix, the bounded pool wait and the scored
fallback, none of which were in the fourth submission.
