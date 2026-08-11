#!/bin/bash
# WHERE THE BUDGET ACTUALLY GOES, ON THE INSTANCE THAT WANTS MORE TIME AND THE ONE THAT DOES NOT.
#
# final.log put the two instances on opposite sides of the same knob, both deterministically:
#     P1    0.50 -> 508,193 / 510,450 / 681,869      0.05 -> 571,668 x3     more time HURTS
#     P27   0.50 -> 859,349 x3                       0.05 -> 692,860 x3     more time HELPS 19.4%
#
# The incumbent is guarded in both places -- the worker returns best[1] behind
# `if pool[0][0] < best[0]`, and the roster only replaces on `o < best[0]` -- so a longer run
# cannot be a worse run of the SAME search.  It is a DIFFERENT search: the operator scheduler
# allocates by measured rate, and _rb, the slot sizes and the beam rungs all scale with the budget.
#
# OGC_OPSTAT=1 prints, per operator, tried / seconds / %budget / gain / gain-per-second.  It has
# never been switched on in this study, so "which operator eats the extra 28 seconds on P1, and
# what does it return" has no answer yet.  That is the question this asks.
#
# WORKERS=1 cells are included because OPSTAT prints on stdout from inside the worker and the pool
# runs workers as child processes; if the pooled cells come back without opstat lines, the
# single-worker cells still carry the profile.  They are diagnostic, not a configuration proposal.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo opstat > harness/CURRENT
L=results/audit/opstat.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/opstat.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/opstat.sh \
        && git commit -q -m "in-flight: opstat $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for p in 1 27; do
  run "pool.p$p.50" $p "OGC_OPSTAT=1 OGC_WSTAT=1 OGC_RESFRAC=0.50"
  run "pool.p$p.05" $p "OGC_OPSTAT=1 OGC_WSTAT=1 OGC_RESFRAC=0.05"
  run "w1.p$p.50"   $p "OGC_OPSTAT=1 OGC_WSTAT=1 OGC_RESFRAC=0.50 WORKERS=1"
  run "w1.p$p.05"   $p "OGC_OPSTAT=1 OGC_WSTAT=1 OGC_RESFRAC=0.05 WORKERS=1"
done
echo "OPSTATDONE" >> $L
echo idle > harness/CURRENT
