#!/bin/bash
# IS THE PRODUCTION SEED GENERATOR MEASURABLE AT ALL, AND DOES 0.7/5 HELP *IT*?
#
# THE HOLE THIS FILLS.  bk67 gave every axis Bmul 0.7 / K 5 and the score did not move.  I reported
# that as "a seed advantage does not reach the score", and that reading requires a link I never
# measured: that bk67 improves the seed IN PRODUCTION.  The deterministic table says 0.7/5 is
# better for `_contact_beam` at step 1 -- the FINE RUNG ALONE.  Production runs `_beam_once`, which
# is two rungs with a reserve and an order redraw.  Nothing has ever compared axes on that.
#
# So bk67's negative has two readings that this separates:
#     (a) 0.7/5 improves production's seed and the score still does not move -- the bridge is broken
#     (b) 0.7/5 does not improve production's seed -- bk67 never got onto the bridge
#
# FIRST IT HAS TO ESTABLISH THAT THE MEASUREMENT IS POSSIBLE.  `_beam_once` splits its budget by
# reading `budget` in SECONDS, so OGC_WORKCAP may not make it reproducible the way it makes
# `_contact_beam` reproducible.  --reps 3 prints three placement digests for one configuration; if
# they differ, the production seed generator cannot be measured without replicates and every
# axis comparison in this project has to go back to noisy A/B.  That is a real possible outcome
# and it is worth more than the axis ranking it would deny.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo bprod > harness/CURRENT
L=results/audit/bprod.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/bprod.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: bprod $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

cell(){ # prob axis work reps
    local tag="p$1.ax$2.w$3"
    grep -q "$tag " $L 2>/dev/null && return
    timeout 900 /usr/bin/python3.12 harness/beamprod.py $1 --work $3 --axis $2 --reps $4 \
        --data data/stage2 --tag "$tag" >> $L 2>&1 || echo "$tag CRASH rc=$?" >> $L
    ci "$tag"
}

# DETERMINISM FIRST, on one cell, three repeats.  Everything below is void if the digests differ.
cell 1 0 3000 3
echo "== BPROD determinism cell done ==" >> $L

# Then the same axis ranking beam1 produced, but through _beam_once.  If the ordering matches
# beam1's -- axes 2 and 3 first -- then the fine rung is representative and bk67 did reach the
# bridge, so reading (a) stands.  If 0.7/5 is NOT better here, bk67 never improved the seed and
# reading (b) stands.
for w in 3000 6000; do
  for a in 0 1 2 3 4 5; do
    cell 1 $a $w 1
  done
done
echo "== BPROD prob_1 done ==" >> $L

for a in 0 1 2 3 4 5; do
  cell 16 $a 6000 1
done
echo "BPRODDONE" >> $L
echo idle > harness/CURRENT
