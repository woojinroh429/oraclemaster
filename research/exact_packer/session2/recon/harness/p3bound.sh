#!/bin/bash
# DID THE CONTACT BOUND KILL P3's 83,095?
#
# 80,795 is not luck.  Every P3 run that ever reported it had a brk attempt of exactly 83,095 in
# its log, and every run that did not report it had no such attempt -- no exceptions across the
# whole day:
#
#   14:10  rel_p3     80,795   83,095 present
#   14:52  rl_p3_r2   90,225   absent
#   15:14  ac_p3      80,795   83,095 present
#   15:29  askcap     80,795
#   16:44  fx_p3      86,975   absent      <- first run on the .so rebuilt at 16:39
#   17:24  fx_p3_r2   87,175   absent
#
# So 80,795 is a specific solution reached through a specific brk result, and something after
# 15:29 stopped that result appearing.  The only live change in the window is the contact bound
# (the instrumentation adds counters, the early exit was implemented and reverted).
#
# The mechanism would be indirect and is worth stating precisely, because the bound provably does
# not change what the beam ANSWERS -- identical placement digests on P3/P4/P6.  It changes how far
# the beam gets in a fixed budget, which changes the incumbent handed to brk, which changes what
# brk returns.  A faster search arriving somewhere worse is a real effect, not a contradiction.
#
# NOT CONCLUSIVE YET, and that is why this runs.  Before the bound P3 hit 80,795 in three runs out
# of four; after it, zero out of two.  3/4 against 0/2 is suggestive and nothing more.  Four
# bound-off samples at the shipped budget say whether 83,095 comes back.
#
# Blocks on the experiment lock, so it queues behind the P5 isolation instead of contending.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

for r in 1 2 3 4; do
    f="results/p3_nobound_r$r.log"
    [ -s "$f" ] && continue
    echo "=== P3 bound OFF r$r $(date -u +%H:%M:%S)"
    # bound-off is the DEFAULT now; OGC_NOPRUNE is no longer read by the engine
    BRK_DEBUG=1 timeout 1500 \
        python3.12 harness/run1.py myalgorithm 3 240 "P3 nobound r$r" > "$f" 2>&1
    echo "    $(grep -h '^P3 ' "$f" | tail -1)"
    echo "    brk: $(grep -o 'obj [0-9]* vs base' "$f" | grep -o '[0-9]*' | sort -n | tr '\n' ' ')"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/$f" >/dev/null 2>&1 \
      && git commit -q -m "P3 bound-off r$r" >/dev/null 2>&1 \
      && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )
done
echo "p3bound done $(date -u +%H:%M:%S)"
