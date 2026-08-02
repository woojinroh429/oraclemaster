#!/bin/bash
# THE ONE AXIS THE LEAN PORTFOLIO NEVER VARIES, AND IT IS THE ONE THAT DECIDES P6.
#
# ogc_fast.cpp, on the position score:
#
#   "The position score's only channel to the objective is which way it fills a bay -- x and y
#    appear nowhere in w1*Z1 + w2*Z2 + w3*Z3, so all a position can do is decide whether the
#    free region stays contiguous.  The score has always been (iy+top)*pos_lam +
#    ix*pos_lam*0.01: bottom-up, with x a tiebreak, one direction and no way to ask for
#    another.  The shipped pipeline carries a portfolio of directions and names one of them
#    the P6 winner and another the P4 winner."
#
# and the legacy portfolio names them outright:
#
#     flatbl (P6 FLOOR), bigleft (P6 WINNER), leftbottom (P4 winner)
#
# flatbl is y-major -- which is exactly swy=1.0, swx=0.01, the default every one of the lean
# build's six _AXES entries uses.  Not one of them sets swy or swx.  So the lean pipeline runs
# P6's FLOOR direction on all six axes and never once tries P6's winner, while varying order,
# K, pos_lam, w3mul and cohort around it.
#
# No new code is needed: swy/swx are already parameters of contact_beam, already plumbed
# through _contact_beam, and OGC_WDIV already assigns a knob per worker.
#
# WHY PER WORKER AND NOT PER AXIS.  Recorded when conw was tried both ways: per-axis diversity
# gave P3 96,235 against a 96,990 base while the same knob held flat everywhere reached 87,560.
# Two of six axes carried the value, so best-of would have surfaced it had it been a candidate
# score.  It was not -- it is a REGIME the whole search has to stay in.  A sweep direction is
# the same kind of thing.
#
# ARMS.  B is the general answer -- half the workers each way, the instance picks by its own
# objective with no threshold anywhere.  C is what the legacy evidence points to for P6 alone
# and is measured to see how much B gives up for being gate-free.
#
# BASELINES: P6 29,651,637 @ 900 | P3 80,795 @ 240 | P4 1,781,181 @ 480
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

# WDIV IS READ AT GENERATION TIME, not at run time -- mkbase.py bakes the per-worker override
# into the module.  So each arm is its own generated file, built here from the same source and
# the same flags as myalg_brk, differing only in OGC_WDIV.
HALF='swy:1.0,1.0,0.01,0.01;swx:0.01,0.01,1.0,1.0'
ALLX='swy:0.01;swx:1.0'
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_WDIV=myalg_swb \
    python3.12 harness/mkbase.py 0.3 myalg_swb.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_WDIV=myalg_swc \
    python3.12 harness/mkbase.py 0.3 myalg_swc.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1

python3.12 -c "
import inspect, myalg_brk as A, myalg_swb as Bm, myalg_swc as Cm
for _m, _want in ((Bm, [1.0, 1.0, 0.01, 0.01]), (Cm, [0.01])):
    _s = inspect.getsource(_m)
    assert '_wov = ' in _s, 'WDIV did not reach the generated module'
    assert repr(_want) in _s, (_m.__name__, _want, [l for l in _s.splitlines() if '_wov' in l])
print('arms built: worker-level sweep overrides are in the modules')" || exit 1

python3.12 -c "
import inspect, myalg_brk as A
s = inspect.getsource(A)
assert 'swy' in s and 'swx' in s, 'sweep knobs not plumbed'
import re
ax = s[s.index('_AXES = ['):s.index(']', s.index('_AXES = ['))]
assert 'swy' not in ax, 'an axis already carries swy -- the premise is wrong, stop'
print('confirmed: swy/swx are plumbed and no axis varies them')" || exit 1

run () {  # tag outfile prob secs module
    [ -s "results/$2" ] && return
    echo "=== $2 ($1) $(date -u +%H:%M:%S)"
    env CRANEPACK_NOBITS=1 BRK_DEBUG=1 timeout $(( $4 * 5 + 300 )) \
        python3.12 harness/run1.py "$5" "$3" "$4" "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "sweepdir: $1" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

# P6 first: it is the claim.  Then the two instances that must not regress.
run "sweep B half P6"  "sw_b_p6.log" 6 900 myalg_swb
run "sweep C allx P6"  "sw_c_p6.log" 6 900 myalg_swc
run "sweep B half P3"  "sw_b_p3.log" 3 240 myalg_swb
run "sweep B half P4"  "sw_b_p4.log" 4 480 myalg_swb
run "sweep B half P5"  "sw_b_p5.log" 5 600 myalg_swb
echo "sweepdir done $(date -u +%H:%M:%S)"
