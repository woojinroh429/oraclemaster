#!/bin/bash
# A MEASURED 14.5% WIN THAT WAS NEVER TURNED ON.
#
# OGC_MCAND is how many candidate blocks each beam state expands.  With m=1 every state at level k
# holds the same block SET and differs only in placements; with m>1 each state expands the m
# earliest unplaced blocks in the dispatch order, so states diverge in WHICH blocks they have
# placed.  The file calls the permutation the largest lever on this problem -- construction spread
# across orders is 32-210%, against about 2% for the combined range of budget policy, axis sets, the
# w3mul grid and brk removal -- and m>1 is the only thing in the engine that searches it.
#
# Its own recorded measurement, 240 s:
#
#     m=2   prob_24 -14.50%   prob_4 -3.74%     won both
#     m=3   prob_24 + 2.40%   prob_4 +10.89%    lost both
#
# and the default is 1.  The note beside it reads "raising the ceiling is the direct test of whether
# m=3 lost to the branching or to the slot shortage" -- so the m=3 question was left open and m=2,
# which won, was never adopted either.  Two instances is thin, and nothing since has re-read it.
#
# It is also the one lever tonight's refutations do NOT touch.  Everything measured in this session
# moved budget BETWEEN operators and none of it moved the answer: bay is a fifth of every worker for
# nothing and removing it changes nothing, the idle tail returns the identical solution, more rounds
# is monotonically worse, the roster cannot be cut.  At 240 s prob_1 returned 470,530 from nine
# different configurations.  What none of that changes is WHICH construction the beam performs, and
# m is exactly that knob: it does not redistribute budget, it widens the neighbourhood the beam
# searches.
#
# m=3 is included because its loss was attributed to running out of survivor slots rather than to
# the branching, and OGC_BCAP raises the ceiling -- so if m=3 recovers at a higher cap, the reading
# was about the cap and not about m.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo mcand > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=mcand" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/mcand.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/mcand.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: mcand $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_24 and prob_4 first: they are the two the 14.50% and 3.74% were measured on, so a failure to
# reproduce there says the reading was wrong before any generalisation is attempted.  Then the five
# this session has replicate spreads for.
for p in 24 4 1 20 16 6 36; do
  run "m240.p$p.m1" $p 240 "OGC_MCAND=1"
  run "m240.p$p.m2" $p 240 "OGC_MCAND=2"
done
echo "== MCAND base done ==" >> $L

# m=3 with the survivor ceiling raised, on the instances where m=2 pays, to settle whether m=3 lost
# to branching or to slots.
for p in 24 4 20; do
  run "m240.p$p.m3"     $p 240 "OGC_MCAND=3"
  run "m240.p$p.m3cap"  $p 240 "OGC_MCAND=3 OGC_BCAP=192"
done
echo "== MCAND m3 done ==" >> $L

# replicate the pair on the instances that carry spread, because a single cell decides nothing here
for p in 24 4 1 20 16 6 36; do
  run "m240.p$p.m1.r2" $p 240 "OGC_MCAND=1"
  run "m240.p$p.m2.r2" $p 240 "OGC_MCAND=2"
done
echo "MCANDDONE" >> $L
echo idle > harness/CURRENT
