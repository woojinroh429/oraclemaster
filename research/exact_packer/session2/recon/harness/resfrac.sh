#!/bin/bash
# THE ONE DIFFERENCE BETWEEN THE 2.6M-P1 BUILD AND THIS ONE THAT NOBODY HAS MEASURED.
#
# Diffing 927ee8bf (reported at hidden P1 = 2.6M, everything else broken) against the current
# build leaves exactly four differences:
#
#     K (P1 2.6M)                        D (current)
#     OGC_ORDER   default "lst"          axis value, lst on the even pair
#     OGC_W3MUL   default "0.5"          axis value, 0.5 on the even pair
#     OGC_RESFRAC default "0.50"         0.35
#     m portfolio none                   _ms = [1,2]
#
# dirall priced the first two and its first replicate says they are NOT the regression:
#
#     da.none.r1    544,247    no worker takes the direction
#     da.all.r1     499,210    all four -- the 7th submission's placement
#     da.stock.r1   489,878    two of four -- shipped
#
# The direction wins 8-10% against not having it, and the shipped HALF beats the global
# application.  So widening it back is not where the missing P1 went.
#
# That leaves the reserve.  The file's own single-knob measurement, prob_1 at 240 s against a
# baseline that repeats to the last digit across six runs (501,758):
#
#     order=lst        483,050   - 3.7%
#     w3mul=0.5        504,490   + 0.5%
#     reserve 50%      470,530   - 6.2%      <-- the largest of the three, and the untested one
#     all three        422,629 / 422,629 / 437,697   -13.0% .. -15.8%
#
# The reserve is time held back from the worker loop for the final polish.  0.50 gives the polish
# half the limit; 0.35 gives it about a third.  On a Z3-dominant instance the polish is
# z3_reassign, which is the pass the whole direction exists to feed -- w3mul=0.5 tells the beam to
# chase preferred bays LESS precisely so that pass has something to collect.  Cutting the reserve
# from 0.50 to 0.35 takes back the time it collects in.  That is a coherent story for why P1
# regressed while the instances that do not depend on the polish were unaffected, and it is a
# story, which is why it is being measured rather than believed.
#
# WHAT WOULD MAKE IT FAIL, named first.  The reserve is also time the WORKERS do not get, and
# results/audit records runs finishing 11-19% short of their budget because the polish had nothing
# to do.  If prob_1's polish is already saturated at 0.35, raising it to 0.50 is pure loss and the
# 240 s measurement above will not reproduce at 120 s -- which is the budget the hidden set gives
# its early instances.  Both budgets are therefore run.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo resfrac > harness/CURRENT
L=results/audit/resfrac.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/resfrac.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/resfrac.sh \
        && git commit -q -m "in-flight: resfrac $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag budget env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 OGC_WSTAT=1 timeout $(( $2 * 3 )) /usr/bin/python3.12 harness/run1.py myalgorithm 1 $2 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# 120 s first: it is the budget the hidden set reportedly gives its early instances.
for rep in 1 2 3; do
  run "rf.120.35.r$rep" 120 "WORKERS=4"
  run "rf.120.50.r$rep" 120 "WORKERS=4 OGC_RESFRAC=0.50"
done
# then 240 s, the budget the -6.2% was measured at, to say whether the knob is budget-dependent.
for rep in 1 2; do
  run "rf.240.35.r$rep" 240 "WORKERS=4"
  run "rf.240.50.r$rep" 240 "WORKERS=4 OGC_RESFRAC=0.50"
done
echo "RESFRACDONE" >> $L
echo idle > harness/CURRENT
