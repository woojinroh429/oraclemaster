#!/bin/bash
# nent FROM THE INSTANCE, not from a table.  P3, P6, P5.
#
# windows() draws its entry times into a SET, so any nent above a block's window width collapses
# to duplicates.  Measured on the real instances -- distinct entry times actually offered, per
# block, averaged:
#
#     P3  width max  6     nent 3 -> 1.96   6 -> 2.12   9 -> 2.12   12 -> 2.12
#     P4  width max 11     nent 3 -> 2.57   6 -> 4.08   9 -> 4.46   12 -> 4.49
#     P6  width max 14     nent 3 -> 2.72   6 -> 4.58   9 -> 5.68   12 -> 6.10
#
# 6 was never a fitted value on P3 -- it is P3's CEILING, and 9 or 12 would be the same
# algorithm there.  But P6 has a third more resolution available and a constant 6 discarded it.
# The ladder is now a SHAPE (full, half, third, sixth) and the numbers come from the instance:
#
#     P3 ceiling  6 -> 6 / 3 / 2 / 1        exactly the old table
#     P4 ceiling 11 -> 11 / 6 / 4 / 2
#     P5 ceiling 14 -> 14 / 7 / 5 / 2
#     P6 ceiling 14 -> 14 / 7 / 5 / 2
#
# P3 REPRODUCING 6/3/2/1 IS THE CONTROL.  If P3 moves, the derivation is not what it claims to
# be.  P6 and P5 are where it can actually pay -- or cost, because more entry times means more
# columns, and the chooser may answer by dropping to a coarser step.  That is the measurement.
#
# BASELINES, all from today, same code except this change:
#     P3     80,795 (x5) / 84,990 (x1) at 240 s
#     P6 30,016,368 at 900 s
#     P5          ? -- sixfix is establishing it right now
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

python3.12 -c "
import inspect, json, bayrepack as R
r = inspect.getsource(R)
assert '_TIERS = [(4, 40, 1.0)' in r, 'tiers are still absolute counts'
assert 'def _ne_of(_frac)' in r, 'no derivation'
assert '_CEIL = max(1, max((int(b[\'due_date\'])' in r.replace('\"', \"'\"), 'ceiling not computed'
T = [(4,40,1.0),(4,40,0.5),(4,20,1/3),(6,10,1/6)]
for p, want in ((3,[6,3,2,1]), (6,[14,7,5,2])):
    d = json.load(open('data/hidden/prob_%d.json' % p))
    c = max(1, max(int(b['due_date'])-int(b['processing_time'])-int(b['release_time'])+1
                   for b in d['blocks']))
    got = [max(1, min(c, int(round(f*c)))) for _,_,f in T]
    assert got == want, (p, got, want)
print('derivation verified: P3 reproduces 6/3/2/1, P6 gives 14/7/5/2')" || exit 1

run () {  # prob secs tag outfile
    [ -s "results/$4" ] && return
    echo "=== $4 ($3) $(date -u +%H:%M:%S)"
    CRANEPACK_NOBITS=1 BRK_DEBUG=1 timeout $(( $2 * 5 + 300 )) \
        python3.12 harness/run1.py myalg_brk "$1" "$2" "$3" > "results/$4" 2>&1
    tail -1 "results/$4"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$4" >/dev/null 2>&1 \
      && git commit -q -m "nentderive: $3" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 3 240 "nentderive P3"    "nd_p3.log"      # control: must stay at 80,795
run 6 900 "nentderive P6"    "nd_p6.log"
run 5 600 "nentderive P5"    "nd_p5.log"
run 3 240 "nentderive P3 r2" "nd_p3_r2.log"
echo "nentderive done $(date -u +%H:%M:%S)"
