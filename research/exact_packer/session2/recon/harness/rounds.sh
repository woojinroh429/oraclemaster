#!/bin/bash
# Does trading round LENGTH for round COUNT remove the bad draw?
#
# WHY THIS IS WORTH RUNNING, and why the original reason for it was wrong.
#
# The answer algorithm() returns is a minimum over nw workers, and OGC_ROUNDS (implemented,
# defaulting to 1) buys R times the draws by giving each round wbudget/R instead of wbudget.  The
# argument for it was that nw cores might be buying a single draw -- that if the workers converge,
# the minimum is over a sample of size one and more samples is the whole lever.
#
# MEASURED, and it is not so.  abvar's WSTAT lines put the intra-round worker spread at a median
# of 23.7% (old build) and 28.7% (new) across eight instances, and on P20 the four workers split
# into two clusters 27% apart.  The workers do not converge.  The portfolio already delivers four
# genuinely different draws.
#
# The case survives on a different footing, and a better one.  A minimum over k draws from a WIDE
# distribution keeps tightening as k grows -- the wider the spread, the more the tail is worth
# buying -- and a bad run is now identifiable as one whose four workers all landed in the high
# cluster, which is exactly what more draws makes rarer.  What it costs is search depth per draw,
# and there is direct evidence that depth is not binding: stage-2 prob_1 returns the SAME answer
# at 240 s and at 360 s.  Time past convergence is spent, not used.
#
# So the question is empirical and narrow: at a fixed 60 s, is min-over-8-shallow better than
# min-over-4-deep, and is min-over-12-shallower better still?
#
# WHAT IS BEING MEASURED IS THE WORST CASE, NOT THE MEAN.  Per-instance scoring pays for the bad
# draw.  An arm that improves the median while leaving the tail alone has not done the thing that
# was asked for, so every cell here is replicated and the reader ranks on the worst.
#
# Rep-major like abvar, for the same reason: an early stop leaves a balanced dataset.
set -u
cd "$(dirname "$0")/.." || exit 1
echo rounds > harness/CURRENT
L=results/audit/rounds.log
mkdir -p results/audit; touch $L

run(){ # rep R prob
    local tag="r$1.R$2.$3"
    grep -q "\[$tag\]" $L 2>/dev/null && return
    echo "# [$tag]" >> $L
    OGC_ROUNDS=$2 OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $3 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/rounds.log \
      && git commit -q -m "in-flight: rounds $tag" ) >/dev/null 2>&1
}

# The instances abvar measured, so their spreads are already known and the two logs compare.
for rep in 1 2 3 4 5; do
    for p in 1 12 16 26 6 3 20 30; do
        for R in 1 2 3; do run $rep $R $p; done
    done
    echo "REPDONE $rep" >> $L
done
echo "ROUNDSDONE" >> $L
echo idle > harness/CURRENT
