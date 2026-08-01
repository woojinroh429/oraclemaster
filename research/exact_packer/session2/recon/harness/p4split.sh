#!/bin/bash
# WHICH CHANGE IS WORTH 39% ON P4?
#
# Measured so far, all at 480 s:
#
#     myalgorithm.py (ships)                3,273,791
#     myalg_orig.py  (c80551b, unpatched)   2,939,598
#     mkbase arm, brk off                   1,780,253
#
# So the old lineage on its own is worth 10%, and the remaining 39% is in what mkbase
# PATCHES ONTO it.  That matters more than anything else found today, because a patch can be
# ported into the shipped file -- it is not a new algorithm, it is a change already validated.
#
# brk is not the answer and is excluded from every arm here.  On P4 it either hurts (its own
# control beats it, 1,780,253 against 1,981,906) or does nothing (1,781,181 once its budget rule
# stopped over-committing).  The 39% was never brk's.
#
# THE DECOMPOSITION.  The arms that produced 1,780,253 were built with OGC_DK=0 and
# OGC_FASTOBJ=1.  Turning each off in turn separates them, and a fourth arm with neither says
# how much is in mkbase's base edits rather than in either knob:
#
#     A  DK=0  FASTOBJ=1   the known-good combination
#     B  DK=3  FASTOBJ=1   DK back to its default
#     C  DK=0  FASTOBJ=0   fast scoring off
#     D  DK=3  FASTOBJ=0   neither knob: mkbase's base alone
#
# If D is already near 1,780,000 the knobs are incidental and the win is in the base edits.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_a.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
         OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_b.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0               python3.12 harness/mkbase.py 0.3 myalg_c.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
                       python3.12 harness/mkbase.py 0.3 myalg_d.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect
import myalg_a as A, myalg_b as Bm, myalg_c as C, myalg_d as D
srcs = {'a': inspect.getsource(A), 'b': inspect.getsource(Bm),
        'c': inspect.getsource(C), 'd': inspect.getsource(D)}
for k, s in srcs.items():
    assert 'bayrepack' not in s, k + ' carries brk; it must not'
assert 'dk=0' in srcs['a'] and 'dk=0' in srcs['c'], 'DK=0 did not reach the axes'
assert 'dk=3' in srcs['b'] and 'dk=3' in srcs['d'], 'DK default did not reach the axes'
assert 'def _fast_obj' in srcs['a'] and 'def _fast_obj' in srcs['b'], 'FASTOBJ missing where it should be'
assert 'def _fast_obj' not in srcs['c'] and 'def _fast_obj' not in srcs['d'], 'FASTOBJ present where it should not be'
print('four arms verified: DK and FASTOBJ vary independently, none carries brk')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 4 480 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "p4split: $2" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run myalg_d "D neither knob"  "p4s_d.log"
run myalg_a "A DK0 FASTOBJ1"  "p4s_a.log"
run myalg_b "B DK3 FASTOBJ1"  "p4s_b.log"
run myalg_c "C DK0 FASTOBJ0"  "p4s_c.log"
echo "p4split done  $(date -u +%H:%M:%S)"
