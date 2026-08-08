#!/bin/bash
# SEARCH AT THE BUDGET THE HIDDEN SET ACTUALLY GIVES.
#
# Everything this project tuned was tuned at 240 s, and the hidden set reportedly gives its early
# instances 60-120.  That is not a detail: the combination found at 240 s reverses sign there.
# Paired on prob_1, alone on an idle machine:
#
#     240 s   default 501,758   order=lst + w3mul=0.5 + reserve 50%   422,629   -15.8%
#      60 s   default 636,140   the same three                        774,699   +21.8%
#
# So the sweep is redone here at 60 s and 120 s, one knob at a time off the shipped default, on the
# instances whose baselines are the most reproducible.  A 60 s cell is a quarter the cost of a
# 240 s one, so this covers four times the ground per hour -- the budget that matters is also the
# cheap one to measure.
#
# WHY THESE KNOBS.  Work-budgeted sweeps overnight put order and w3mul far outside anything else
# measured (prob_1 axis-0 params, order only: defer_big 1,174,681 -> lst 690,840), and the reserve
# fraction is the one that moved the full pipeline at 240 s.  None has ever been read at 60 s.
#
# resfrac is included at values BELOW the shipped 0.20 as well as above: at 60 s the shipped
# reserve is min(0.20*60, 40) = 12 s while the polish converges in about 17, so the short-budget
# question is whether the polish is being cut off rather than over-fed.
#
# ONE CELL AT A TIME, NOTHING ELSE ON THE MACHINE.  Two contaminated cells earlier today read
# 524,295 and 438,791 for a configuration that returns 422,629 three times on an idle box -- this
# engine sizes its beam from measured seconds, so a second job on the cores changes the answer.
set -u
cd "$(dirname "$0")/.." || exit 1
echo short60 > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=short60" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/short60.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/short60.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: short60 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 5 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_1 first and complete: it is the hidden set's closest analogue and its 240 s baseline repeats
# to the last digit.  prob_4 second for the same reason, then prob_24 as the Z1-leaning check.
for L in 60 120; do
  for p in 1 4 24; do
    run "b$L.p$p.base"      $p $L ""
    for od in lst edd cohort; do
      run "b$L.p$p.od$od"   $p $L "OGC_ORDER=$od"
    done
    for wm in 0.5 2.0; do
      run "b$L.p$p.wm$wm"   $p $L "OGC_W3MUL=$wm"
    done
    for rf in 0.10 0.35 0.50; do
      run "b$L.p$p.rf$rf"   $p $L "OGC_RESFRAC=$rf"
    done
  done
  echo "== BUDGET $L done ==" >> $L
done
echo "SHORT60DONE" >> $L
echo idle > harness/CURRENT
