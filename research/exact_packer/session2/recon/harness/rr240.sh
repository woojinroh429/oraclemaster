#!/bin/bash
# THE PER-WORKER BUDGET IS TOO BIG, AND OGC_ROUNDS IS THE KNOB THAT MAKES IT SMALLER.
#
# Measured inside a single run, with the axis confound removed -- phase 2 of the aim race reuses
# phase 1's wids, so the seeds and the dispatch axes are IDENTICAL and only the budget differs:
#
#     prob_20   50 s, aim 0.10          9,162,795
#              147 s, aim 0.10, x4      9,552,359  9,552,359  9,646,568  9,723,448
#
# Four draws at three times the budget, all worse, +4.3% to +6.1%.  prob_16 showed the same shape.
# So more budget per worker is not merely wasted here, it is harmful, and the shipped build gives
# each worker ~200 s of a 240 s limit -- about four times where prob_20's good draw was.
#
# This also explains why OGC_ROUNDS lost when it was measured: that run was at a 60 s LIMIT with
# R=2, i.e. ~30 s per worker, which is BELOW the good region rather than above it.  The knob was
# right and the budget it was tested at was wrong.  Together the two measurements bracket it:
#
#     ~30 s   (ROUNDS at a 60 s limit, R=2)     worse -- too shallow
#     ~50 s   (race phase 1)                    good
#     ~147 s  (race phase 2)                    worse -- too long
#     ~200 s  (shipped, 240 s limit, R=1)       what we ship
#
# R=4 at a 240 s limit puts each worker near 50 s and yields 16 draws instead of 4.  At the
# measured spread (sigma ~ 7.8%) the statistics of a minimum give E[min] -1.027 -> -1.767 sigma
# and SD[min] 0.701 -> 0.543 sigma: about -5.8% on the answer and -23% on its variability, which
# is both things at once and is exactly the size being asked for.
#
# THE PREDICTION IS FALSIFIABLE.  If the good region is really near 50 s, R=4 wins and R=2
# (~100 s) lands between R=1 and R=4.  If R=2 beats R=4, the region is wider and higher than the
# race measurement suggests.  If neither beats R=1, then prob_20's four-worker result was about
# something other than budget and this reading is wrong.
set -u
cd "$(dirname "$0")/.." || exit 1
echo rr240 > harness/CURRENT
L=results/audit/rr240.log
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
      && git add research/exact_packer/session2/recon/results/audit/rr240.log \
      && git commit -q -m "in-flight: rr240 $tag" ) >/dev/null 2>&1
}

for rep in 1 2 3; do
    for p in 20 16 36 34 6 1 26 30; do
        for R in 1 2 4; do
            run $rep $R $p
        done
    done
    echo "REPDONE $rep" >> $L
done
echo "RR240DONE" >> $L
echo idle > harness/CURRENT
