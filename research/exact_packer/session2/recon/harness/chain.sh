#!/bin/bash
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while pgrep -f "rfsplit.sh" >/dev/null 2>&1; do sleep 20; done
exec bash harness/cross.sh
