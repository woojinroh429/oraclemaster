#!/bin/bash
# THE GATE.  Does brk survive the instances it was not developed on?
#
# NOT LAUNCHED AUTOMATICALLY.  P3 still has open questions and the lock is shared; run this when
# the P3 queues are done, or when someone asks for it:
#
#     nohup bash harness/gate_brk.sh > results/gate_brk.log 2>&1 &
#
# WHAT IS BEING GATED.  On P3, paired against its own control, three reps against three:
#
#     brk   82,180 / 86,550 / 86,550     mean  85,093
#     ctl   96,990 / 106,700 / 106,700   mean 103,463      -17.75%, bands disjoint
#
# That is one instance, and this session has already shown twice how far a P3 result can be from
# a P4 one.  conw=0.0 is the clearest case: the best P3 setting anything produced (87,560) and a
# +25.9% catastrophe on P4, because a saturated instance needs every cell pressed together and
# conw throws tightness away to get a flat packing.
#
# WHY brk SHOULD NOT REPEAT THAT, and why that is a prediction rather than a result.  brk runs
# with conw at 1.0 -- contact at full strength, asserted in the arm -- and takes nothing away
# from the search.  It re-solves an arrangement the greedy pass already committed to, and keeps
# the result only if the real grader scores it better.  On a saturated instance the same
# operator should buy Z1 rather than Z3: a bay that packs better admits blocks earlier, so fewer
# are late.  Nothing in it tests density; the target bay is whichever has the highest
# u_j * load_j AND something that wants to enter.
#
# But it has never run on a saturated instance, and two things could still go wrong:
#
#   COST   cranepack does not respect its time budget -- 120 s asked, 18 minutes taken, measured
#          at grid step 2 on P3.  The operator now sizes the problem to an OBSERVED took/asked
#          ratio, but that ratio was learned on 200 blocks in a 989-cell bay.  P6 has 250 blocks
#          and a 900 s budget; P5 has four bays.  If the sizing rule does not hold there, brk
#          eats the run.
#   VALUE  on P3 the objective is a pure function of the assignment (Z1 = 0), so a repack that
#          moves blocks between bays moves the objective directly.  Where Z1 dominates, the
#          gain has to come through timing instead, which is a longer causal chain and may
#          simply not pay.
#
# Each instance runs its real budget, paired, brk on and off, same build otherwise.  Two reps
# where the budget allows it.  P4 first: it is the one that killed conw, so it is the honest
# first question, not the friendliest.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
# ONE INSTANCE.  The shared experiment lock serialises DIFFERENT queues but not a second
# copy of this one -- two copies take it in turn and overwrite the same result files,
# which is what contaminated q23.
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py    0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1           python3.12 harness/mkbase.py 0.3 myalg_brkctl.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A, myalg_brkctl as C
a, c = inspect.getsource(A), inspect.getsource(C)
assert 'import bayrepack as _brk' in a and '_ogc_fast_engine' in a, 'brk arm not wired'
assert 'bayrepack' not in c, 'control must not carry the operator'
assert all(x.get('conw', 1.0) == 1.0 for x in A._AXES), 'contact must stay at FULL strength'
assert 'def _fast_obj' in a and 'def _fast_obj' in c, 'both arms on the same base'
print('gate arms verified: brk vs control, contact at full on both')" || exit 1

run () {  # module prob secs tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "gate: $4" >/dev/null 2>&1 )
}

# P4 first -- the instance that killed conw.  Then P5 (four bays, so the target choice matters
# more), then P6 (250 blocks at 900 s, where an overrun costs most).
for rep in 1 2; do
    run myalg_brk    4 480 "P4 brk on r$rep"  "gbrk_p4_on_r${rep}.log"
    run myalg_brkctl 4 480 "P4 brk off r$rep" "gbrk_p4_off_r${rep}.log"
done
for rep in 1 2; do
    run myalg_brk    5 600 "P5 brk on r$rep"  "gbrk_p5_on_r${rep}.log"
    run myalg_brkctl 5 600 "P5 brk off r$rep" "gbrk_p5_off_r${rep}.log"
done
run myalg_brk    6 900 "P6 brk on r1"  "gbrk_p6_on_r1.log"
run myalg_brkctl 6 900 "P6 brk off r1" "gbrk_p6_off_r1.log"
echo "gate_brk done  $(date -u +%H:%M:%S)"
