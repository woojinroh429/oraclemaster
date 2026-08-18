#!/bin/bash
# ON prob_1, THREE OF THE FOUR WORKERS ARE NOT PARTICIPATING.
#
# The share queue was stopped two replicates in because the per-worker lines answered its question
# and a different one.  Six cells, every worker printed:
#
#     r1.off       w0=472330   w1=596780   w2=504490   w3=787370
#     r1.share     w0=422629   w1=738538   w2=504490   w3=682240
#     r1.share3    w0=438791   w1=738538   w2=504490   w3=752084
#     r2.off       w0=438791   w1=772500   w2=504490   w3=689851
#     r2.share     w0=438791   w1=760047   w2=504490   w3=682240
#     r2.share3    w0=472330   w1=788591   w2=504490   w3=678163
#
# WHAT THE SHARE ARMS DID.  The restarts fire exactly where they were meant to -- w1 and w3, at
# 32-44% of the budget, against a leader 76-103% ahead -- and the restarted workers come back at
# 678k-788k.  They were at 596k-788k before.  A fresh seed on the ODD configuration lands in the
# same region a fresh seed on the odd configuration always lands in, because what is wrong with
# those workers on this instance is not their basin, it is their CONFIGURATION.  The mechanism
# works and cannot reach.
#
# WHAT THE OTHER TWO COLUMNS SAY.  w2 returns 504,490 in all six cells, to the digit, under three
# different arms -- a frozen draw.  w0 is the only worker whose value moves and the only worker
# that ever holds the minimum.  On this instance the answer is a minimum over ONE draw.
#
# THE TEST.  wid decides a worker's configuration through three `wid % 2` lookups and its diversity
# through `random.Random(1234 + wid)` and `_AXES[(wid + i) % 6]`.  Pinning the configuration in the
# environment leaves the seed and the axis rotation still keyed to wid, so four workers all on the
# even configuration are four INDEPENDENT draws of it -- exactly what parityfill.md proposes to do
# with the idle tail, but for the whole run and with no code change.
#
#     even = OGC_MCAND=1 OGC_BEAMAIM=0.90 OGC_ORDER=lst OGC_W3MUL=0.5     (w0, w2 today)
#     odd  = OGC_MCAND=2 OGC_BEAMAIM=0.10 OGC_DIRSET=0                    (w1, w3 today)
#
# WHAT WOULD REFUTE IT.  The odd pair wins 8% of prob_1 runs, and a minimum keeps whatever is lower,
# so those 8% may be a tail the even configuration cannot reach.  If alleven never beats ship, that
# is what they were.  And the risk is symmetric: prob_20 is 94% odd and prob_16 80% odd, so allodd
# has to win there by the same margin or the whole idea is instance-fitting.  Both are in the queue,
# and every cell is read per WORKER as well as per minimum -- four observations a cell instead of
# one, which is what made two replicates enough to stop the share queue.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
echo parity > harness/CURRENT
( cd "$(git rev-parse --show-toplevel)" \
  && git add research/exact_packer/session2/recon/harness/CURRENT \
  && git commit -q -m "queue: CURRENT=parity" \
  && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
L=results/audit/parity.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/parity.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
        && git commit -q -m "in-flight: parity $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }

run(){ # tag prob limit env
    local tag="$1"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout $(( $3 * 4 )) /usr/bin/python3.12 harness/run1.py myalgorithm $2 $3 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$2 [$tag] CRASH rc=$?" >> $L
    ci "$tag"
}

EVEN="OGC_MCAND=1 OGC_BEAMAIM=0.90 OGC_ORDER=lst OGC_W3MUL=0.5"
ODD="OGC_MCAND=2 OGC_BEAMAIM=0.10 OGC_DIRSET=0"

# prob_1 first and with four replicates: it is the instance the priority is about and the one the
# per-worker lines say is running on one cylinder.
for rep in 1 2 3 4; do
  run "r$rep.p1.ship"    1 240 ""
  run "r$rep.p1.alleven" 1 240 "$EVEN"
  run "r$rep.p1.allodd"  1 240 "$ODD"
done
echo "== PARITY prob_1 done ==" >> $L

# the symmetry check, on the two instances the ODD pair owns (94% and 80% of wins).  If allodd does
# not win there, the split is not reading a real property of the instances and neither arm ships.
for rep in 1 2; do
  for p in 20 16; do
    run "r$rep.p$p.ship"    $p 240 ""
    run "r$rep.p$p.alleven" $p 240 "$EVEN"
    run "r$rep.p$p.allodd"  $p 240 "$ODD"
  done
done
echo "PARITYDONE" >> $L
echo idle > harness/CURRENT
