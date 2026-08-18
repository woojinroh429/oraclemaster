#!/bin/bash
# WHICH LINEAGE IS BETTER, AND ON WHICH INSTANCE?
#
# mkbase builds every experimental arm from myalg_orig.py, which its own header says is
# "c80551b verbatim -- the build that scored 29396046 on the real P6 at 900s".  That is a
# DIFFERENT LINEAGE from myalgorithm.py, the file that actually ships.  So every A/B run
# tonight compared patches against each other on the old lineage, and none of them compared
# either lineage against the submission.
#
# Measured so far, one rep each:
#
#                              P3        P4
#     myalgorithm.py (ship)    90,545    3,273,791
#     myalg_brkctl (orig+pat)  106,700   1,780,253
#
# The submission is better on P3 and 84% WORSE on P4.  Against the targets -- P3 70,000 and
# P4 2,200,000 -- the submission misses P4 badly while an arm that already exists clears it.
#
# THIS SEPARATES LINEAGE FROM PATCHES.  myalg_orig.py is run unpatched.  If it lands near
# 1,780,253 on P4, the win is the old lineage and the submission has regressed; if it lands
# near 3,273,791, the win is in mkbase's patches (these arms were built with OGC_DK=0 and
# OGC_FASTOBJ=1) and the fix is to port those.  Either answer is worth more than anything else
# on the table.
#
# A second shipped P4 rep as well, because the 3,273,791 that started all this is a single run.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, myalgorithm as S, myalg_orig as O
s, o = inspect.getsource(S), inspect.getsource(O)
assert s != o, 'the two lineages are the same file -- the premise is wrong'
assert 'bayrepack' not in s and 'bayrepack' not in o, 'neither lineage should carry brk'
print('two distinct lineages verified, neither carrying brk')" || exit 1

run () {  # module prob secs tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "lineage: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

# P4 first: it is where the 84% gap is.
run myalg_orig   4 480 "ORIG P4 r1"    "lin_orig_p4_r1.log"
run myalgorithm  4 480 "SHIPPED P4 r2" "lin_ship_p4_r2.log"
run myalg_orig   3 240 "ORIG P3 r1"    "lin_orig_p3_r1.log"
run myalg_orig   4 480 "ORIG P4 r2"    "lin_orig_p4_r2.log"
echo "lineage done  $(date -u +%H:%M:%S)"
