#!/bin/bash
# FINEFRAC ON ALL FORTY, SO THE RULE IS FITTED ON HALF AND JUDGED ON THE OTHER HALF.
#
# WHAT IS ESTABLISHED.  FINEFRAC 0.85 against the shipped 0.60, paired, two replicates each:
#
#     n=150  prob_1    -24.01, -19.21   mean -21.61%
#     n=200  prob_3     +1.71,  +1.10   mean  +1.40%
#     n=300  prob_16    +4.25,  +8.00   mean  +6.13%
#
# The gain on prob_1 is the largest effect this session has produced and it reproduced.  The cost
# on prob_16 also reproduced and grew, so it cannot ship globally.  The ordering is monotone in
# block count and it matches the mechanism the code already documents -- the coarse rung's reserve
# exists because the fine rung can fail to finish, and myalgorithm.py records "two of three beam
# calls returned nothing at all" on prob_18 at n=300 when the fine rung was given the whole slice.
#
# WHY THIS IS A SCAN AND NOT ANOTHER GATE GUESS.  Two gates were rejected today -- Z3 share and
# mean layer count -- and both failed the same way: the rule was read off the outcomes of four
# instances and then judged on those same four, so one instance changing sign destroyed it.  With
# forty instances the rule can be FITTED on a training half and JUDGED on a holdout half that had
# no part in choosing it.  That is the step both failures skipped.
#
# BLOCK COUNT IS THE OBVIOUS CANDIDATE AND IT IS NOT THE ONLY ONE.  Each run also carries
# OGC_BEAMSTAT, so every cell records the beam's own report -- salvage flag, level fraction, used
# fraction, achieved work.  Those are free, they are measured rather than assumed, and they fold
# together instance size, grid density and budget in a way n cannot.  The candidate rules are
# written down before the split is looked at: block count, salvage rate, used-fraction, peak_util.
#
# WHAT WOULD MAKE THIS FAIL, named first, and it is the sample size.  One paired draw per instance
# is weak on its own -- prob_1 spans about 30% between draws on unchanged code.  This is therefore
# NOT a per-instance verdict and will not be reported as one.  What forty paired draws can support
# is a rule about the SIGN across a population, and even that only survives if the holdout half
# agrees with the training half.  Any rule that ships gets its winners re-measured with replicates
# afterwards; nothing here goes into the build directly.
#
# The second risk is that no clean separator exists -- that the sign is noise on most instances and
# only prob_1 is really moving.  That is a real outcome and it means FINEFRAC stays at 0.60 with
# prob_1's -21.6% left on the table, which is worth knowing rather than papering over.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire scan40
L=results/audit/scan40.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/scan40.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/scan40.sh \
        && git commit -q -m "in-flight: scan40 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" p="$2" env0="$3" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    _s=$(date +%s.%N)
    env $env0 OGC_BEAMSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
# Paired A/B back to back on each instance so the box state is shared within the pair.
for p in $(ls data/stage2/prob_*.json | sed 's/.*prob_//;s/\.json//' | sort -n); do
    run "A.p$p" $p ""
    run "B.p$p" $p "OGC_FINEFRAC=0.85"
done
echo "SCAN40DONE" >> $L
lock_release scan40
