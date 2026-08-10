#!/bin/bash
# WHERE IS THE BOUNDARY BETWEEN A SECOND ROUND THAT WINS AND ONE THAT CANNOT?
#
# Variant B ships OGC_RESFRAC=0.35 with the tail polish capped, which is round 0 at 155 s and a
# second round at 76 s.  Everything it costs is the 44 s taken off round 0: prob_16 +10.69%,
# prob_20 +2.23%, while prob_1 gains -1.04% at the mean and -6.38% at the worst case.
#
# The second round only has to be long enough to beat a bad round-0 draw, and tonight bracketed
# that: 76 s beat 524,295 and 486,096 on prob_1, while 24 s and 31 s returned moved=0 four times
# out of four -- a short pool round on prob_1 lands near 600 k, worse than even a poor round 0.
# Nothing has been measured in between.  With the polish capped the reserve maps cleanly onto the
# split:
#
#     0.20   round 0 191 s   second round 35 s
#     0.25   round 0 179 s   second round 47 s
#     0.35   round 0 155 s   second round 76 s     <- shipped
#     0.50   round 0 119 s   second round 112 s
#
# If 47 s still cuts prob_1's tail, 0.25 keeps the gain and hands 24 s back to round 0, which is
# where every instance except prob_1 is losing.  If it does not, 0.35 is the floor and the trade
# is as steep as it looks.
#
# prob_16 is the instance the trade is paid on, so it gets equal weight with prob_1.  Read prob_1
# on the WORST cell, not the mean: the claim is about the right tail.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo rfsplit > harness/CURRENT
L=results/audit/rfsplit.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rfsplit.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: rfsplit $1" \
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
    run "r$rep.p$p.rf20" $p 240 "OGC_RESFRAC=0.20"
    run "r$rep.p$p.rf25" $p 240 "OGC_RESFRAC=0.25"
    run "r$rep.p$p.rf35" $p 240 ""
  done
done
echo "== RFSPLIT core done ==" >> $L
for p in 3 20 24; do
  run "g.p$p.rf25" $p 240 "OGC_RESFRAC=0.25"
  run "g.p$p.rf35" $p 240 ""
done
echo "RFSPLITDONE" >> $L
echo idle > harness/CURRENT
