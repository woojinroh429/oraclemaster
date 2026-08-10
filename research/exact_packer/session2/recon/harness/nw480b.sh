#!/bin/bash
# FILL THE CELL THAT BROKE THE SHIPPING CLAIM.
#
# The ship note for nw = cpu - 1 rests on one sentence: "the worst draw improves in all six
# cells".  nw480.sh added a seventh and eighth cell and prob_1 at 480 s does not comply:
#
#     480 s        r1        r2        r3       mean    span    worst
#     w4      442,451   405,381   426,604    424,812    9.1%  442,451
#     w3      392,626   402,890   456,249    417,255   16.2%  456,249   <- 3.1% ABOVE w4's worst
#
# Three pairs.  Every claim made at two or three draws tonight has been overturned by the next
# one -- five times -- so this is not yet a counterexample, it is a cell that needs finishing.
#
# WHY THIS CELL AND NOT ANOTHER.  friend_ref/README.md records the reference submission using
# close to the full ~500 s budget, so the instances scored at this budget are the ones carrying
# the points.  A worst-draw regression at 60 s would cost little; one here costs the most it can.
#
# WHAT EACH OUTCOME MEANS, decided before the numbers land:
#
#     worst recovers over 5 pairs   -> r3 was a draw, the shipped default stands unqualified
#     worst stays above w4's        -> the tail claim has a real exception at the top budget, and
#                                      the honest form is a gate: 3 workers under some limit,
#                                      4 above it.  timelimit is an argument to algorithm(), so
#                                      the gate needs nothing predicted -- unlike brk's.
#
# NOT reverting on three pairs either way: reverting on n=3 would repeat the exact error being
# corrected for.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo nw480b > harness/CURRENT
L=results/audit/nw480.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/nw480.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/nw480b.sh \
        && git commit -q -m "in-flight: nw480b $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 2 + 120 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

for rep in 4 5; do
  run "b480.r$rep.p1.w4" 1 480 "WORKERS=4"
  run "b480.r$rep.p1.w3" 1 480 "WORKERS=3"
done
echo "NW480BDONE" >> $L
echo idle > harness/CURRENT
