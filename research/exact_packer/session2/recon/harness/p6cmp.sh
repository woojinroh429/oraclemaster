#!/bin/bash
cd "$(dirname "$0")/.."
while pgrep -f "harness/run1.py myalg_v2" >/dev/null; do sleep 20; done
python3.12 harness/run1.py myalg_orig 6 900 "origv2"
python3.12 harness/run1.py myalg_base 6 900 "origv2+coh"
python3.12 harness/run1.py myalg_orig 6 900 "origv2"
python3.12 harness/run1.py myalg_base 6 900 "origv2+coh"
echo P6CMP-DONE
