#!/bin/bash
# PRICE r BEFORE ANYONE WRITES THE GEOMETRY-LEVEL CONFLICT GRAPH.
#
# THE IDEA, from results/audit/conflictfactor.md.  cranepack's cost is one loop over every pair of
# placement columns.  It is calibrated at 6.4e-8 s per squared column -- ncol 11,580 costs 8.3 s,
# 24,318 costs 39.1 s -- and OGC_OPSTAT prices the whole brk operator at 34-36 s, 22-23% of a
# worker.  Every cheap optimisation is already in it: bay-first sort with a break, entry sort with
# a break, flat arrays, an AABB pre-filter, a memo keyed on relative offset.
#
# What is left is the predicate's own algebra:
#
#     conflict(A,B) = timeoverlap(A,B) AND ( R OR (AoverB AND U) OR (BoverA AND V) )
#
# with R, U, V functions of the GEOMETRY alone and time entering only as three integer compares.
# Columns are generated as (block, orient, x, y) x (entry window), so r = ncol / geom_slots columns
# share one (R,U,V) and column pairs outnumber geometry pairs by r^2.  A geometry pair with
# R=U=V=0 cannot conflict at any entry combination, and the loop presently visits and rejects all
# nA x nB of its column pairs one at a time.
#
# WHY THIS RUNS BEFORE ANY CODE IS WRITTEN.  conflictfactor.md ends by naming the one number that
# decides it and recording that the number has never been measured: "If r is near 1 the
# factorisation buys nothing and the grid is the only lever; if r is 5 the enumeration falls by up
# to 25x."  A 25x-or-nothing rework with ~24 hours left is exactly the case where the sizing
# measurement comes first.  This is the same order applied to idlegap (which sized the gap before
# proposing a fix) and the opposite of how the -fopenmp branch was opened, on two lucky cells.
#
# CRANEPACK_COLSTAT=1 prints ncol, geom_slots and their ratio and changes no decision the solver
# makes -- but it is NOT free: it builds a std::set over every column, so the WALL of these runs is
# not comparable to a normal run and no objective from this queue may be used as a measurement.
# It prices the ratio, not the runtime.
#
# INSTANCES.  brk has to actually run for the line to print, and results/audit records brk paying
# on prob_3 and prob_16 (P3 80,795 against 96,990 with it off).  prob_13 and prob_2 are the
# largest instances and are where ncol is biggest, so they are where the r^2 factor would matter
# most if it exists.  prob_1 and prob_20 for breadth.
#
# JUDGED, fixed before the run.  This queue decides nothing about the objective.  It reports r.
#   * r < 1.5 across the set  -> the factorisation is dead, and the grid is the only remaining
#     lever on this operator.  Say so and close it.
#   * r >= 3                  -> enumeration falls by up to r^2; worth costing the rework against
#     the time remaining, WITHOUT committing to it here.
#   * A run where the COLSTAT line never prints means brk did not run on that instance at 60 s,
#     which is itself an answer -- the operator is not on the critical path there.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire colstat
L=results/audit/colstat.log
mkdir -p results/audit; touch $L
for p in 3 16 13 2 1 20; do
    tag="p$p"
    grep -q "^# \[$tag\]" $L 2>/dev/null && continue
    echo "# [$tag]" >> $L
    env CRANEPACK_COLSTAT=1 OGC_WSTAT=1 timeout 200 /usr/bin/python3.12 \
        harness/run1.py myalgorithm $p 60 "[$tag]" --data data/stage2 2>&1 \
        | grep -E 'COLSTAT|^P[0-9]' >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/colstat.log \
                research/exact_packer/session2/recon/harness/colstat.sh \
                research/exact_packer/session2/recon/harness/CURRENT \
      && git commit -q -m "in-flight: colstat $tag" \
      && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1
done
echo "COLSTATDONE" >> $L
lock_release colstat
