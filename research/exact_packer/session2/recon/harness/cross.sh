#!/bin/bash
# FOUR WORKERS, TWO CONFIGURATIONS.  MAKE IT FOUR.
#
# The aim split, the m split and the direction override all index by `wid % 2`, so the pool holds
# two configurations with two workers each -- w0 == w2 and w1 == w3.  Indexing m by (wid // 2) % 2
# makes them a 2x2 and the pool holds four distinct bets.
#
# WHY THIS IS NOT ANOTHER TIME-REALLOCATION ARM.  Every branch that closed tonight moved seconds
# between round 0, a second round, the polish and the probe, and every one of them ran into the
# same wall: prob_1 wants draws and prob_16 wants depth, and no predictor tells them apart before
# the search starts (four were tried and all four failed).  This moves no seconds at all.  It
# changes what the four workers are betting ON, and the answer is a minimum over those bets.
#
# WHAT IT GIVES UP, STATED BEFORE THE DATA.  Each configuration currently gets a minimum over TWO
# draws; crossed it gets one.  The alleven/allodd queue priced the same trade from the other side
# -- four workers concentrated on one configuration merely TIED with the 2+2 split on prob_1 --
# which says the second draw of a configuration is worth little there and predicts crossing should
# win.  It also says nothing about prob_16, where the workers agree much more closely and a second
# draw of the right configuration may be worth more than a first draw of a wrong one.
#
# Reported per WORKER as well as per minimum: if crossing works, the WSTAT spread should widen and
# the minimum should fall.  A widened spread with an unchanged minimum means the two new
# configurations are simply worse, which is the honest failure mode and is not the same as noise.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo cross > harness/CURRENT
L=results/audit/cross.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cross.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: cross $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2 3; do
  for p in 1 16; do
    run "r$rep.p$p.off"   $p 240 ""
    run "r$rep.p$p.cross" $p 240 "OGC_CROSS=1"
  done
done
echo "== CROSS core done ==" >> $L
for rep in 1 2; do
  for p in 3 20 24 6; do
    run "r$rep.p$p.off"   $p 240 ""
    run "r$rep.p$p.cross" $p 240 "OGC_CROSS=1"
  done
done
echo "CROSSDONE" >> $L
echo idle > harness/CURRENT
