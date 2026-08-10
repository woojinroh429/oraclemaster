#!/bin/bash
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while ! grep -q BSPLITDONE results/audit/bsplit.log 2>/dev/null; do sleep 30; done
exec bash harness/all40.sh
