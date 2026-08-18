#!/bin/bash
# A AGAINST B ON EVERY TRAINING INSTANCE, BECAUSE FIVE POINTS CANNOT DECIDE A DEFAULT.
#
# Variant B ships and its cost is known on five instances only: prob_1 gains (mean -1.04%, worst
# case -6.38%), prob_3 is flat (-0.03%), prob_20 pays +2.23%, prob_16 pays +10.69%, prob_24 was
# never measured.  Five points is not a distribution, and every attempt tonight to predict which
# side an instance falls on failed -- _demand_ratio_phys (r = -0.607), hz1_est on an empty
# solution (identically 0 on all thirteen), _safe_sequential's Z3 share (0.0% everywhere, it is
# 100% Z1), and a 15 s probe round (both instances deterministic there, spreads overlapping).
#
# Those failures are usually read as "no signal exists".  They are equally consistent with "four
# candidate statistics were tried against five labelled instances".  Forty labels is the cheapest
# way to tell those apart, and it is also the honest way to answer the only question that matters
# about B: how many instances does it hurt, and by how much.
#
# 120 s rather than 240 s.  The hidden set gives 60-120 s per instance by the organisers' own
# statement, so this is inside the real range rather than a scaled-down proxy, and it halves a
# 2h40 sweep.  What it cannot do is settle a knob whose behaviour is budget-dependent -- the
# reserve is one, since it is a FRACTION -- so the arms are compared here for their SHAPE across
# instances, and anything that looks decisive gets re-run at 240 s on the instances it matters on.
#
# A is the 10th entry's behaviour minus THRUBEAM; B adds RESFRAC=0.35 + POLCAP=5 + PARFILL=1.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo all40 > harness/CURRENT
L=results/audit/all40.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/all40.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: all40 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
A="OGC_RESFRAC= OGC_POLCAP=999 OGC_PARFILL=0"
# priority instances first, so a partial sweep is still the useful half
for p in 1 3 2 16 20 24 4 5 6 7 8 9 10 11 12 13 14 15 17 18 19 21 22 23 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40; do
  run "p$p.A" $p 120 "$A"
  run "p$p.B" $p 120 ""
done
echo "ALL40DONE" >> $L
echo idle > harness/CURRENT
