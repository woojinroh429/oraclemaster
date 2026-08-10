#!/bin/bash
# THREE USEFUL DRAWS INSTEAD OF TWO, WITHOUT DROPPING A WORKER.
#
# Configs index on wid % 2 (myalgorithm.py 2693 and 2779): even wids get aim 0.90 with m=1
# (config A), odd wids get aim 0.10 with m=2 (config B).  So round 0 at four workers is A B A B --
# and shortdraws.md measured config B as never going below 516,577 in 540 draws on prob_1, against
# config A's median of 530,650.  Half of round 0 cannot produce a winning ticket at all.
#
# `_aims[wid % len(_aims)]` reads a list of ANY length, so the split is reachable from the
# environment with no code change -- BUT THE AIM IS ONLY HALF OF THE CONFIG.  _ms indexes wid % 2
# over [1,2] independently (line 2779), and the file's own comment spells the pairing out:
#
#     w0 (aim 0.90, m=1)   w1 (aim 0.10, m=2)   w2 (aim 0.90, m=1)   w3 (aim 0.10, m=2)
#
# Setting AIMSET alone would make wid 3 (aim 0.90, m=2), a hybrid that has never been measured,
# not a third config A.  Both lists have to be lengthened together:
#
#     OGC_AIMSET=0.90,0.10,0.90,0.90  OGC_MSET=1,2,1,1   ->   wid 0,1,2,3 = A B A A
#
# shortdraws.md proposed exactly this and shelved it, because acting on it needed to know the
# instance family before round 0 and the only predictor was a threshold fitted to thirteen points
# with two known misses.  Its estimate was P(<= 450,000) from 0.30 to 0.41.
#
# THE COMPARISON THIS BUYS.  Two ways to spend the same four cores, now measurable in the same
# units against the 772-draw WORKERS=4 pool already on disk:
#
#     WORKERS=4, stock       A B A B    2 useful draws, 1.00 core each
#     WORKERS=3  (shipped)   A B A      2 useful draws, 1.33 cores each   <- deeper
#     WORKERS=4, 3+1         A B A A    3 useful draws, 1.00 core each    <- more tickets
#
# The shipped gate bought depth.  This buys count.  They are the two remaining moves and nothing
# in the logs says which is worth more, because the second has never been run.
#
# WHAT WOULD REFUSE IT.  If the config-A draws under 3+1 are individually worse than the config-A
# draws under stock -- three A workers contending where two did -- then the extra ticket is bought
# with quality and the trade has to be priced, not assumed.  That is readable directly: WSTAT slot
# 3 becomes an A draw here, so its distribution against slots 0 and 2 answers it inside this queue.
#
# THE FIRST ATTEMPT WAS INVALID AND ITS FIVE RUNS ARE KEPT AS a3.* FOR THE RECORD.  Config A is
# THREE settings tied to wid % 2, not two: OGC_DIRSET=2, the default, also gives even wids
# OGC_ORDER=lst and OGC_W3MUL=0.5.  Lengthening AIMSET and MSET gave wid 3 the aim and the m but
# not the direction, producing a combination never measured before, and it is catastrophic:
#
#     slot 0  (A, has direction)    median 482,866
#     slot 2  (A, has direction)    median 489,878
#     slot 3  (aim + m only)        median 993,027     2.03x worse, and worse than config B
#
# That is the largest single effect measured in this session, and it was hiding inside a default.
# DIRSET only selects even-or-odd, so A B A A cannot be reached by choosing a pair.  Setting the
# direction GLOBALLY reaches it: every wid gets order=lst and w3mul=0.5, and aim/m then make wid
# 0, 2, 3 config A while wid 1 becomes a config B that also carries the direction -- irrelevant,
# since B has not produced a draw under 450,000 in 388 tries.
#
# NOTE ON READING THE LOG.  Under 3+1 the useful draws are slots 0, 2 and 3; under stock they are
# slots 0 and 2.  Any pooled statistic that ignores slot position mixes A and B and means nothing.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo p1a3 > harness/CURRENT
L=results/audit/p1a3.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/p1a3.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/p1a3.sh \
        && git commit -q -m "in-flight: p1a3 $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $2 OGC_WSTAT=1 timeout 560 /usr/bin/python3.12 harness/run1.py myalgorithm 1 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P1 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in $(seq 1 10); do
  run "a3d.r$rep" "WORKERS=4 OGC_AIMSET=0.90,0.10,0.90,0.90 OGC_MSET=1,2,1,1 OGC_ORDER=lst OGC_W3MUL=0.5"
done
echo "P1A3DONE" >> $L
echo idle > harness/CURRENT
