#!/bin/bash
# Do hmatch and brk stack?
#
# WHAT EACH IS WORTH ALONE, measured against its own control:
#
#     brk        82,180 / 86,550 / 86,550   vs  96,990 / 106,700 / 106,700    -17.75%
#     hmatch=2   94,275 / 94,275            vs  106,700 / 96,990              -2.8% vs the
#                                                                             control's good end
#
# WHY THEY MIGHT ADD.  They act at different stages on the same physical constraint.  hmatch
# charges the mean |my height - neighbour's height| over the touching boundary as the packing is
# BUILT, so tall settles beside tall and the low ground stays in one piece for the overhangs
# that need it -- 1,352 of P3's 1,588 (block, orientation) pairs have an upper layer past their
# own layer 0.  brk takes whatever arrangement came out and re-solves one bay exactly.  A layout
# whose height field is already sorted should give brk a better starting point, not a redundant
# one.
#
# WHY THEY MIGHT NOT.  brk's gain comes from repairing exactly the mistakes a greedy pass makes.
# If hmatch prevents some of those mistakes, brk finds less to fix and the two overlap rather
# than add.  That would still be worth knowing: it would mean the height mechanism and the
# repack are two ways at the same 15%, and only one of them needs to be carried.
#
# The control here is brk alone, not the bare base -- stacking is the question, so the arm has
# to beat the thing it is being stacked onto.
#
# hmatch=2.0 is the value, and it is the measured optimum rather than a guess: 0.0/0.5/2.0/8.0
# gave 106,700 / 100,865 / 94,275 / 104,460, an interior optimum.  8.0 degenerates -- its Z2 of
# 3,762 sits next to conw=0.0's 3,652, which is the signature of height-matching overriding
# contact entirely and reproducing the knob that kills P4.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_HMATCH=2.0 \
    python3.12 harness/mkbase.py 0.3 myalg_brkhm.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py   0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brkhm as A, myalg_brk as B
a, b = inspect.getsource(A), inspect.getsource(B)
for nm, s in (('brkhm', a), ('brk', b)):
    assert 'import bayrepack as _brk' in s and '_ogc_fast_engine' in s, nm
assert all(x.get('hmatch') == 2.0 for x in A._AXES), A._AXES
assert all(x.get('hmatch', 0.0) == 0.0 for x in B._AXES), 'control must not carry hmatch'
assert all(x.get('conw', 1.0) == 1.0 for x in A._AXES), 'contact stays at full on both'
print('stack arm and its brk-only control verified')" || exit 1

run () {  # module tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run myalg_brkhm "brk+hmatch2 r$rep" "q16_stack_r${rep}.log"
    run myalg_brk   "brk only r$rep"    "q16_brkonly_r${rep}.log"
done
echo "queue16done  $(date -u +%H:%M:%S)"
