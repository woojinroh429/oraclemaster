#!/bin/bash
# Guard on the interpreter, anchored: a bare "harness/run1.py ..." pattern also matches the
# tool-wrapper shells that launched the runs, and that stalled this queue once for 25 minutes.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/run1\.py' >/dev/null; }
while busy; do sleep 20; done
for i in 1 2; do
  python3.12 harness/run1.py myalg_orig 6 900 "origv2"
  python3.12 harness/run1.py myalg_base 6 900 "origv2+coh"
done
echo P6CMP-DONE
