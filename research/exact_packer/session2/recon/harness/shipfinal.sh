#!/bin/bash
# THE SHIPPED CONFIGURATION, on the two instances the report's progression table quotes.
#
# The table currently mixes configurations in one row: P3's 80,795 was measured with the contact
# bound OFF (which is what ships) while P6's 29,566,129 was measured with it ON.  The rules require
# the report to describe the submitted algorithm, so a row that reports two different builds is a
# defect regardless of how small the difference turns out to be.
#
# P6 twice, because its run-to-run spread is ~112,000 and one sample cannot be told apart from it.
# P3 once more as a check that the restored container reproduces 80,795.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

run () {   # prob secs outfile tag
    [ -s "results/$3" ] && return
    echo "=== $4 $(date -u +%H:%M:%S)"
    BRK_DEBUG=1 timeout $(( $2 * 4 + 300 )) \
        python3.12 harness/run1.py myalgorithm "$1" "$2" "$4" > "results/$3" 2>&1
    tail -1 "results/$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/$3" >/dev/null 2>&1 \
      && git commit -q -m "shipped config: $4" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
}

run 6 900 "ship_p6_r1.log" "ship P6 r1"
run 6 900 "ship_p6_r2.log" "ship P6 r2"
run 3 240 "ship_p3.log"    "ship P3"
echo "shipfinal done $(date -u +%H:%M:%S)"
