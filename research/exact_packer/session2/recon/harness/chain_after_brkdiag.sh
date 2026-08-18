#!/bin/bash
# Serialise brkbig then m120 behind whatever is running, without two waiters racing for the lock.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
bash harness/brkbig.sh
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
bash harness/m120.sh
