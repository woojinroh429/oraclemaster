#!/bin/bash
# THE ONE MECHANISM THAT ADDS DRAWS WITHOUT PAYING FOR THEM, AND IT HAS NEVER BEEN MEASURED.
#
# myalgorithm.py line 109:
#
#   # OGC_SHARE=1 lets a worker that is far behind the others restart from a fresh seed instead of
#   # spending the rest of the budget on a basin the final minimum will discard.  OGC_SHAREGAP is
#   # how far behind it has to be, as a fraction; 0.5 means fifty per cent worse than the best
#   # other worker.  Off by default until measured on the full set.
#
# "Off by default until measured" -- and it never was.
#
# WHY IT IS DIFFERENT FROM EVERYTHING TRIED TONIGHT.  p1lottery.md established that a run's answer
# is a MINIMUM over worker draws and that the count of draws is what moves it.  Every arm since has
# either traded count against quality (worker count: three workers means three draws not four) or
# tried to shift the quality distribution (axis, width, w3mul, order, prefw) and been absorbed by
# the attractor.  SHARE does neither: a worker already 50% behind the best cannot become the
# minimum, so the rest of its budget is already spent, and restarting it converts that dead time
# into a fresh draw.  It raises the effective draw count without adding a worker, so without adding
# contention -- which is what killed the 3+1 arm.
#
# WHAT WOULD MAKE IT FAIL, named first.  Restarting throws away a partial solution that might still
# have been improving, and the 50% gap is measured against the best OTHER worker at that moment --
# early in a run every worker is bad, so a badly placed threshold could restart workers that were
# merely young.  OGC_SHAREGAP is swept alongside for exactly that reason: 0.3 restarts eagerly,
# 0.5 is the shipped default, 1.0 only abandons workers that are twice as bad.
#
# SHIPPED RIG, not the uniform one.  SHARE is about how the four real workers interact, so the
# portfolio has to be the real one -- two config A and two config B, answer taken as the minimum.
# That also means the run objective is the measurement, not the round-0 draws, because the whole
# point is what happens AFTER round 0 diverges.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo share > harness/CURRENT
L=results/audit/share.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/share.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/share.sh \
        && git commit -q -m "in-flight: share $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5; do
  run "sh.off.r$rep"   "WORKERS=4"
  run "sh.g03.r$rep"   "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=0.3"
  run "sh.g05.r$rep"   "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=0.5"
  run "sh.g10.r$rep"   "WORKERS=4 OGC_SHARE=1 OGC_SHAREGAP=1.0"
done
echo "SHAREDONE" >> $L
echo idle > harness/CURRENT
