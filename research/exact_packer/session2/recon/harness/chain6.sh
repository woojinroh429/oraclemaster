#!/bin/bash
# brkfast -> cross.  chain2 then takes CROSSDONE -> bsplit, chain3 BSPLITDONE -> all40.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while ! grep -q BRKFASTDONE results/audit/brkfast.log 2>/dev/null; do sleep 30; done
exec bash harness/cross.sh
