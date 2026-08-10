#!/bin/bash
# THE 40% OF EVERY BEAM SLICE THAT NOTHING CAN REACH.
#
# `_beam_once` runs `for step, frac in ((1, 0.6), (2, 1.0))` and RETURNS as soon as a step produces
# a feasible answer.  So the fine rung is handed 60% of the slice, and when it succeeds the other
# 40% is unreachable -- not idle time the bandit can redistribute, because the slice was already
# charged to the beam.
#
# THREE MEASUREMENTS SAY THIS IS REAL AND NOT A READING OF THE CODE.
#
#   520 production draws on prob_1 with OGC_DRAWSTAT: took/ask median 0.49, 78% of draws use under
#   60% of their allowance, 1% use 95% or more.  First draw asks 31.0 s and takes 8.9 s.
#
#   beamprod, which runs `_beam_once` itself under WORKCAP, returns the identical objective to
#   beam1's `_contact_beam` at step=1 on all six axes at work 3,000 -- 1,174,681 / 1,323,041 /
#   684,687 / 737,578 / 1,403,609 / 1,350,271.  The two-rung structure COLLAPSES to the fine rung:
#   the reserve is never used on this instance.
#
#   The deterministic table has prob_1's best axis still improving 8.9% from work 6,000 to 12,000,
#   i.e. at 51 s, while production stops it near 9 s.  A longer fine rung is what that curve asks
#   for and it is the one thing the 40% could buy.
#
# THIS IS NOT LIKE THE OTHER ARMS TONIGHT.  brk, round count, RESFRAC, POLCAP, PARFILL, PARROUND,
# BRKPAR and bk67 all MOVE seconds between things that already have them, which is why they all
# landed inside the 0.4% the whole pipeline is worth over a single seed.  This RECLAIMS seconds
# that no consumer can currently reach.
#
# THE VETO RUNS FIRST AND IS THE POINT OF THE QUEUE.  The reserve exists for a real failure: on
# prob_18 (n=300) inside a 12 s slice, two of three beam calls returned NOTHING when the fine rung
# was handed the whole slice.  prob_18 is not in stage2; prob_40 and prob_36 are the same n=300, so
# they carry the veto.  If a 300-block instance loses, the reserve is earning its 40% and the
# number stays at 0.6 -- and that is the likeliest way this dies.
#
# prob_1 gets THREE pairs.  Two replicates reversed on me four times tonight -- ax5, brk, prob_20,
# bk67 -- every time when the control happened to draw prob_1's floor basin at 422,629.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo finefrac > harness/CURRENT
L=results/audit/finefrac.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/finefrac.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: finefrac $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# VETO FIRST: n=300, where the reserve was put there to stop the beam returning nothing.
for rep in 1 2; do
  for p in 40 36; do
    run "r$rep.p$p.f60" $p 240 ""
    run "r$rep.p$p.f85" $p 240 "OGC_FINEFRAC=0.85"
  done
done
echo "== FINEFRAC veto done ==" >> $L

for rep in 1 2 3; do
  run "r$rep.p1.f60" 1 240 ""
  run "r$rep.p1.f85" 1 240 "OGC_FINEFRAC=0.85"
done
echo "== FINEFRAC prob_1 done ==" >> $L

for rep in 1 2; do
  for p in 16 20; do
    run "r$rep.p$p.f60" $p 240 ""
    run "r$rep.p$p.f85" $p 240 "OGC_FINEFRAC=0.85"
  done
done
echo "FINEFRACDONE" >> $L
echo idle > harness/CURRENT
