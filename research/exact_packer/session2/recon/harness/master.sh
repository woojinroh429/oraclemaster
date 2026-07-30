#!/bin/bash
# The whole night's plan for P3/P4/P5, as one resumable list.
#
# The container has reset five times in this session and each reset killed whatever queue was
# running, so the plan is written to survive that: every step writes a sentinel when it
# finishes, and re-running this script skips what is already done.  Recovery is therefore
#
#     git fetch && git reset --hard origin/<branch>
#     harness/restore.sh
#     harness/master.sh
#
# and nothing is repeated or lost.  supervisor.sh keeps it alive within a container's lifetime;
# the sentinels handle everything across one.
#
# Targets: P3 80,000  P4 22,000,000  P5 8,000,000.  What the floors say about each:
#   Z1's lower bound is 0 on all three -- no deadline is impossible, so tardiness is congestion.
#   P3 needs 17,135 and Z3 holds 62,550 of recoverable cost.  Its Z1 is 0: preference and
#      balance only, no scheduling problem at all.
#   P5 needs 1,044,458 and Z3 holds 458,185 of it.  The rest must come from Z1, 94% of its score.
#   P4 sits between them at demand ratio 0.702.
set -u
cd "$(dirname "$0")/.."
mkdir -p _n
# Refuse to run twice.  A hand-started master and a supervisor-started one both ran for a while
# tonight: two of them share four cores, so every timing either takes is contended -- which is
# exactly how a P5 pair got corrupted earlier in this session.
exec 9>_n/master.lock
flock -n 9 || { echo "another master already holds the lock" >&2; exit 0; }
DONE=_n/master.done
LOG=_n/master.log
touch "$DONE"

step() {                     # step <name> <cmd...>
  local name="$1"; shift
  grep -qx "DONE $name" "$DONE" && return 0
  echo "[$(date -u +%H:%M:%S)] START $name" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  echo "[$(date -u +%H:%M:%S)] END   $name" >> "$LOG"
  echo "DONE $name" >> "$DONE"
}

P=python3.12

# --- A. baselines at the real limits ---------------------------------------------------------
# The last numbers for these three are scattered across a night of logs and half of them predate
# the engine fixes, so nothing downstream is trustworthy until they are re-pinned.
for p in 3 4 5; do
  for m in myalg_orig myalg_base myalgorithm; do
    step "base-$p-$m" $P harness/base345.py $p $m
  done
done
step "headroom" $P harness/headroom.py

# --- B. does the construction family reach P3/P4/P5 at all? ----------------------------------
# Anchored on each instance's own best construction (bigleft/rank), not on P6's sac3 -- the
# earlier P5 attempt used P6's anchor and started 19% behind, which is why its verdict was
# withdrawn.
step "fair-5-777"  $P harness/grasp.py 5 400 100 6 bigleft 777  rank
step "fair-5-4242" $P harness/grasp.py 5 400 100 6 bigleft 4242 rank
step "fair-4-777"  $P harness/grasp.py 4 300 100 6 bigleft 777  rank
step "fair-3-777"  $P harness/grasp.py 3 150 60  6 bigleft 777  rank

# --- C. Beam-GRASP where the beam is the better decoder --------------------------------------
# P5's beam completes and is deterministic, so its budget past the first beam is idle -- the
# same pathology the fixed construction had on P6.  k=1 reproduces the fixed order exactly.
for k in 3 5; do
  step "bg-5-k$k" $P harness/bgrasp.py 5 600 $k myalg_base 777 1
done
step "bg-4-k3" $P harness/bgrasp.py 4 480 3 myalg_base 777 1
step "bg-3-k3" $P harness/bgrasp.py 3 240 3 myalg_base 777 1

# --- D. P3 is a preference problem: attack Z3 directly ---------------------------------------
# Z1 = 0 on P3, so nothing here is about tardiness.  The construction carries preference-first
# modes the beam has no equivalent of -- prefaware puts preference at the head of the key,
# prefmid grades it -- and on an instance with no tardiness to trade they should be exactly
# right rather than exactly wrong.
for m in prefaware prefmid flatbl; do
  step "p3-mode-$m" $P harness/bigleft.py 3 120 $m 1 rank 0.60
done
step "p3-grasp-prefaware" $P harness/grasp.py 3 150 60 6 prefaware 777 rank
step "p3-grasp-prefmid"   $P harness/grasp.py 3 150 60 6 prefmid   777 rank
# and the same question for P4, which is 20% Z3
for m in prefaware prefmid; do
  step "p4-mode-$m" $P harness/bigleft.py 4 120 $m 1 rank 0.60
done

# --- E. repeats, so nothing is concluded from one draw ---------------------------------------
step "fair-5-99"   $P harness/grasp.py 5 400 100 6 bigleft 99 rank
step "bg-5-k3-b"   $P harness/bgrasp.py 5 600 3 myalg_base 4242 1
step "fair-4-4242" $P harness/grasp.py 4 300 100 6 bigleft 4242 rank

echo "[$(date -u +%H:%M:%S)] MASTER-PLAN-COMPLETE" >> "$LOG"
