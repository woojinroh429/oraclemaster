#!/bin/bash
# brk -> cross.  chain2 then picks up on CROSSDONE and chain3 on BSPLITDONE, so the four queues
# run back to back without two of them ever sharing the four cores -- which is what corrupted
# three cells earlier tonight.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while ! grep -q BRKDONE results/audit/brk.log 2>/dev/null; do sleep 30; done
exec bash harness/cross.sh
