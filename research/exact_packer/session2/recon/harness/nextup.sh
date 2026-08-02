#!/bin/bash
# THE P6 LEVER ITSELF, and the scheduler defect that keeps rewarding failure.
#
# Queued behind sweepdir on the shared lock, so nothing overlaps a measurement.
#
# 1. GRASP ON TODAY'S CODE.  results/split.log holds
#
#        draw 1    28,261,134  at 14 s
#        draw 11   27,607,317  at 152 s
#        polished  27,556,165  feasible=True
#
#    against 29,651,637 from the current pipeline.  But that log was produced by harness/grasp.py,
#    which imports myalgorithm (the 6,675-line legacy file) and myalg_orig -- neither of which is
#    what ships.  The number therefore proves nothing about the current code until it is taken
#    again on it.  That is this step, and it runs FIRST because every plan built on 27.5M
#    depends on it holding.
#
# 2. FAILURE MUST NOT GROW A SLICE.  myalg_lean.py:
#
#        elif ops[k][3]:
#            if s is None:
#                slot[k] = min(budget * 0.45, slot[k] * 1.3)
#
#    The roster flag means "starves without budget", and for a beam that is right -- a beam
#    handed too little time returns nothing and wants more.  brk carries the same flag but its
#    None almost always means a displaced block could not be rehomed: infeasible, not starved.
#    So failing grows its share, up to 45% of the run.  On a 900 s P6 that is 405 s to an
#    operator that just failed, and P6 is where brk fails most.
#
#    THE FIX IS NOT A PER-OPERATOR EXCEPTION.  It asks the same question of every operator, from
#    what it did rather than from what it is registered as: an operator that SPENT its slice and
#    came back empty was starved; one that returned empty in a fraction of it was not.
#
#        if s is None and el >= 0.6 * slot[k]:  grow
#        else:                                  record it as exhausted at this incumbent
#
#    0.6 is a shape, not a fitted value -- the claim is only "most of it" versus "a little of
#    it", and the arm exists to find out whether the distinction pays at all.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
echo "waiting for the experiment lock $(date -u +%H:%M:%S)"
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1
echo "lock acquired $(date -u +%H:%M:%S)"

# ---- 1. does GRASP still reach 27.5M, on today's tree? ----
if [ ! -s results/nx_grasp_p6.log ]; then
    echo "=== nx_grasp_p6.log (GRASP P6 600+300) $(date -u +%H:%M:%S)"
    timeout 1500 python3.12 harness/grasp.py 6 600 300 6 flatbl 12345 sac3 \
        > results/nx_grasp_p6.log 2>&1
    tail -2 results/nx_grasp_p6.log
    ( cd ../../.. && git add -f research/exact_packer/session2/recon/results/nx_grasp_p6.log \
      && git commit -q -m "nextup: GRASP P6 reproduction on today's code" \
      && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
fi

# ---- 2. the slice rule ----
python3.12 - <<'PY' || exit 1
import re
s = open("harness/mkbase.py").read()
if "OGC_SLICEFIX" in s:
    print("slice arm already present"); raise SystemExit
anchor = '''        elif ops[k][3]:
            if s is None:'''
assert s.count(anchor) == 1, ("slice-growth site not found -- refusing to guess", s.count(anchor))
new = '''        elif ops[k][3]:
            if s is None and (not _SLICEFIX or el >= 0.6 * slot[k]):'''
s = s.replace(anchor, new, 1)
# the flag, defined next to the roster so it travels with the generated file
anchor2 = "    gain = [0.0] * len(ops); spent = [1e-6] * len(ops); tried = [0] * len(ops)"
assert s.count(anchor2) == 1, "roster stats site not found"
s = s.replace(anchor2,
              '    _SLICEFIX = os.environ.get("OGC_SLICEFIX") == "1"\n' + anchor2, 1)
open("harness/mkbase.py", "w").write(s)
print("slice arm added to the generator")
PY

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_slf.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_slf as M
s = inspect.getsource(M)
assert 'el >= 0.6 * slot[k]' in s, 'slice rule not generated'
assert '_SLICEFIX = os.environ.get' in s, 'flag not generated'
print('slice arm built; OGC_SLICEFIX=1 selects it, default is the current rule')" || exit 1

run () {  # tag outfile prob secs slicefix
    [ -s "results/$2" ] && return
    echo "=== $2 ($1) $(date -u +%H:%M:%S)"
    env CRANEPACK_NOBITS=1 OGC_SLICEFIX="$5" BRK_DEBUG=1 timeout $(( $4 * 5 + 300 )) \
        python3.12 harness/run1.py myalg_slf "$3" "$4" "$1" > "results/$2" 2>&1
    tail -1 "results/$2"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$2" >/dev/null 2>&1 \
      && git commit -q -m "nextup: $1" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run "slice on P6"  "nx_slf_p6.log"  6 900 1
run "slice off P6" "nx_slfoff_p6.log" 6 900 0
run "slice on P3"  "nx_slf_p3.log"  3 240 1
run "slice on P5"  "nx_slf_p5.log"  5 600 1
run "slice on P4"  "nx_slf_p4.log"  4 480 1
echo "nextup done $(date -u +%H:%M:%S)"
