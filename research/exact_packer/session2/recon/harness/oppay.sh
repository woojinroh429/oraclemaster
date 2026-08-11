#!/bin/bash
# WHICH OPERATORS ACTUALLY PAY, AND DOES peak_util PREDICT IT.
#
# Two investigations today reached the same wall from opposite ends.  The repair passes were found
# inert -- _z3_improve, _z1_improve and _assign all return their input on stage2/prob_1
# (results/audit/improvers_are_inert.md).  And the discarded budget turned out to be unspendable:
# four fill rounds at 18-33 s supplied the minimum zero times out of four
# (results/audit/fillmoved.log).  The conclusion both times was that this pipeline reconstructs
# rather than improves, and reconstruction needs a long budget to pay.
#
# But DIRGATE contradicts that in one specific place.  It wins 5 of 7 inside 1.00 <= peak_util <=
# 1.30, by 6.9-15.5%, and one of its three knobs is RESFRAC 0.35 -> 0.50 -- which gives the polish
# MORE time, not less.  If the polish were inert everywhere that knob could not help.  So the
# polish is not inert everywhere; it is inert where it was measured, and prob_1's own band
# neighbours may be where it works.
#
# OGC_OPSTAT=1 answers this directly.  Per worker it prints, for every operator in the roster:
#
#     opstat  op  tried  seconds  %budget  gain  gain/s
#
# gain is what that operator actually took off the incumbent.  It is an internal accounting of one
# run, so unlike an objective comparison it carries no run-to-run noise: an operator either
# returned an improvement in that run or it did not.  This session has been repeatedly defeated by
# 5-40% spreads on paired objectives, and this measurement is immune to them.
#
# SIXTEEN INSTANCES SPANNING THE WHOLE peak_util RANGE, 0.68 to 6.26, at 60 s -- the readable
# regime (prob_1's control spread is 0.6% at 60 s against 10%+ at 120 s) and the budget the hidden
# set reportedly gives its early instances.  DIRGATE off throughout so this measures the stock
# pipeline rather than the gate's configuration.
#
# WHAT THE ANSWER CHANGES.  If gain concentrates inside the band, the band is not a curiosity about
# dispatch order -- it is where the polish has room to work, which explains DIRGATE mechanically
# and says the 34 instances outside it need a different treatment entirely.  If gain is flat or
# absent everywhere, then DIRGATE's win comes from the order/w3mul half alone and the reserve is
# carried for nothing, which is a shippable simplification.
#
# WHAT WOULD MAKE IT USELESS, named first.  gain is credited per operator by the roster loop, so an
# operator that improves a solution the final minimum then discards still books gain.  The number
# is "did this operator ever produce something better than what it was handed", not "did it change
# the answer".  Read as an upper bound.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 20; done
echo oppay > harness/CURRENT
L=results/audit/oppay.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/oppay.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/oppay.sh \
        && git commit -q -m "in-flight: oppay $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # prob peak_util
    local tag="op.p$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag] peak_util=$2" >> $L
    WORKERS=4 OGC_DIRGATE=0 OGC_OPSTAT=1 \
        timeout 240 /usr/bin/python3.12 harness/run1.py myalgorithm $1 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$1 [$tag] CRASH rc=$?" >> $L
    ci "p$1"
}

# ordered by peak_util so a partial queue still spans the range
run 22 0.68
run 1  1.02
run 16 1.23
run 4  1.35
run 34 0.98
run 27 1.13
run 7  1.27
run 9  1.44
run 30 1.58
run 20 1.75
run 8  1.90
run 6  2.05
run 26 2.22
run 2  3.29
run 36 4.66
run 25 6.26
echo "OPPAYDONE" >> $L
echo idle > harness/CURRENT
