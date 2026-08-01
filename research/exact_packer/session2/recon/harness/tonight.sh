#!/bin/bash
# Unattended chain: finish verifying the mask packer, KEEP OR REVERT IT ON THE MEASUREMENT,
# then run the overnight queue.
#
# The decision is not mine to make in advance, so it is written as a rule here:
#
#   placement not IDENTICAL   revert.  A faster packer that changes an answer is not a
#                             faster packer, it is a different one.
#   speedup < 1.05x           revert.  The last two attempts were 0.9x; a filter that does
#                             not pay is dead weight in the hot loop and one more thing to
#                             explain later.
#   otherwise                 keep, and record the number.
#
# Reverting is safe: cranepack.old.so is the binary every result quoted today was produced
# with, so the overnight queue runs against known ground either way.
set -u
cd "$(dirname "$0")/.." || exit 1
SCRATCH=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
SO=cranepack.cpython-312-x86_64-linux-gnu.so

# the verification may already be running from the foreground; wait for it either way
while pgrep -f "harness/packspeed.py" >/dev/null 2>&1; do sleep 20; done
if [ ! -s results/packspeed_mask.log ]; then
    echo "=== verifying the mask packer $(date -u +%H:%M:%S)"
    cp "$SCRATCH/cranepack.mask.so" "$SO"
    timeout 3600 python3.12 harness/packspeed.py > results/packspeed_mask.log 2>&1
fi
cat results/packspeed_mask.log

KEEP=1
grep -q "IDENTICAL" results/packspeed_mask.log || KEEP=0
python3.12 - <<'PY' || KEEP=0
import re, sys
txt = open("results/packspeed_mask.log").read()
sp = [float(m) for m in re.findall(r"([0-9.]+)x", txt)]
ok = bool(sp) and (sum(sp) / len(sp)) >= 1.05
print("mean speedup %.2fx -> %s" % ((sum(sp) / len(sp)) if sp else 0.0, "KEEP" if ok else "REVERT"))
sys.exit(0 if ok else 1)
PY
if [ "$KEEP" = "1" ]; then
    echo "=== keeping the mask packer"
else
    echo "=== reverting to the packer every result today was measured on"
    cp "$SCRATCH/cranepack.old.so" "$SO"
    ( cd ../../.. && git checkout HEAD -- research/exact_packer/session2/recon/cranepack.cpp 2>/dev/null )
fi
( cd ../../.. && git add -f research/exact_packer/session2/recon/results/packspeed_mask.log >/dev/null 2>&1 \
  && git commit -q -m "overnight: mask packer verdict" >/dev/null 2>&1 \
  && git push -q origin claude/repair-plan-model-1ig6it >/dev/null 2>&1 )

exec bash harness/overnight.sh
