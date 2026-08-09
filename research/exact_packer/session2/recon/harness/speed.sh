#!/bin/bash
# THROUGHPUT IS DRAWS, AND DRAWS ARE WHAT THE MINIMUM IS OVER.
#
# The operator census puts the beam at 50-60% of every worker's budget and three to four orders of
# magnitude above every other operator in objective per second.  The WSTAT lines then showed that
# prob_1's answer is decided by whether ANY of four diverse draws reaches a good basin.  Put those
# together and beam throughput is not a side issue: a faster beam is more draws, and more draws is
# a tighter minimum.  This is the one lever that needs no judgement about which direction is right.
#
# Everything here is ALREADY COMPILED INTO THE SHIPPED .so and gated by an environment variable, so
# none of it needs a rebuild and none of it can invalidate the measurements taken against that
# binary.
#
#     OGC_FCACHE=1   the OR-stamp grid cache, default OFF.  The (occ,F) pair for a
#                    (bay, window, content) key is memoised thread-locally, so the many sibling beam
#                    states that share a bay's contents skip the O(placed x footprint) layer
#                    stamping and pay only the O(placed) content hash.  Its own note records that a
#                    wrong hit could only mark an infeasible cell clear, which the committed
#                    placement then fails on and best-of discards -- it cannot produce a wrong
#                    accepted answer, only a slower or faster search.
#
#     OGC_PPQ=0      per-parent quota OFF.  On by default: it caps children per parent at
#                    max(2,(B+1)/2) so one strong parent cannot fill the beam with its own
#                    children.  It costs rank quality per level and buys structural diversity.  With
#                    m=2 now shipped, states already diverge in WHICH blocks they placed, so the
#                    quota may be buying diversity that the m portfolio already provides.
#
#     OGC_ADAPTK=0   adaptive K pinned.  On by default, it raises candidates-per-state when the
#                    width controller has spare budget.  That competes with width for the same
#                    seconds and has never been read on its own.
#
#     OGC_THRUBEAM=1 not a speed knob -- a different beam OBJECTIVE.  It ranks states almost purely
#                    by tardiness plus an amplified lookahead and DROPS the Z3 preference term as
#                    noise where Z1 dominates.  That is exactly the saturated-instance case, which
#                    is where the hidden set's large instances live (P2 19.8M, P8 17.3M) and where
#                    every direction tried tonight has been wrong.  It is off by default and has
#                    never been measured.
#
# OGC_ARPRE is deliberately excluded: its own note says the audit does not read zero and it took
# prob_38 from 41.1M to 104.4M when last enabled.
#
# BEAMSTAT on every cell, so each one reports work= -- state expansions actually performed -- and
# the arms can be compared on throughput as well as on the objective they reached.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo speed > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=speed" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/speed.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/speed.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: speed $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_BEAMSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py \
        myalgorithm $2 $3 "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

# prob_16 first: 300 blocks, the beam is slice-bound there, so a throughput change should show up
# in work= most clearly.  prob_1 second because it is the priority and because its answer depends
# on draw count more visibly than anywhere else.
for p in 16 1; do
  run "s.p$p.base"    $p 240 ""
  run "s.p$p.fcache"  $p 240 "OGC_FCACHE=1"
  run "s.p$p.noppq"   $p 240 "OGC_PPQ=0"
  run "s.p$p.noadk"   $p 240 "OGC_ADAPTK=0"
done
echo "== SPEED knobs done ==" >> $L

# the throughput-objective beam, on the two saturated instances it was written for
for p in 36 6 20; do
  run "s.p$p.base"  $p 240 ""
  run "s.p$p.thru"  $p 240 "OGC_THRUBEAM=1"
done
echo "SPEEDDONE" >> $L
echo idle > harness/CURRENT
