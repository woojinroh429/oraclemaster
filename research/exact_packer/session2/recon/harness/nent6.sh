#!/bin/bash
# nent=6 looks like the first real P3 gain of the session.  Confirm it, and check it does not
# cost P4.
#
# Single runs, forced knobs, P3 at its real 240 s budget:
#
#     (4,40,3)  88,695   Z2 2679  Z3 502   ran 239 s
#     (4,40,6)  80,795   Z2 3469  Z3 423   ran 239 s     -8.9%, inside budget
#     (3,40,3)  81,085   Z2 3107  Z3 437   ran 279 s     -8.6%, 39 s over
#
# 80,795 is below the 82,180 that was this session's best and the first time P3 has gone under
# 82,000.  It also makes exactly the trade the optimum makes and our pipeline has refused all
# day: Z2 WORSE (2679 -> 3469), Z3 better (502 -> 423), on an instance where a unit of
# preference is worth thirty of balance.  nent is the number of entry times offered per block,
# so more of it means more chances to re-time a block into the bay it prefers.
#
# WHY THIS NEEDS CONFIRMING.  One run each, and P3's measured noise band is 3.0% (+-2,900).
# -7,900 sits outside that, so it is probably real -- but "probably" is what four earlier
# directions today looked like before a second rep.
#
# WHY P4 IS IN THIS QUEUE.  Three separate P3-only wins have wrecked another instance today
# (conw historically, brk's tier table, the ejection move).  nent=6 raises the column count
# everywhere, and P4's bays are already the ones that forced the tier down, so it is exactly
# the shape of change that overruns there.  P4 must stay inside 480 s.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

run () {  # nent prob secs tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    BRK_STEP=4 BRK_NOUT=40 BRK_NENT="$1" timeout 1800 \
        python3.12 harness/run1.py myalg_brk "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$5" >/dev/null 2>&1 \
      && git commit -q -m "nent6: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

for rep in 2 3; do
    run 6 3 240 "nent6 P3 r$rep" "n6_p3_r${rep}.log"
    run 3 3 240 "nent3 P3 r$rep" "n3_p3_r${rep}.log"
done
run 6 4 480 "nent6 P4 r1" "n6_p4_r1.log"
echo "nent6 done  $(date -u +%H:%M:%S)"
