#!/bin/bash
# Z2 LOOKAHEAD: give the balance term the same treatment the tardiness term already gets.
#
# THE DEFECT, in one table.  The beam's state rank is
#
#     w1*gt + w3*gz3 - mu*gcontact + w2*obj2f(loads) + w1*hz
#
# and the three objective terms are handled unequally:
#
#     Z1  additive        exact over placed  +  wb_hz1 estimate for the unplaced remainder
#     Z3  additive        exact over placed; a prefix sum IS a partial answer
#     Z2  RANGE of FINAL  partial loads, no estimate of the remainder at all
#
# Z1 has exactly Z2's problem -- a prefix cannot see the unplaced blocks' contribution -- and it
# was given a lookahead.  Z2 never got one, so early states all carry small similar loads, the
# term behaves like a constant, and by the time loads mean anything the bays are committed.
#
# WHY THIS IS NOT THE ATTEMPT ALREADY RECORDED AS DEAD.  ogc_fast.cpp documents two failures:
#
#   * projecting the remainder PROPORTIONALLY is provably a no-op -- share_j ~ 1/u_j makes
#     u_j*share_j the same constant for every bay, and a constant added to every value leaves
#     max-min unchanged.  That proof is correct and it does not apply here: this projects each
#     remaining block into ITS OWN PREFERRED BAY, which adds a different amount per bay.
#   * twice the RMS deviation changed the OBJECTIVE and came out net worse over 12 instances.
#     This keeps the exact objective -- still the range -- and only evaluates it at a better
#     point.
#
# Costs nothing: the dispatch order is fixed, so every state at a level shares one projection
# vector, computed once per level.
#
# MEASURED ON THE SHIPPED FILE, which is the best P3 build there is (90,545 twice, to the
# digit) -- not on an mkbase arm, which is 7% worse there and would flatter any change.
# Z2LA=0 must reproduce 90,545 exactly, or the rebuild itself changed something and the
# comparison is void.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import ogc_fast, inspect, myalgorithm as S
src = open('ogc_fast.cpp').read()
assert 'OGC_Z2LA' in src and 'obj2la(c.loads,level)' in src, 'the lookahead is not wired'
assert src.count('obj2la(c.loads,level)') == 2, 'both state-rank sites must use it'
assert 'w2*std::floor(obj2f(' in src, 'the EXACT objective sites must still use obj2f'
assert 'bayrepack' not in inspect.getsource(S)
print('Z2 lookahead wired at both state-rank sites; exact-objective sites untouched')" || exit 1

run () {  # z2la prob secs tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    OGC_Z2LA="$1" python3.12 harness/run1.py myalgorithm "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "z2la: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 1 2; do
    run 0 3 240 "Z2LA off P3 r$rep" "z2_off_p3_r${rep}.log"
    run 1 3 240 "Z2LA on  P3 r$rep" "z2_on_p3_r${rep}.log"
done
echo "z2la done  $(date -u +%H:%M:%S)"
