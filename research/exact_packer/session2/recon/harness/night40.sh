#!/bin/bash
# Sweep shad_lam on P5, the knob the crane measurement just justified.
#
# The paired count on one shipped P5 solution:
#
#                       own bay            all bays
#   full descent rule    878 (4.4/block)   1,120 (5.6/block)
#   j == k only        1,312 (6.6/block)   2,332 (11.7/block)
#   lost to descent        33%                52%
#
# So a third of a block's legal positions in its own bay are taken by descent shadows rather
# than by anything occupying the space.  shad_lam is the beam term aimed exactly at that -- it
# penalises a placement by its overhang, union/layer0 - 1, which is what casts the shadow.
#
# It has never been swept honestly.  Earlier in this session shadow/span/lex silently failed to
# reach _contact_beam, so a sweep of them measured the control several times over and read as
# "the term does nothing".  mkbase.py now asserts the forwarding site exists, so this is the
# first real reading.
#
# Paired against shadow=0, same engine, same limit, sequential.  P4 runs too: a term that only
# helps the instance it was tuned on is overfitting, and P4 is the one instance whose score is
# settled, so it is the one that can least afford a regression.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
for SH in 0.0 0.5 1.5 4.0; do
    mod="myalg_sh${SH/./_}"
    python3.12 harness/mkbase.py 0.3 "${mod}.py" "$SH" > /dev/null || exit 1
done
echo "arms built  $(date -u +%H:%M:%S)"
declare -A LIM=([5]=600 [4]=480)
for p in 5 4; do
  for SH in 0.0 0.5 1.5 4.0; do
    mod="myalg_sh${SH/./_}"
    out="results/shad_p${p}_${SH}.log"
    [ -s "$out" ] && continue
    echo "=== P$p shadow=$SH (${LIM[$p]}s)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$mod" "$p" "${LIM[$p]}" "shadow=$SH" > "$out" 2>&1
    tail -1 "$out"
    ( cd .. && git add -f "session2/recon/$out" >/dev/null 2>&1 )
  done
done
echo "done  $(date -u +%H:%M:%S)"
