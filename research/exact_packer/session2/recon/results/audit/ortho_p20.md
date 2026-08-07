# Replacing the axis list loses, and the loss tracks how many axes were removed

prob_20, 240 s, one draw per arm.  base is the shipped six.

    arm    axes  obj           vs base   workers                                    spread
    base    6    8,854,193       --      10922434  8973869 11372627  8862263        28.3%
    o5      5    9,918,731     +12.0%    (see log)
    o4f     4   10,161,450     +14.8%    12124144 10666398 12534316 10170147        23.3%
    o4      4   10,417,619     +17.7%    11568249 10934950 10862050 10417619        11.1%

Two things read off this directly.

The damage tracks the count: six, five, four, four maps to 0, +12.0, +14.8, +17.7.  And no arm put
a single worker anywhere near base's good pair at 8.86M and 8.97M -- o5's best worker is more than
10% above them.  Swapping the shape signal from aspect to box fill moved 2.9%, so the loss is not
about which shape measure was used.

## Where the reasoning went wrong

axes_structure.md counted the viewpoints correctly -- three distinct orders across four opening
slots, with defer_big holding three -- and then treated "duplicate viewpoint" as "wasted slot".
That step was inference, not measurement, and prob_20 says it was wrong.  The three defer_big
entries share an order but not a search:

    axis 0   Bmul 1.0   pos_lam 0.10   w3mul 1.0   cohort 0.0
    axis 1   Bmul 1.0   pos_lam 0.12   w3mul 3.0   cohort 0.3
    axis 5   Bmul 0.5   pos_lam 0.20   w3mul 1.5   cohort 0.0

Beam width differs by 2x and the preference multiplier by 3x.  Same dispatch sequence, different
search.  The name was the only thing that was duplicated.

## Also void: the 60 s smoke

The o4 smoke on prob_20 at 60 s showed worker spread 55.1% against a base that runs 19-30% there,
and that was read as the mechanism working.  At 240 s the same arm's spread is 11.1% -- narrower
than base, not wider -- and the objective is 17.7% worse.  A single 60 s draw did not even get the
direction right.

## What a safe redesign looks like

Not replacement, and not a seventh axis either (newaxis measured appending one at -10.8% on P1).
What is left is a single opening slot: with nw = 4 the live wids are 0..3, so axes 4 and 5 are
already reserve entries that never open a run.  Moving one shape axis into an opening slot and the
displaced axis into reserve keeps the count at six, changes one worker's opening axis out of four,
and costs at most that worker's draw if the shape signal is bad -- the minimum protects the rest.

Not yet established: this is one instance and one draw per arm.  The queue continues across the
other eleven before the count effect is treated as general.
