#!/bin/bash
# Give brk the budget.  Target: low 70,000s on P3.
#
# WHERE WE ARE.  brk is the only thing that survived the night, and it is not close:
#
#     control (no brk)   96,990 / 106,700 / 106,700                    mean 103,463
#     brk                82,180 / 86,550 / 86,550 / 88,720 /
#                        90,545 / 91,670                               mean  87,703   -15.2%
#
# Every brk run beats every control run.  The capacity-aware lower bound is 36,765 and area is
# not what blocks it -- bay 0's first-choice demand is 0.48 of its cells x horizon -- so the
# remaining gap is packing efficiency and there is no arithmetic reason 70,000 is out of reach.
#
# WHAT IS PROBABLY HOLDING IT.  brk reaches the search only through the allocator, and three
# things throttle it there, none of which has been measured:
#
#   A  ITS SHARE.  The allocator ranks by gain[i]/spent[i] with gain the ABSOLUTE improvement
#      over an incumbent that starts at the 2.49e9 greedy floor.  Whichever operator first
#      returns a real solution banks 2.49e9 and everything after it earns thousands -- a
#      millionfold head start only the 15% exploration draw can overturn.  So brk may be doing
#      -15.2% on scraps.  OGC_OPS=beam,brk hands it everything the repair passes and the
#      breeding were taking.
#
#   B  ITS SLICE FLOOR.  8.0 s was a guess made right after the smoke test.  bayrepack sizes the
#      problem to the slice, so an 8 s call lands in the smallest tier -- grid step 6, ten
#      outsiders, one entry time each -- which may be too small to find a repack worth keeping.
#      If so, every cheap call is wasted and the operator only works on the rare large slice.
#
#   C  THE CLOSING RESERVE.  40 s of a 240 s run, 17% of it, is held back for the final z3 pass.
#      That split predates brk, when the post-pass was the only thing that could move Z3 after
#      construction.  Now it competes with an operator that moves Z3 by re-solving the packing,
#      and the trade has never been priced.
#
# Each arm is paired against a brk-default control IN THIS QUEUE and interleaved with it, because
# the six brk-default runs so far split cleanly by queue (82,180/86,550/86,550 in one,
# 90,545/88,720/91,670 in another) with the code diffed and no contention found.  Cross-queue
# comparison is not available here and pretending otherwise is how a wrong result gets adopted.
#
# run1.py prints the wall clock; any arm that exceeds 240 s is disqualified whatever it scored.
# nout=80 and step=3 both scored well and both overran, which is exactly the trap.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_BRKFLOOR=24 \
    python3.12 harness/mkbase.py 0.3 myalg_brkf24.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_RESERVE=0.04 \
    python3.12 harness/mkbase.py 0.3 myalg_brkr04.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, re, myalg_brk as A, myalg_brkf24 as B, myalg_brkr04 as C
for nm, M in (('brk', A), ('brkf24', B), ('brkr04', C)):
    s = inspect.getsource(M)
    assert 'import bayrepack as _brk' in s and '_ogc_fast_engine' in s, nm
    assert all(x.get('conw', 1.0) == 1.0 for x in M._AXES), nm
a, b, c = (inspect.getsource(M) for M in (A, B, C))
assert 'OGC_BRKFLOOR' in b and 'OGC_BRKFLOOR' in a, 'floor must be env-driven in both'
r = lambda s: re.search(r'reserve = max\(2.0, min\(([0-9.]+) \* timelimit, ([0-9.]+)\)\)', s).groups()
assert r(a) == ('0.20', '40.0'), r(a)
assert r(c) == ('0.04', '8.0'), r(c)
print('arms verified: brk default / brk floor 24s / brk reserve 4%')" || exit 1

run () {  # module tag outfile  env...
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    env "${@:4}" python3.12 harness/run1.py "$1" 3 240 "$2" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2; do
    run myalg_brk    "brk default r$rep"  "q18_def_r${rep}.log"
    run myalg_brk    "brk solo r$rep"     "q18_solo_r${rep}.log"   OGC_OPS=beam,brk
    run myalg_brkf24 "brk floor24 r$rep"  "q18_floor_r${rep}.log"
    run myalg_brkr04 "brk reserve4 r$rep" "q18_res_r${rep}.log"
done
echo "queue18done  $(date -u +%H:%M:%S)"
