# 12TH ENTRY: BEST TOTAL EVER, AND P1 IS A MEDIAN DRAW RATHER THAN A REGRESSION

Submitted 2026-08-10 18:55 UTC.  The build is the gated one -- myalgorithm.py md5
45b7127a0b58df726fd5a343582ecd6e, carrying `nw = cpu-1 when cpu >= 4 and timelimit <= 240`.

    instance          1st           2nd           3rd          12th     rank
    P1          3,068,862     3,328,237     2,847,060     3,018,944     2/4
    P2         19,829,534    20,337,489    20,063,787    19,034,370     1/4   best ever
    P3          5,886,589     5,867,652     5,613,271     5,802,412     2/4
    P4          4,421,375     4,283,430     4,681,440     4,200,264     1/4   best ever
    P5          6,308,099     6,104,015     6,148,480     6,061,204     1/4   best ever
    P6          1,024,046     1,053,770       968,674       973,403     2/4
    P7         16,385,030    16,285,457    16,310,765    15,976,842     1/4   best ever
    P8         17,079,881    16,023,014    17,347,930    17,897,845     4/4   worst ever

    total      74,003,416    73,283,064    73,981,407    72,965,284     -0.43% on the previous best

Four of eight are all-time bests and the total is the lowest of the four recorded entries.

## P1 IS NOT DOWN, IT IS MIDDLE

Every P1 value on record, sorted:

    2,685,759  2,847,060  3,009,531  3,018,944  3,051,204  3,068,862  3,185,928  3,328,237

The 12th sits just below the median of 3,051,204.  Values at or under 2,850,000 have happened
twice in eight entries -- one in four, not "often".  The 7th's 2,685,759 remains the best ticket
ever drawn and has not recurred in five subsequent entries.  This is the 18.6% band p1lottery.md
described, and a single entry lands wherever the draw lands.

## WHAT THIS ENTRY CANNOT SETTLE

ONE DRAW PER INSTANCE.  Four all-time bests and one all-time worst are eight samples from eight
distributions, and the same build resubmitted has been measured at median -0.07% with a range of
-5.16% to +8.66%.  Nothing here separates the gate from the lottery.

AND IT IS NOT KNOWN WHETHER THE GATE FIRED AT ALL.  Finals time limits are per-instance and
unpublished (techreport_ko.md section 4).  Above 240 s the gate is inert and this build is byte
for byte the previous one, in which case every movement above is luck.  There is no WSTAT in the
submission output to check against.

    fix available: have the submitted build record the timelimit it was handed, so the next entry
    answers this instead of leaving it open.

## WHAT WOULD ACTUALLY MOVE P1

The band is a draw distribution, so it moves only if the distribution moves.  Measured today on
finals prob_1 at 240 s:

    config B has never produced a draw under 450,000 in 388 tries -- one worker in four is inert
    deleting it (WORKERS=3) lifts each config-A draw from p = 0.273 to 0.344
    adding a config-A worker instead is an exact wash: p falls to 0.200, three tickets at 0.200
      compounding to what two at 0.273 already gave
    a config-A worker WITHOUT the direction (order=lst, w3mul=0.5) draws 2.03x worse

The direction is the only factor found that moves a draw by more than single digits, and it is two
settings at once.  harness/p1dir.sh is separating them.
