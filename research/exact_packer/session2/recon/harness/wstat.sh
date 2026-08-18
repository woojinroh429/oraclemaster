#!/bin/bash
# Where does the answer's variance come from?
#
# P7's control arm returned 1,075,322 and then 831,362 on the same build at the same budget --
# 29.3% against itself, wider than any gap we have measured BETWEEN arms on that instance.  On a
# per-instance score that swing costs more than a 3% improvement in the mean buys, and it is the
# thing the whole session has been chasing without measuring directly.
#
# The answer is a minimum over four workers, so its variance is set by the worker distribution:
# how far apart the four land, and how heavy the good tail is.  Measuring that needs replicates of
# the ANSWER -- expensive -- or one run with the workers printed, which is what OGC_WSTAT does.
# Two runs per instance instead of ten.
#
# The prediction to test: the aim portfolio should WIDEN the worker spread, because two of its
# four workers now search at a different beam width, and a wider spread with the same floor makes
# the minimum both better and steadier.  The one pair we have says 29.3% (ctl) against 6.2% (mix),
# which is the right direction from two points and worth nothing until it is eight.
set -u
cd "$(dirname "$0")/.." || exit 1
L=results/audit/wstat.log
mkdir -p results/audit
touch $L

run(){ grep -q "^# \[$1\]" $L 2>/dev/null && return
       echo "# [$1]" >> $L
       env $3 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm $2 180 "[$1]" \
           --data data/stage2 >> $L 2>&1
       ( cd "$(git rev-parse --show-toplevel)" && git add research/exact_packer/session2/recon/results/audit/wstat.log \
         && git commit -q -m "in-flight: wstat $1" ) >/dev/null 2>&1 ; }

# small and large alternating, so a truncated log is still balanced across sizes.
for p in 7 25 22 13 1 36 5 20; do
    run "ctl.$p" $p "OGC_BEAMAIM=0.90"
    run "mix.$p" $p "OGC_NOTHING=1"
done
echo "WSTATDONE $(grep -c '^WSTAT' $L)"
echo idle > "$(dirname "$0")/CURRENT"   # do not let the restart hook re-run a finished queue
