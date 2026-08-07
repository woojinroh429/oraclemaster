#!/bin/bash
# R=2, MEASURED FOR THE FIRST TIME WITH THE ROUND LOOP ACTUALLY RUNNING TWO ROUNDS.
#
# OGC_ROUNDS was retired on results/audit/rounds.log -- R=2 median +0.91% at a 60 s limit -- and
# that measurement is void.  The room check demanded a full round plus the polish reserve before
# starting another, and _rb is wbudget/_R, so the test could never pass: at 60 s (wbudget ~ 47,
# _rb ~ 23, reserve ~ 12) the second round was unaffordable by construction, and at 240 s R=2 ran
# ONE round and returned after 153 s, discarding 87 s.  Every R>1 number this project has is
# "a fraction of the budget, one round", not "R rounds".
#
# 76d8e8b6 runs the last round with whatever is left instead of skipping it.  A short round cannot
# lose -- `best` spans the rounds and a round only replaces the answer by beating it.
#
# First run on the fixed code, stage-2 prob_20 at 240 s:
#     round 0  min 9,267,869
#     round 1  min 9,044,121      -2.4%, and the second round is where it came from
#     final    9,041,517          against 9,144,888 at R=1, -1.13%
#
# One draw, and prob_20's own spread across today's 240 s runs is about 6%, so that is a reason to
# measure rather than a result.  What makes it worth the machine time and the other reallocation
# arms not: R=2 gives each worker ~99 s, and the two budgets that HAVE been measured against 200 s
# bracket it -- 49 s (R=4, twelve draws) came back +0.20%, 147 s came back +4.3% to +6.1% on four
# workers out of four.  If there is an optimum per-worker budget it is in the middle, and 99 s has
# never been tried.
#
# Eight instances, three replicates, paired on the instance.  Rep-major so an early stop leaves a
# balanced dataset.
set -u
cd "$(dirname "$0")/.." || exit 1
echo r2fix > harness/CURRENT
L=results/audit/r2fix.log
mkdir -p results/audit; touch $L

run(){ # rep R prob
    local tag="r$1.R$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    OGC_ROUNDS=$2 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalgorithm $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/r2fix.log \
      && git commit -q -m "in-flight: r2fix $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 20 16 6 36 34 26 30 1; do
        run $rep 1 $p
        run $rep 2 $p
    done
    echo "REPDONE $rep" >> $L
done
echo "R2FIXDONE" >> $L
echo idle > harness/CURRENT
