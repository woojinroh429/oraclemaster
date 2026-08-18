#!/bin/bash
# Is brk getting the budget it deserves?
#
# It is by far the best operator on this instance -- paired, three reps against three, it moves
# P3 by 17.75% while every scoring knob in the session managed under 10% at its luckiest and
# none survived a control.  But it reaches the search only through the allocator, which ranks
# operators by gain[i]/spent[i], and that rate has a known defect: gain is the ABSOLUTE
# improvement over the incumbent, and the incumbent starts at the _safe_sequential floor --
# 2,488,352,313 on P3 against a final answer near 85,000.  Whichever operator first returns a
# real solution banks 2.49e9; everything after it faces a good incumbent and can earn thousands.
# A millionfold head start that only the 15% random pick can overturn.
#
# So brk may be earning its share, or it may be living on the exploration draw.  Nothing so far
# distinguishes those, and they imply opposite work: if it is starved, the budget is the lever
# and no amount of tuning the operator matters; if it is already saturated, the operator itself
# has to get better.
#
# OGC_OPS is the existing ablation filter and needs no new code.
#
#   beam,brk        construction plus the repack, nothing else.  brk gets everything the repair
#                   passes and the breeding were taking.
#   beam,grow,brk   the search operators plus the repack -- drops bal/pref/bay, which p3max
#                   proved structurally dead here anyway (single-move eviction from bay 0 needs
#                   gap/workload under 0.0948 and the cheapest resident is 0.145).
#   (unset)         the full roster, which is the 82,180/86,550/86,550 already measured.
#
# A large win for beam,brk means the allocator is starving it and the fix is upstream of the
# operator.  No change means it is already getting what it can use, and 80,000 has to come from
# somewhere else.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_brk as A
s = inspect.getsource(A)
assert 'import bayrepack as _brk' in s and 'OGC_OPS' in s
assert all(x.get('conw', 1.0) == 1.0 for x in A._AXES), 'contact must stay at full strength'
print('brk arm verified, contact at full')" || exit 1

run () {  # opsfilter tag outfile
    [ -s "results/$3" ] && return
    echo "=== $3  ($2)  $(date -u +%H:%M:%S)"
    if [ -n "$1" ]; then export OGC_OPS="$1"; else unset OGC_OPS; fi
    python3.12 harness/run1.py myalg_brk 3 240 "$2" > "results/$3" 2>&1
    unset OGC_OPS
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "result: $2" >/dev/null 2>&1 )
}

for rep in 1 2; do
    run "beam,brk"      "brk alone r$rep"    "q15_solo_r${rep}.log"
    run "beam,grow,brk" "brk+grow r$rep"     "q15_grow_r${rep}.log"
done
echo "queue15done  $(date -u +%H:%M:%S)"
