#!/bin/bash
# THE EXTRA BUDGET GOES TO OPERATORS THAT RETURN ZERO, AND OPSTAT NAMES THEM.
#
# results/audit/opstat.log, single worker on prob_1, the two reserves side by side:
#
#     RESFRAC 0.50 (27.8 s)                    RESFRAC 0.05 (54.7 s)
#     beam  11.9 s  42.2%  pays                beam  16.2 s  29.4%  pays
#     pref   4.3 s  15.2%  155,451             pref   6.1 s  11.1%  107,585
#     grow   5.1 s  18.1%  0                   grow   9.8 s  17.7%  2,624
#     bay    5.0 s  17.6%  0                   bay    9.3 s  17.0%  0
#     brk    1.5 s   5.4%  0                   brk   13.3 s  24.3%  0
#
# The 27 extra seconds land almost entirely on grow, bay and brk, which return nothing, and brk
# alone takes 13.3 s -- a QUARTER of the budget -- on tried=1.  beam's SHARE falls from 42.2% to
# 29.4% even though its seconds rise.  That is why more time makes prob_1 worse.
#
# P27, where more time HELPS by 19.4%, does the opposite: beam 12.3 -> 25.8 s and holds 46.6% of
# the budget, pref's gain rises 101,852 -> 275,866, and brk stays at 1.0-1.1 s in both.
#
# WHY THE SCHEDULER DOES NOT CORRECT ITSELF.  Budget is meant to follow measured rate --
# `k = max(elig, key=lambda i: gain[i]/spent[i])` -- but brk's PROBE is the expensive call: one
# invocation costs 13.3 s at this budget because its slice is sized from what is available.  An
# operator cannot be demoted for a bad rate until it has been tried once, and trying it once is
# the whole cost.
#
# ARM: OGC_BRK=0 on top of RESFRAC 0.05.  If the 13.3 s moves to beam and pref, prob_1 should beat
# its 571,668 -- and the target worth watching is A's 508,193, which is what the 29 s configuration
# reaches without ever paying brk.
#
# WHAT WOULD MAKE IT FAIL, named first.  brk is measured as WORTH shipping on other instances --
# tasks 8 and 10 in this study adopted it and chose BRKPAR=all -- so switching it off band-wide may
# win prob_1 and lose the instances it was adopted for.  P16 and P33 are the ones to watch; if brk
# pays there this becomes a gate rather than a removal, and a gate needs a feature, which is the
# thing that has failed nine times today.
#
# JUDGED: three draws, paired against final.log's B cells on the same engine, ratio-mean and
# geometric mean over the six firing instances.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo brkoff > harness/CURRENT
L=results/audit/brkoff.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkoff.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/brkoff.sh \
        && git commit -q -m "in-flight: brkoff $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
# F: the shipped candidate (0.05) with brk off.  P1 first -- it is the instance the profile came from.
for rep in 1 2 3; do
  for p in 1 3 27 16 7 33; do
    run "F.p$p.r$rep" $p "OGC_RESFRAC=0.05 OGC_BRK=0"
  done
done
# and prob_1 at the OLD reserve with brk off, to see whether 508,193 was itself brk-limited
for rep in 1 2; do
  run "G.p1.r$rep" 1 "OGC_RESFRAC=0.50 OGC_BRK=0"
done
echo "BRKOFFDONE" >> $L
echo idle > harness/CURRENT
