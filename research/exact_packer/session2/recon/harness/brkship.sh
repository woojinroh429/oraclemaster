#!/bin/bash
# DOES MAKING brk CHEAP REMOVE THE INSTANCES IT COSTS?
#
# brk is measured and it is a trade: prob_1 -6.5% over three replicates with no cell worse and the
# run-to-run range collapsing from 16.5% to 2.0%, against +0.34% on prob_3, +2.14% on prob_16,
# +1.84% on prob_24 and +1.72% on prob_20.  The losses are all the same size and they have one
# cause -- OGC_OPSTAT prices the operator at 34-36 s, 22-23% of a worker, taken from a beam that
# returns 8.1M objective units per second against 17.5K for the next best thing.
#
# The acceleration queue then found two levers that both reach 422,629, this project's best number
# on prob_1, by different routes:
#
#     nout50   half the outsider candidates -> a QUARTER of the edges, the graph being quadratic
#     th2      two threads around CP.pack only
#     nout25   437,484   +3.5%    too few candidates to repack with
#     th4      485,018  +14.8%    16 threads on 4 cores, and the grader is 4 cores too
#
# So both levers have an interior optimum and both land on the same solution, which is what you
# expect if the mechanism is "brk costs less, the beam gets the seconds back".
#
# WHAT THIS QUEUE DECIDES.  Whether that also erases the +1.7-2.1% on the instances brk currently
# costs.  If it does, brk stops being a trade and ships; if the losses survive a cheaper brk, they
# are not about its price and the operator has to be gated on something -- Z3 share is the
# candidate, being 86.3% on prob_1 against 15.1-48.7% on the three that pay.
#
# The instances that PAY run first, because they are what the decision turns on.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo brkship > harness/CURRENT
L=results/audit/brkship.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/brkship.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: brkship $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 OGC_OPSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}
for rep in 1 2; do
  for p in 16 20 24; do
    run "r$rep.p$p.off"    $p 240 ""
    run "r$rep.p$p.brk"    $p 240 "OGC_BRK=1"
    run "r$rep.p$p.fast"   $p 240 "OGC_BRK=1 OGC_TIERNOUT=0.5"
  done
done
echo "== BRKSHIP cost instances done ==" >> $L
for rep in 1 2 3; do
  run "r$rep.p1.off"   1 240 ""
  run "r$rep.p1.fast"  1 240 "OGC_BRK=1 OGC_TIERNOUT=0.5"
done
echo "BRKSHIPDONE" >> $L
echo idle > harness/CURRENT
