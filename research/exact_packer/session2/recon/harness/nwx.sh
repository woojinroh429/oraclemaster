#!/bin/bash
# WHERE DOES w3 STOP WINNING?  THE GATE NEEDS A NUMBER.
#
# nw2.sh + nwbud.sh bracket the crossover but do not locate it:
#
#                prob_1     prob_16
#      60 s      -0.85%      -10.1%     w3 ahead or level
#     120 s     -15.5%        -5.0%     w3 ahead
#     240 s      +3.6%        +5.2%     w4 ahead
#
# A gate written as `timelimit <= 150 -> 3 workers` is a guess sitting between two measured
# points.  180 s splits the bracket; if w3 still wins there the boundary is above 180, if it
# loses the boundary is between 120 and 180 and 150 is defensible.
#
# WHY THE CROSSOVER IS WORTH LOCATING AT ALL, given the win is mid-budget only.  The hidden set
# is reported to give its EARLY instances 60-120 s.  Those are exactly the cells where 120 s
# measured -15.5% and -5.0%, and they are scored like any other.  A gate that fires only there
# is a real gain on a real part of the set, and it costs nothing anywhere else because outside
# the gate the shipped behaviour is byte-identical.
#
# 180 s FIRST on prob_1, because prob_1 has the larger effect at 120 s and so the clearer signal.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nwx > harness/CURRENT
L=results/audit/nwx.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nwx.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nwx.sh \
        && git commit -q -m "in-flight: nwx $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for p in 1 16; do
    run "b180.r$rep.p$p.w4" $p 180 "WORKERS=4"
    run "b180.r$rep.p$p.w3" $p 180 "WORKERS=3"
  done
done
echo "NWXDONE" >> $L
echo idle > harness/CURRENT
