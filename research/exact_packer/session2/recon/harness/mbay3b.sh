#!/bin/bash
# Fill the holes mbay3.sh left, and stop leaving them.
#
# Two instances are missing from results/audit/mbay3.log for two different reasons, and both are
# the same 02:18 incident.
#
# P9 has a `solved` line and no arms.  mbay3.sh skips an instance with `grep -q "^P$p "`, and that
# pattern matches the SOLVE line as readily as a result line -- so an instance whose solve landed
# before it was interrupted looks finished forever after.  The skip predicate has to name the LAST
# line an instance writes, which is the nbay=2 arm; anything earlier is a partial.
#
# P26 wrote nothing at all despite running for minutes.  The pre-fix keepalive.sh looked for
# run1.py, found none (this queue drives mbay.py), concluded the machine was idle, and ran
# `git reset --hard FETCH_HEAD` -- which replaced the tracked log file with a fresh inode.  The
# in-flight P26 kept appending to the unlinked one.  Its output was written and then thrown away.
# keepalive.sh's liveness pattern is fixed; this script exists to redo the measurement it cost.
#
# Same log, same arguments, same order as mbay3.sh, so the table reads as one experiment.
set -u
cd "$(dirname "$0")/.." || exit 1
echo mbay3b > "$(dirname "$0")/CURRENT"
L=results/audit/mbay3.log
mkdir -p results/audit; touch $L
for p in 9 26 3 1 16 12 20 6; do
    grep -q "^P$p  *nbay=2" $L 2>/dev/null && continue
    # An instance with a stale partial (a solve line and no arms) would print a SECOND solve line
    # and read as a duplicate.  Drop its partial rows first so the log stays one row per arm.
    grep -v "^P$p " $L > $L.tmp 2>/dev/null && mv $L.tmp $L
    timeout 600 /usr/bin/python3.12 harness/mbay.py $p 30 60 3 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/mbay3.log \
      && git commit -q -m "in-flight: mbay3b P$p" ) >/dev/null 2>&1
done
echo "MBAY3BDONE" >> $L
echo idle > "$(dirname "$0")/CURRENT"
