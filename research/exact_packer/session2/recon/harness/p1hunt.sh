#!/bin/bash
# EVERYTHING STILL UNTRIED ON prob_1, MEASURED WHERE IT CAN ACTUALLY BE SEEN.
#
# prob_1's wall-clock value moved from 508k-518k this afternoon to 622k-680k tonight ON THE SAME
# BUILD -- the box got slower and the beam sets its width from the clock, so the whole attractor set
# shifted.  Nothing below 20% is measurable that way, and the effects worth having are 2-10%.
# OGC_WORKCAP replaces seconds with states-expanded in the width controller and the stop test, and
# three verification runs returned 568,924 to the digit.  Every cell here is exact.
#
# WHAT IS ALREADY CLOSED ON THIS INSTANCE, so it is not repeated: RESFRAC (every value 0.05-0.50),
# ROUNDS 1/2/3, MCAND 1-8 (+42% at M=2, the worst knob measured on it), brk on/off, the first-try
# cap, the gain-attribution fix, w3mul, prefpow, CPANCH/CPORD, SHARE, and the dispatch orders.
#
# WHAT IS NOT, and why each is here:
#
#   OGC_BCAP    beam width ceiling, default 96.  The file records B=137 alone worth -2.5% on prob_16
#               and -8.9% combined with axis 2, and separately notes that on prob_1 "the beam
#               FINISHES: the salvage never runs".  An instance whose beam completes is limited by
#               WIDTH, not by time -- which is the one shape where raising this ceiling is supposed
#               to buy real search rather than fewer draws.
#   OGC_PREFSEARCH  reclassifies pref from repair pass to search operator.  The roster comment
#               argues for it at length -- z3_reassign is a ruin-and-recreate loop that absorbs
#               whatever it is given, w3*Z3 is the median 39.5% of the objective, and pref is the
#               only operator aiming there -- and ends "env-gated rather than flipped" because it
#               was never measured.  opstat puts pref second in gain on this instance.
#   OGC_FINEFRAC  the beam's two-rung schedule, 0.6 shipped.  Task 13 has been open all study.
#   OGC_Z1OP    a whole operator that exists, is registered, and is then filtered back out.
#   OGC_BMULSET per-axis width, the "third way" the BCAP note proposes and never measures.
#
# JUDGED: deterministic, so one cell per arm is exact and anything below the control is real.  The
# winners then have to survive wall clock at the shipped worker count, which is a separate run --
# WORKCAP overruns the budget by design and is not a shipping mode.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo p1hunt > harness/CURRENT
L=results/audit/p1hunt.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1hunt.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p1hunt.sh \
        && git commit -q -m "in-flight: p1hunt $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" envs="$2"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env OGC_WORKCAP=5000 WORKERS=1 $envs timeout 300 /usr/bin/python3.12 \
        harness/run1.py myalgorithm 1 60 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

run "ctl"          "OGC_DEBUG=0"
run "bcap137"      "OGC_BCAP=137"
run "bcap192"      "OGC_BCAP=192"
run "bcap256"      "OGC_BCAP=256"
run "bcap64"       "OGC_BCAP=64"
run "prefsearch"   "OGC_PREFSEARCH=1"
run "finefrac85"   "OGC_FINEFRAC=0.85"
run "finefrac40"   "OGC_FINEFRAC=0.40"
run "z1op"         "OGC_Z1OP=1"
run "bmul_all15"   "OGC_BMULSET=1.5,1.5,1.5,1.5,1.5,1.5"
run "bcap192_pref" "OGC_BCAP=192 OGC_PREFSEARCH=1"
echo "P1HUNTDONE" >> $L
echo idle > harness/CURRENT
