#!/bin/bash
# A FOURTH DIVERSITY AXIS -- THE ONLY ROUTE THE RECORDS LEAVE OPEN.
#
# The answer is a minimum over four workers' draws, so lowering P1 needs a better draw.  Three ways
# to get one are now closed by measurement:
#
#   OGC_SHARE   restarts a lagging worker; it returns to the same attractor.  gap 0.5 never fires,
#               0.3's -1.4% did not reproduce (r2 came back on the control value to the digit),
#               0.15 costs 20% on P1 while helping P3, and values simply hop between arms.
#   OGC_ROUNDS  already shipped.
#   OGC_CROSS   built to raise dispersion, LOWERED it 34% for +12.7%.  Two binary factors crossed
#               give a 2x2 grid whose points sit closer together than the two diagonal corners.
#
# cross_lowers_dispersion.md ends with the instruction this arm follows: "raising dispersion needs
# configurations FURTHER APART, not more of them ... widening it requires a NEW factor, not a
# re-indexing of the ones there."  aim, m and direction all index wid % 2, so the shipped pool is
# already at maximum diameter for the factors in the file.
#
# OGC_PREFPOW is a new factor.  It bends the preference penalty per block -- R*(pen/R)^gamma with R
# the median largest penalty, so scale is held and only the SPREAD moves -- and it is independent
# of aim, m and dispatch order.  As a global SETTING it was measured and closed: no gamma beat the
# control over two replicates.  That does not close it as an AXIS.  A pool needs its members far
# apart, not each member good, and the minimum discards the losers for free.
#
# ARMS.  OGC_PREFPOWSET is a comma list indexed by wid, so "1.0,1.6" leaves w0/w2 on the true
# objective and bends w1/w3.  Wider settings push the pair further apart.
#
# WHAT WOULD MAKE IT FAIL, named first.  If r(dispersion, min) = -0.771 is correlation rather than
# cause, spreading the pool costs what the moved workers gave up and buys nothing.  And half the
# pool now optimises a bent objective, so where the bend is actively wrong those two workers are
# wasted rather than merely different -- which is what the single smoke draw (605,506 against a
# 556,718 control) would look like if it is more than a draw.
#
# JUDGED ON BOTH INSTANCES, as fixed before the run: an arm ships only if it is below control on
# P1 AND P3 in at least two of three replicates.  Six settings today have failed to transfer
# between instances; one-sided wins are not counted.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo ppaxis > harness/CURRENT
L=results/audit/ppaxis.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/ppaxis.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/ppaxis.sh \
        && git commit -q -m "in-flight: ppaxis $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for p in 1 3; do
    run "pa.p$p.off.r$rep"  $p "WORKERS=4"
    run "pa.p$p.g16.r$rep"  $p "WORKERS=4 OGC_PREFPOWSET=1.0,1.6"
    run "pa.p$p.g25.r$rep"  $p "WORKERS=4 OGC_PREFPOWSET=1.0,2.5"
    run "pa.p$p.g07.r$rep"  $p "WORKERS=4 OGC_PREFPOWSET=1.0,0.7"
  done
done
echo "PPAXISDONE" >> $L
echo idle > harness/CURRENT
