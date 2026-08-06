#!/bin/bash
# WHERE DOES THE BAD DRAW COME FROM?  Two spreads, measured together because they cost the same.
#
# The answer algorithm() returns is a minimum over nw workers, and `best` only ever moves down --
# the top-level ratchet is correct, and the final polish is guarded the same way.  So a run that
# lands 20% worse than the run before it did not throw a good solution away.  Every worker in that
# run missed the good basin.
#
# That makes two numbers worth having, and one run with OGC_WSTAT=1 yields both:
#
#   RUN-TO-RUN spread -- the same instance, same build, replicate to replicate.  This is the risk
#   the score actually carries, and it is what "sometimes it goes bad" means.
#
#   INTRA-ROUND spread -- how far apart the nw workers of a single run finish.  This decides
#   whether more DRAWS can help.  If the workers all converge to the same objective, nw cores are
#   buying one draw, the minimum is over a sample of size one, and OGC_ROUNDS (already
#   implemented, defaulting to 1) is a large untaken lever.  If they are already far apart, the
#   minimum is over a real sample and shortening each round to buy more of them may cost more
#   than it returns.
#
# Which instances carry the tail is measured here rather than recalled.  The rounds A/B that
# follows targets whatever this finds, so it cannot be aimed at instances chosen to flatter it.
#
# Three replicates is enough to SEE a one-in-three tail, not to size it.  That is the right
# resolution for choosing targets; the arm that has to survive a decision gets more.
set -u
cd "$(dirname "$0")/.." || exit 1
echo wspread > "$(dirname "$0")/CURRENT"
L=results/audit/wspread.log
mkdir -p results/audit; touch $L

for rep in 1 2 3; do
    for p in 1 3 6 9 12 16 20 25 26 30 36 40; do
        grep -q "^# \[r$rep\.p$p\]" $L 2>/dev/null && continue
        echo "# [r$rep.p$p]" >> $L
        OGC_WSTAT=1 timeout 300 /usr/bin/python3.12 harness/run1.py myalgorithm $p 60 "[r$rep.p$p]" \
            --data data/stage2 >> $L 2>&1
        ( cd "$(git rev-parse --show-toplevel)" \
          && git add research/exact_packer/session2/recon/results/audit/wspread.log \
          && git commit -q -m "in-flight: wspread r$rep p$p" ) >/dev/null 2>&1
    done
done
echo "WSPREADDONE" >> $L
echo idle > "$(dirname "$0")/CURRENT"
