#!/bin/bash
# Z2 LOOKAHEAD on the LEAN BUILD -- the one that is actually the algorithm.
#
# myalg_orig.py is 1,361 lines and is what this project set out to write.  myalgorithm.py is
# 6,675 lines of legacy that build_submission.sh still copies.  I spent most of today calling
# the 6,675-line file "the submission" and treating mkbase's arms as side experiments, which is
# backwards: mkbase generates the arms FROM the lean build, so the arms are the real work.
#
# The first Z2LA run measured the 6,675-line file and came back byte-identical with the flag on
# and off (90,545 both ways).  That file has many modes and may never reach the C++
# contact_beam on P3, so it measured nothing.  The lean build provably reaches it, at
# myalg_orig.py:405.
#
# THE DEFECT.  The beam's state rank is w1*gt + w3*gz3 - mu*gcontact + w2*obj2(loads) + w1*hz,
# and the three objective terms are treated unequally:
#
#     Z1  additive        exact over placed  +  wb_hz1 estimate for the unplaced remainder
#     Z3  additive        exact over placed; a prefix sum IS a partial answer
#     Z2  RANGE of FINAL  partial loads, no estimate of the remainder at all
#
# Z1 has exactly Z2's problem and was given a lookahead.  Z2 never got one, so early states all
# carry small similar loads, the term behaves like a constant, and by the time loads mean
# anything the bays are committed.  On P3 that matters more than anywhere: Z1 is zero and 87%
# of the objective is preference, so the objective IS the assignment.
#
# Not either recorded failure.  Projecting the remainder proportionally is provably a no-op
# (u_j*share_j is one constant for every bay, and a constant leaves max-min alone); this
# projects each remaining block into its OWN PREFERRED BAY, which adds a different amount per
# bay.  The RMS attempt changed the objective and lost over 12 instances; this keeps the exact
# range and only evaluates it at a better point.
#
# Z2LA=0 must reproduce the lean arm's own P3 number, or the rebuild moved something and the
# comparison is void.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 python3.12 harness/mkbase.py 0.3 myalg_a.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_a as A
a = inspect.getsource(A)
src = open('ogc_fast.cpp').read()
assert 'contact_beam' in a, 'the lean arm must reach the C++ beam'
assert 'bayrepack' not in a, 'keep brk out of this comparison'
assert src.count('obj2la(c.loads,level)') == 2, 'both state-rank sites must use the lookahead'
assert 'w2*std::floor(obj2f(' in src, 'the EXACT objective sites must still use obj2f'
print('lean arm and Z2 lookahead verified')" || exit 1

run () {  # z2la tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    OGC_Z2LA="$1" python3.12 harness/run1.py myalg_a 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "z2lean: $2" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 1 2; do
    run 0 "lean Z2LA off r$rep" "z2L_off_r${rep}.log"
    run 1 "lean Z2LA on  r$rep" "z2L_on_r${rep}.log"
done
echo "z2lean done  $(date -u +%H:%M:%S)"
