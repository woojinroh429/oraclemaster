#!/bin/bash
# THE COMPULSORY FIRST TRY IS 20% OF THE CLOCK, AND MOST OF IT IS SPENT ON OPERATORS THAT PAY ZERO.
#
# `slot = [budget * (0.20 if o[3] else _rep) for o in ops]` opens every search operator at a fifth
# of the budget, and `unt = [i for i in elig if tried[i] == 0]` runs each untried one BEFORE
# selection by rate begins.  So the probes are a fraction of the clock and grow with it.  OPSTAT on
# stage-2 prob_1, single worker, tried=1 operators only:
#
#     RESFRAC 0.50, 27.8 s     grow 5.1 + bay 5.0 + brk  1.5 = 11.6 s = 41.7%   all gain 0
#     RESFRAC 0.05, 54.7 s     grow 9.8 + bay 9.3 + brk 13.3 = 32.4 s = 59.2%   all gain 0
#
# Doubling the budget took the waste from 41.7% to 59.2% and pushed beam from 42.2% of the clock to
# 29.4%.  That is the mechanism behind prob_1 getting WORSE with more time, and it is why brkoff
# changed nothing: deleting brk left grow and bay still opening at 20% each, so the freed seconds
# moved from one zero-payer to the next and three medians came back identical to the digit.
#
# OGC_PROBE caps the FIRST try only.  A rate estimate needs a sample, not a full-size run, and an
# operator that was genuinely starved still grows -- the sizing rule multiplies slot by 1.3 each
# time a search operator returns empty, so a beam that needs ten seconds still gets there, having
# paid two seconds to find out instead of eleven.
#
# SMOKE, prob_1 at RESFRAC 0.05, single draw: 531,403 with PROBE=2 against 571,668 without, -7.0%,
# with brk down from 13.3 s to 2.5 s and bay to zero.
#
# WHAT WOULD MAKE IT FAIL, named first.  The smoke's profile shows grow taking 90% of the budget
# and carrying the whole gain while beam recorded 0.0 s -- the first operator to produce a real
# solution books the entire floor-to-solution jump as its gain and then dominates selection by rate
# for the rest of the run.  Cheap probes change WHICH operator wins that race, so this may be
# reshuffling who gets the budget rather than reducing waste, and on another instance the winner of
# that race may be worse.  The band is what decides it.
#
# JUDGED: three draws, paired against final.log's B cells (same engine, same worker count), by
# ratio-mean and geometric mean over the six firing instances.  Ships only if it wins the band and
# does not lose prob_1.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo probe > harness/CURRENT
L=results/audit/probe.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/probe.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/probe.sh \
        && git commit -q -m "in-flight: probe $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $3 timeout 220 /usr/bin/python3.12 harness/run1.py myalgorithm $2 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 1 3 27 16 7 33; do
    run "H.p$p.r$rep" $p "OGC_RESFRAC=0.05 OGC_PROBE=2"
  done
done
# and the size of the cap itself, on prob_1
for rep in 1 2; do
  run "H1.p1.r$rep" 1 "OGC_RESFRAC=0.05 OGC_PROBE=1"
  run "H4.p1.r$rep" 1 "OGC_RESFRAC=0.05 OGC_PROBE=4"
done
echo "PROBEDONE" >> $L
echo idle > harness/CURRENT
