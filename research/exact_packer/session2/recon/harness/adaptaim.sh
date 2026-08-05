#!/bin/bash
# Does letting each worker tune its own beam aim beat the fixed 0.90/0.10 portfolio?
#
# results/audit/wstat.md measured, per worker, that half the portfolio is 8-40% behind on every
# instance -- and that which half is behind is not the instance's size.  The low aim wins on P5
# (150 blocks, 64% of blocks three or more layers) and loses on P7, P22 and P1 (150 blocks, flat),
# because layers make the descent test expensive and it is total work that decides whether the
# beam finishes.  So the aim is tuned from the beam's own overrun report instead: multiplicative
# decrease on a salvage, additive increase on a comfortable finish.
#
# The eight instances here are exactly the ones wstat measured, so the per-worker numbers to
# compare against already exist.  OGC_WSTAT stays on: the point is not only whether the answer
# improves but whether the four workers stop splitting into a winning and a wasted half.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/adaptaim.log
mkdir -p results/audit
touch $L

run(){ grep -q "\[$1\]" $L 2>/dev/null && return
       echo "# [$1]" >> $L
       env $3 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd "$(git rev-parse --show-toplevel)" \
         && git add research/exact_packer/session2/recon/results/audit/adaptaim.log \
         && git commit -q -m "in-flight: adaptaim $1" ) >/dev/null 2>&1 ; }

# The two families alternate so a truncated log still covers both: P7/P22/P1 want the high aim,
# P5/P20/P25/P13/P36 want the low one.
for p in 7 25 22 13 1 36 5 20; do
    run "fix.$p" $p "OGC_NOTHING=1"
    run "ada.$p" $p "OGC_ADAPTAIM=1"
done
echo "ADAPTAIMDONE $(grep -c '^P' $L)"
echo idle > "$(dirname "$0")/CURRENT"   # do not let the restart hook re-run a finished queue
