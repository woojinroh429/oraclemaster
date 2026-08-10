#!/bin/bash
# WHICH OF VARIANT B's THREE SWITCHES IS PAYING FOR prob_16's +10.69%?
#
# B ships three things at once: OGC_RESFRAC=0.35, OGC_POLCAP=5, OGC_PARFILL=1.  Its cost on
# prob_16 was attributed entirely to the first -- round 0 falling from 199 s to 155 s -- on the
# strength of a single pair, prob_16's best worker reaching 2,671,848 at 199 s against 2,879,376
# at 155 s.
#
# rfsplit now contradicts that twice, paired, with a stable magnitude:
#
#               rf20 (round 0 191 s)   rf25 (round 0 179 s)
#     r1                  3,095,477              2,948,010   -4.8%
#     r2                  2,850,396              2,700,422   -5.3%
#
# Shorter round 0 is BETTER on prob_16, which is the opposite of the attribution.  If that holds,
# the +10.69% is being paid by one of the other two switches, and both are things B can turn off:
#
#     POLCAP=5     caps the tail polish.  prob_16 spends its whole reserve there by default and
#                  runs 239 s of 240; if that pass earns its seconds on this instance, capping it
#                  is the loss.  The evidence it does not was measured on prob_3 (39 s vs 5 s,
#                  0.05% apart) and never on prob_16.
#     PARFILL=1    points the second round at the parity that won round 0.  It measured no
#                  difference on prob_1 -- `both` and `rf50` returned the identical number -- and
#                  was never isolated anywhere else.  On prob_16 the answers come from the ODD
#                  pair 80% of the time, and PARFILL concentrating four workers on one parity
#                  halves the number of configurations the second round draws from.
#
# So: B with each switch removed in turn, three replicates, on the instance that pays and the
# instance that gains.  If a single switch carries the cost, B keeps its gain and drops its loss.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo bsplit > harness/CURRENT
L=results/audit/bsplit.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bsplit.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: bsplit $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2 3; do
  for p in 16 1; do
    run "r$rep.p$p.B"      $p 240 ""
    run "r$rep.p$p.nopol"  $p 240 "OGC_POLCAP=999"
    run "r$rep.p$p.nopar"  $p 240 "OGC_PARFILL=0"
    run "r$rep.p$p.A"      $p 240 "OGC_RESFRAC= OGC_POLCAP=999 OGC_PARFILL=0"
  done
done
echo "BSPLITDONE" >> $L
echo idle > harness/CURRENT
