# Rate mode: three versions, a proved mechanism, and a negative result

## What it was for

The same build, the same instance and the same budget disagree with themselves by 2.5-25%.  Every
RNG in this project is constant-seeded, so two runs differ in exactly one input -- `time.time()` --
and the beam turns that input into its width at every one of ~250 levels:

    per  = elapsed()/work ;  left = time_budget_s*AIM - elapsed() ;  Bcur = left/(per*rem)

`Bcur` decides what the next level costs, which moves the clock, which picks the next `Bcur`.  That
feedback loop is the amplifier.  `OGC_WORKCAP` removes it completely and cannot ship, because the
competition budget is wall clock.  Rate mode was the attempt to keep the clock for the SIZE of the
search and take it out of the SHAPE.

## Three versions, three replicates per arm, 60 s, both arms on the same fresh binary

    version                             P20                          P1
    v1  arm from every beam    spread 0.55->0.00%  mean -2.88%   3.44->26.68%  +6.12%
    v2  arm only if slice-bound       0.94->0.79%       -3.47%   2.42-> 0.00% +11.00%
    v3  width controller only         4.46->3.22%       -0.23%  18.65->21.24% +25.36%

## What is established

**The mechanism is real and removable.**  v2 returned 682,888 on prob_1 three times to the digit,
and 8,924,228 on prob_20 three times to the digit in v1.  A search whose spread is 2-4% run to run
became exactly repeatable.  That is not a small claim and it is measured.

**Every version that removes the noise also changes the search, and the change costs more than the
noise.**  In v1 and v2 the work cap is also the stop test, so it decides WHEN the beam stops: on
prob_1 it stops too early and every beam exits through the salvage path with a rolled-out partial
instead of completing its levels.  Deterministic, and 11% worse.

**Restoring the stop test does not rescue it.**  v3 leaves the clock in charge of stopping and gives
the work cap to the width controller alone.  But the cap can be exhausted before the clock is, and
the retirement rule that handles that (`_useW=false`, clock takes the tail) puts the clock back into
the trajectory -- so v3 is neither deterministic (P1 spread 21.24%) nor better (P1 +25.36%).  It also
gave up most of v2's prob_20 gain, -0.23% against -3.47%.

## What is NOT established, and why the line stopped here rather than being disproved

The v2 loss has a specific cause -- beams cut short by a cap that was too small -- and a specific
untried fix: the cap is `rate * slice * aim`, and a margin above 1.0 would let a beam that would
have completed still complete, with the wall-clock backstop catching the rest.  That is one knob and
about eight cells to read.  It was not run because the queue it would displace (the axis director,
the scheduled tardiness pass, and OGC_ROUNDS) has direct evidence behind it and this does not yet.

`OGC_WRATE` is unset by default, so none of this is in the shipped path.

## One reading worth keeping from the queue itself

prob_1 at 60 s returned 524,295 in a plain baseline cell, against the 610,000-625,000 those cells
usually give.  The instance has a much better basin reachable inside 60 s, and construction finds it
only occasionally -- which is the case for more draws per budget (`OGC_ROUNDS`) rather than for a
better-behaved single draw.
