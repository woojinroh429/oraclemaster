#!/bin/bash
# Wait for the CROSS queue's completion MARKER rather than for a process name.  chain.sh execs
# from rfsplit.sh into cross.sh, so there is a window where neither process exists and a
# pgrep-based wait would fire into a still-busy machine.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while ! grep -q CROSSDONE results/audit/cross.log 2>/dev/null; do sleep 30; done
exec bash harness/bsplit.sh
