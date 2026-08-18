#!/bin/bash
# THE GATE THROWS AWAY HALF THE BUDGET AT 60 s AND WINS ANYWAY.  GIVE THE TIME BACK.
#
#     P1 60 s, DIRGATE on   ran 30 s of 60      reserve 30 s, workers 29 s, polish ~1 s
#     P1 60 s, DIRGATE off  ran 39 s of 60      reserve 21 s, workers 38 s
#
# DIRGATE sets RESFRAC=0.50, so at a 60 s limit the workers get 29 seconds and thirty are never
# used: the polish returns almost at once, and results/audit/fillmoved.log already established that
# the leftover cannot be spent on a fill round (0 of 4 supplied the minimum).  The gate still wins
# 15.5%, which says the DIRECTION is worth more than the time it costs.  Keeping the direction and
# not paying for it has never been tried.
#
# RESFRAC=0.50 was never measured at 60 s.  It arrived inside DIRGATE as part of the 7th
# submission's package, and that package's single-knob table was taken at 240 s -- where the
# reserve is 84 s and the polish actually spends 77 of them.  At 60 s the same fraction buys
# nothing.
#
# AND IT FOLLOWS FROM THE DAY'S ONE STRUCTURAL FINDING.  P1 at 60 s is unfinished, not stuck:
# 556,718 at 60 s, 492,989 at 120 s, 422,629 at 240 s.  Reach per second is the binding constraint,
# and thirty idle seconds is the largest single block of reach left on the table.
#
# WHAT WOULD MAKE IT FAIL, named first.  DIRGATE's three knobs were measured as NON-INDEPENDENT --
# the parts sum to -9.4% while the combination beats -13% -- with the stated explanation that
# w3mul=0.5 leaves preference for z3_reassign to collect and the larger reserve funds the
# collecting.  If that holds, cutting the reserve removes the funding and the direction stops
# paying.  The 60 s evidence argues otherwise (the polish takes about a second there) but what was
# measured is the combination, not the parts.
#
# JUDGED ON BOTH INSTANCES, fixed before the run: below control on P1 AND P3 in at least two of
# three replicates.  Seven settings have failed to transfer between instances today.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo gaterf > harness/CURRENT
L=results/audit/gaterf.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/gaterf.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/gaterf.sh \
        && git commit -q -m "in-flight: gaterf $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3; do
    run "rf.p$p.50.r$rep" $p "WORKERS=4"
    run "rf.p$p.30.r$rep" $p "WORKERS=4 OGC_RESFRAC=0.30"
    run "rf.p$p.15.r$rep" $p "WORKERS=4 OGC_RESFRAC=0.15"
    run "rf.p$p.05.r$rep" $p "WORKERS=4 OGC_RESFRAC=0.05"
  done
done
echo "GATERFDONE" >> $L
echo idle > harness/CURRENT
