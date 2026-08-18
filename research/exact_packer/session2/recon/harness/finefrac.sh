#!/bin/bash
# THE KNOB THAT ACTS ON THE 72% OF THE SCORE NOBODY HAS TOUCHED.
#
# The submission's weight is not where the work went today:
#
#     P2 18,490,685   P7 16,376,270   P8 16,960,384   = 51,827,339 = 71.8% of total
#     P1  2,796,931                                                =  3.9%
#
# An 8% cut on P1 moves the total by 0.35%.  One per cent on those three moves it by 0.72%.
#
# And oppay says the polish cannot reach them: at 60 s P2 gives its workers FOUR operator
# invocations in total and books zero pref gain, P25 gives zero, P36 five.  On big instances the
# objective is decided almost entirely by CONSTRUCTION, which is the half no experiment today
# touched.
#
# OGC_FINEFRAC is the construction's own budget split and it has never been measured.  _beam_once
# runs two rungs -- step 1 (fine grid) then step 2 (coarse) -- and hands the fine rung `frac` of
# what is left:
#
#     for step, frac in ((1, _ff), (2, 1.0)):     _ff = OGC_FINEFRAC, default 0.6
#
# The file's own note argues the fine rung is being cut off mid-improvement: "prob_1's best axis is
# still improving at work 12,000 (51 s) while production stops it around 9 s, so a longer fine rung
# is exactly what that curve asks for."  That was written and never tested; task #13 has sat
# pending all day.
#
# WHY IT SHOULD MATTER MORE ON BIG INSTANCES, stated so the result can contradict it.  Cost per
# beam state grows with block count, so at 300 blocks the fine rung gets through proportionally
# fewer states in its 60% and is likelier to be stopped before it has anything.  If that is right,
# raising the fraction should help the large instances and do little on the small ones.  If the
# effect is flat across sizes, the reasoning is wrong even where the numbers are good.
#
# WHAT WOULD MAKE IT FAIL.  frac is taken from what is LEFT, so a larger fine rung starves step 2 --
# and step 2 exists because instrumented runs on prob_18 showed two of three beam calls returning
# NOTHING when the fine rung was handed the whole slice.  Raising the fraction risks reproducing
# exactly that, and a crash to zero on any instance is decisive against.
#
# READ AS A SIGN COUNT.  Single cells on these instances span 5-40%; today that has overturned
# eight readings.  The verdict is how many of the six instances move the same way, not any one
# percentage.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo finefrac > harness/CURRENT
L=results/audit/finefrac.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/finefrac.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/finefrac.sh \
        && git commit -q -m "in-flight: finefrac $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_DIRGATE=0 timeout 260 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# 60 s, DIRGATE off so this measures the construction split alone.
# Six instances: the three largest in the practice set by objective, plus three 300-block ones.
for rep in 1 2; do
  for p in 2 36 25 26 13 40; do
    run "ff.p$p.f60.r$rep" $p "WORKERS=4"
    run "ff.p$p.f85.r$rep" $p "WORKERS=4 OGC_FINEFRAC=0.85"
  done
done
echo "FINEFRACDONE" >> $L
echo idle > harness/CURRENT
