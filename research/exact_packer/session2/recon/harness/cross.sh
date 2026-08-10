#!/bin/bash
# THE ONE AXIS NOTHING TONIGHT TOUCHED: MAKE THE WORKERS DIFFERENT, NOT BETTER.
#
# 297 prob_1 runs, with the minimum EXCLUDED from both regressors so neither is arithmetically
# tied to it (spread_artifact.md's trap: (max-min)/min has the score in its denominator):
#
#     r(mean of the three non-minimum workers, min)     +0.826
#     r(dispersion of the three non-minimum workers, min)  -0.771
#
# The two forces are nearly equal.  Every arm tonight -- brk, bk67, the axis director, axis
# pinning, round count, RESFRAC, POLCAP, PARFILL, PARROUND, BRKPAR, FINEFRAC -- aimed at the first
# one, and all nine failed.  Nothing aimed at the second.
#
# AND THE POOL IS NARROWER THAN IT LOOKS.  The beam aim, the m split and DIRSET all index wid % 2,
# so four workers hold TWO configurations, two workers each:
#
#     shipped                       OGC_CROSS=1
#     wid 0   aim 0.90  m=1         aim 0.90  m=1
#     wid 1   aim 0.10  m=2         aim 0.10  m=1
#     wid 2   aim 0.90  m=1         aim 0.90  m=2
#     wid 3   aim 0.10  m=2         aim 0.10  m=2
#     two configs, each twice       FOUR configs, each once
#
# The code is already in the file and its own comment says "whether widening beats deepening here
# is exactly what has never been measured".
#
# WHAT WOULD REFUTE IT, AND WHY THE DISPERSION IS LOGGED AS WELL AS THE SCORE.  The trade is real:
# four configs once each is a minimum over four DIFFERENT things, two configs twice each is a
# minimum over two things sampled twice.  If dispersion rises and the objective does not fall, the
# correlation was not causal and the whole dispersion reading dies with it -- which is worth
# knowing, because it is the only untried direction left.  So every cell's WSTAT is kept and the
# report is (objective, dispersion) per cell, not objective alone.
#
# prob_1 GETS THE MOST CELLS because it is where the correlation is strongest (-0.771) and because
# it is the instance the user needs moved.  Six pairs, and after tonight six is still thin: five
# separate two-pair readings reversed on their third.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo cross > harness/CURRENT
L=results/audit/cross2.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/cross2.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: cross $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 + 60 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 1 2 3 4 5 6; do
  run "r$rep.p1.off"   1 120 ""
  run "r$rep.p1.cross" 1 120 "OGC_CROSS=1"
done
echo "== CROSS prob_1 120 done ==" >> $L

for rep in 1 2 3 4; do
  run "r$rep.p16.off"   16 120 ""
  run "r$rep.p16.cross" 16 120 "OGC_CROSS=1"
done
echo "== CROSS prob_16 done ==" >> $L

# The budget is not established, so the arm is re-checked at the other one rather than assumed.
for rep in 1 2 3; do
  run "r$rep.p1L.off"   1 240 ""
  run "r$rep.p1L.cross" 1 240 "OGC_CROSS=1"
done
echo "== CROSS prob_1 240 done ==" >> $L

for rep in 1 2; do
  for p in 20 40; do
    run "r$rep.p$p.off"   $p 120 ""
    run "r$rep.p$p.cross" $p 120 "OGC_CROSS=1"
  done
done
echo "CROSSDONE" >> $L
echo idle > harness/CURRENT
