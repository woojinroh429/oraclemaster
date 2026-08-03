#!/bin/bash
# The night's queue, written so that losing it costs nothing.
#
# THE CONTAINER HAS RESTARTED FOUR TIMES TODAY and each restart killed whatever was mid-flight.
# So this script is RESUMABLE: every run appends one line tagged with its own key, and the script
# skips any key already present in the log.  Re-running it after a restart continues from where
# it stopped instead of starting over, and running it twice by accident costs nothing.
#
# WHAT IS BEING MEASURED.  cranepack indexed its weights by BLOCK, so a block's on-time seat and
# its ten-days-late seat carried the same number and the solver could not prefer either.  Every
# outside workaround failed for that reason.  It now takes win_weights[i][k] -- the value of
# seating candidate i at its k-th window -- and bayrepack prices each seat exactly, by the only
# term an entry time can move: max(0, exit - due) - max(0, current_exit - due).
#
#   base    OGC_LATEWIN=0                 no late windows at all -- the conservative floor
#   old     OGC_LATEWIN=1 OGC_WINW=0      late windows, per-BLOCK weights (today's default)
#   new     OGC_LATEWIN=1 OGC_WINW=1      late windows, per-SEAT prices
#
# The twelve instances are those where the trade is actually available, ranked by
# w3 * (total preference regret) / w1, all with non-zero d_max and slack to spend.  Judged by
# sign count over pairs, not per instance: the run-to-run spread on this set is about 3% and no
# single pair carries information against that.
cd "$(dirname "$0")/.."
L=results/audit/night_winw.log
touch $L
run () {   # key prob arm-env...
  local key="$1"; shift; local p="$1"; shift
  grep -q "\[$key\]" $L && return 0
  env "$@" /usr/bin/python3.12 harness/run1.py myalgorithm "$p" 180 "[$key]" \
      --data data/stage2 >> $L 2>&1
}
# EXTENDED TO ALL FORTY.  The twelve where the trade is available gave new 8 better /
# 2 worse / 2 identical against base -- p about 0.055 on a sign test, suggestive and
# short of a verdict.  The other twenty-eight also answer a second question the first
# twelve cannot: whether per-seat pricing COSTS anything where the trade is not
# available, which is what decides if it ships as a default.
for p in 40 26 3 4 13 36 18 27 24 15 17 9 \
         1 2 5 6 7 8 10 11 14 16 19 20 21 22 23 25 28 29 30 31 32 33 34 35 37 38 39; do
  run "base.$p" $p OGC_LATEWIN=0
  run "old.$p"  $p OGC_LATEWIN=1 OGC_WINW=0
  run "new.$p"  $p OGC_LATEWIN=1 OGC_WINW=1
done
echo "NIGHTWINWDONE $(date -u +%H:%M)" >> $L
