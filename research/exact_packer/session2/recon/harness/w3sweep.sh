#!/bin/bash
# THE BEAM WEIGHTS THE TERM THAT IS 87% OF THE OBJECTIVE AT THE LOWEST SETTING IN THE TABLE.
#
# stage2/prob_1 has w1=6667, w2=3, w3=600, so obj = 6667*Z1 + 3*Z2 + 600*Z3 and a typical run
# splits as Z1 = 8-20 (53k-133k) against Z3 = 543-900 (326k-540k).  Z3 is 70-87% of it.
#
# _AXES carries w3mul 1.0 / 3.0 / 1.5 / 6.0 across the six axes, and OGC_DIRSET=2 -- the shipped
# default -- overrides the config-A workers to w3mul 0.5, BELOW every value in the table.  The
# workers that decide prob_1 are the ones weighting its dominant term least.
#
# That override was measured as 2.03x better than the axis defaults, but it changes TWO things at
# once: order becomes lst AND w3mul becomes 0.5.  The two have never been separated -- two attempts
# earlier this session were confounded by config B's cost changing between cells.  If order=lst is
# what pays and w3mul=0.5 merely comes along, then the dominant term is being under-weighted for no
# reason and raising it is free objective.
#
# UNIFORM WORKERS, so every cell has identical contention and only w3mul varies:
#
#     WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1 OGC_ORDER=lst
#
# makes all four wids (aim 0.90, m=1, order lst) and leaves w3mul as the single free variable.
# Four draws per run instead of two, and no config B to average in.
#
# 120 s, not 240: the question is which direction w3mul should move, and prob_1's control span at
# 120 s is 13% against 33% at 240 s, so the shorter budget is the cheaper AND quieter place to ask.
#
# WHY IT MIGHT LOSE.  Z3 is the preference term and the beam's contact proxy is myopic; weighting
# preference harder can push blocks into bays they fit badly, which shows up as Z1 at 6,667 a unit.
# The cells report all three components so the trade is visible rather than inferred.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo w3sweep > harness/CURRENT
L=results/audit/w3sweep.log
mkdir -p results/audit; touch $L
U="WORKERS=4 OGC_DIRSET=0 OGC_AIMSET=0.90 OGC_MSET=1 OGC_ORDER=lst"
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/w3sweep.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/w3sweep.sh \
        && git commit -q -m "in-flight: w3sweep $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3; do
  for W in 0.25 0.5 1.0 2.0 4.0 8.0; do
    run "w3.$W.r$rep" "$U OGC_W3MUL=$W"
  done
done
echo "W3SWEEPDONE" >> $L
echo idle > harness/CURRENT
