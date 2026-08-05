#!/bin/bash
# Runs when the replicate queue frees the CPU.  Deliverables before the next experiment: the
# package has been stale since 08-04 and the aim ladder is exploratory.
#
#   1. rebuild every ABI.  Both .cpp files gained the source stamp, so all eight binaries
#      disagree with their source now, not just the three that were two days behind.
#   2. rebuild the zip.  mkzip refuses to package a set whose stamps do not match, so (1) has
#      to succeed first -- that is the point of the check.
#
# The ladder is launched separately and only after this, so it runs entirely on one binary.
set -u
cd "$(dirname "$0")/.." || exit 1

while pgrep -f "harness/rep722\.sh" >/dev/null; do sleep 20; done
echo "== replicate queue done at $(date +%T); rebuilding =="

bash harness/buildabi.sh || { echo "BUILD FAILED -- not packaging"; exit 1; }
bash harness/mkzip.sh    || { echo "PACKAGE FAILED"; exit 1; }
echo "AFTERREPDONE $(date +%T)"
