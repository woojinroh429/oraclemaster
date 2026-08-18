#!/bin/bash
# P1 IS 13% WORSE THAN OUR OWN BEST AND THE FILE RECORDS WHY.
#
# From the DIRSET comment in myalgorithm.py, scored on the hidden set:
#
#     6th entry                                      P1 = 2.88M
#     7th entry, order=lst + w3mul=0.5 on ALL axes   P1 -6.86%  ->  ~2.68M   best ever
#                                                    P3 -2.55%   P6 -7.06%
#                                                    P2 +14.23%  P5 +19.03%  P8 +14.00%
#                                                    3 better / 5 worse -> rolled back
#     now, DIRSET=2 (two workers of four)            P1 = 3,051,204 and 3,018,944
#
# So the direction that produced this project's best-ever P1 and P3 is currently carried by half
# the portfolio, which caps the damage on saturated instances at +3.34% and gives back most of the
# P1 win.  The friend's report that P1 and P3 move together is the same observation from outside.
#
# THE MECHANISM IS RECORDED AND IT IS CONDITIONAL.  w3mul=0.5 tells the beam to chase preferred
# bays LESS during construction and leaves preference to z3_reassign afterwards; that pass only
# moves a block to a MORE preferred bay and only when w1*dtardy + w3*dpen < 0, so it needs somewhere
# for the block to GO.  Loose yard -> there is room and the trade pays.  Saturated yard -> there is
# none, the polish collects nothing, and the construction was weakened for free.
#
# Saturation is not a thing to guess: it is w1*Z1 / obj.  stage2/prob_1 runs at Z1 = 19-25 out of
# ~500,000, i.e. a 25% tardiness share -- loose.  prob_36 is 94% -- saturated.  That is the gate
# the rollback needed and never got.
#
# WHAT THIS SWEEP MEASURES, and it needs no code change: OGC_ORDER and OGC_W3MUL are set with
# os.environ.setdefault inside the worker, so exporting them makes ALL FOUR workers take the
# direction -- exactly the 7th submission's behaviour -- while unset leaves the shipped DIRSET=2
# half-portfolio.  Three arms:
#
#     stock     DIRSET=2, two workers of four            the shipped build
#     all       direction on all four                    the 7th submission
#     none      DIRSET=0, no worker takes it             the 6th submission
#
# on the instance the direction was chosen for.  If "all" beats "stock" here by something like the
# 6.86% the hidden set recorded, the gate is worth building and the only remaining work is picking
# the threshold on the tardiness share.
#
# WHAT WOULD MAKE IT FAIL, named first.  The hidden P1 is not stage2/prob_1, and the 7th's win was
# measured at whatever budget the hidden set gives its first instance, not at 120 s.  A null here
# does not clear the direction; it only says this instance cannot resolve it, and the forty-instance
# sign count would be next.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo dirall > harness/CURRENT
L=results/audit/dirall.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/dirall.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/dirall.sh \
        && git commit -q -m "in-flight: dirall $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 400 /usr/bin/python3.12 harness/run1.py myalgorithm 1 120 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4; do
  run "da.stock.r$rep" "WORKERS=4"
  run "da.all.r$rep"   "WORKERS=4 OGC_ORDER=lst OGC_W3MUL=0.5"
  run "da.none.r$rep"  "WORKERS=4 OGC_DIRSET=0"
done
echo "DIRALLDONE" >> $L
echo idle > harness/CURRENT
