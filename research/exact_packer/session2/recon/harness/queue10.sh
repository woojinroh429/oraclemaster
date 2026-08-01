#!/bin/bash
# WHICH OPERATOR IS ACTUALLY EARNING P3?
#
# The whole night has gone into how the BEAM scores a cell, on the assumption that the beam is
# what produces P3's answer.  That has never been checked, and P3 is the instance where it is
# least obvious: Z1 is 0, the objective is a pure function of the bay assignment, and one of the
# five operators -- `bay`, the CP-SAT reassignment -- solves exactly that problem directly.  If
# `bay` is what lands the good solutions then every candidate-scoring knob this session has
# tuned the wrong stage.
#
# There is a specific reason to suspect the allocator chooses badly here.  It ranks operators by
# gain[i]/spent[i] with gain the ABSOLUTE improvement over the incumbent, and the incumbent
# starts at the _safe_sequential floor -- 2,488,362,823 on P3 against a final answer near
# 90,000.  Whichever operator first returns a real solution banks 2.49e9; everything after it
# faces a good incumbent and can earn thousands.  A millionfold head start that only the 15%
# random pick can overturn, so the rate largely measures which operator ran FIRST -- and the
# ordering moves with timing, which is where the spread comes from.
#
# OGC_OPS is already in the file as an ablation filter, so this needs no new code:
#
#   beam          construction alone -- no breeding, no repair, no assignment solve
#   beam,grow     the search operators, which is what every knob this session has touched
#   beam,bay      construction plus the CP-SAT assignment, the operator that sees P3's objective
#   (unset)       everything, the shipped roster
#
# If beam,bay matches the full roster, the repair passes spend budget for nothing here.  If beam
# alone is close to it, the 240s re-derives what the first construction already knew and the
# budget should buy diversity rather than refinement.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_ops.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_ops as A
s = inspect.getsource(A)
assert 'OGC_OPS' in s and 'def _fast_obj' in s
print('ops arm built on the fastobj base')" || exit 1

run () {  # opsfilter tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    if [ -n "$1" ]; then export OGC_OPS="$1"; else unset OGC_OPS; fi
    python3.12 harness/run1.py myalg_ops 3 240 "$2" > "results/$3" 2>&1
    unset OGC_OPS
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2; do
    run "beam"      "ops=beam r$rep"      "q10_beam_r${rep}.log"
    run "beam,grow" "ops=beam,grow r$rep" "q10_beamgrow_r${rep}.log"
    run "beam,bay"  "ops=beam,bay r$rep"  "q10_beambay_r${rep}.log"
    run ""          "ops=all r$rep"       "q10_all_r${rep}.log"
done
echo "queue10done  $(date -u +%H:%M:%S)"
