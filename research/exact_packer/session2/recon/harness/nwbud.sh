#!/bin/bash
# DOES w3 SURVIVE A CHANGE OF BUDGET?  THE ONE THING THAT WOULD STOP IT SHIPPING.
#
# nw2.sh settled WORKERS=3 vs 4 at 120 s and it was the cleanest result of the night:
#
#     prob_1   5 pairs, zero overlap, mean -15.5%, worst draw -18.7%
#     prob_16  4 pairs, 2 wins 2 ties 0 losses, span 11.2% -> 0.0%
#
# But every one of those nine pairs is at ONE budget, and myalgorithm.py records what that is
# worth.  From the reserve-fraction comment, a three-part change measured on the same instance:
#
#     240 s   old 501,758   ->  422,629   -15.8%
#      60 s   old 636,140   ->  774,699   +21.8%
#
# A 15.8% win at 240 s was a 21.8% LOSS at 60 s.  The hidden set gives its early instances
# 60-120 s and its late ones ~500 s, so a knob validated at 120 s alone is validated nowhere
# that is actually scored.
#
# WHY THE BUDGET COULD FLIP THIS ONE SPECIFICALLY.  w3's gain is cores per worker: 1.33 instead
# of 1.00, so each beam searches deeper.  Depth pays only if the extra depth lands inside the
# budget.  At 60 s a worker may not finish the deeper construction at all, in which case w3 is
# simply three workers instead of four -- a draw thrown away for nothing.  That is the same
# shape as the reserve failure above: the winning setting starved the beam at the short budget.
#
# 60 s FIRST, because that is where the recorded reversal happened.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nwbud > harness/CURRENT
L=results/audit/nwbud.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwbud.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwbud.sh \
        && git commit -q -m "in-flight: nwbud $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# 60 s -- the budget where the recorded reversal happened
for rep in 1 2 3; do
  for p in 1 16; do
    run "b60.r$rep.p$p.w4" $p 60 "WORKERS=4"
    run "b60.r$rep.p$p.w3" $p 60 "WORKERS=3"
  done
done
echo "== NWBUD 60s done ==" >> $L

# 240 s -- the long end
for rep in 1 2; do
  for p in 1 16; do
    run "b240.r$rep.p$p.w4" $p 240 "WORKERS=4"
    run "b240.r$rep.p$p.w3" $p 240 "WORKERS=3"
  done
done
echo "NWBUDDONE" >> $L
echo idle > harness/CURRENT
