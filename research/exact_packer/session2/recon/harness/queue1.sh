#!/bin/bash
# ONE queue, strictly sequential.  Every experiment in this session that overlapped another gave
# a number that had to be thrown away: earlier it was two chains released by the same completion
# marker, running ten processes on four cores.  Chained scripts that each wait on a different
# condition are not a schedule, they are a race.  Everything pending goes here, in order, one at
# a time, and nothing else runs.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
run () {  # module prob limit tag outfile
    [ -s "results/$5" ] && return
    echo "=== $5  ($4)  $(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "$1" "$2" "$3" "$4" > "results/$5" 2>&1
    tail -1 "results/$5"
    ( cd .. && git add -f "session2/recon/results/$5" >/dev/null 2>&1 )
}

# A. w3mul at conw=0.25 -- the only LIVE path to Z3.
#
#    prefw looked like the preference lever and is not one.  It enters the per-cell score, where
#    the bay penalty is constant across the cells being compared and so cannot change which one
#    wins; and it enters the per-bay drank, which is sorted and truncated to top-K, with K >= the
#    bay count on every instance so nothing is ever dropped.  Both sites are dead for exactly the
#    reason the beam's anchor was, and the file already says so at the drank site.  Measured:
#    prefw 0.0, 2.0 and 8.0 all returned 100,535 with identical Z2 and Z3 on P3.
#
#    The bay is chosen by the STATE rank, w1*gt + w3_route*gz3 - mu*gcontact + w2*obj2, and
#    w3_route = w3 * w3mul.  That dial is live, sits on Z3 (79% of P3's objective at the current
#    best), and has never been swept -- the axes carry 1.0 to 6.0 as hand-set values.
for W in 1 3 6 12 24; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_w3m${W}.py" 0 "" 0 1.0 "" 0 0.25 "" "$W" >/dev/null || exit 1
done
python3.12 - <<'PY'
import myalg_w3m1 as A, myalg_w3m24 as B
assert [x["w3mul"] for x in A._AXES] == [1.0]*6, A._AXES[0]
assert [x["w3mul"] for x in B._AXES] == [24.0]*6, B._AXES[0]
assert A._AXES[1]["conw"] == 0.25 and B._AXES[1]["conw"] == 0.25
print("w3mul arms verified at conw=0.25: 1 .. 24")
PY
for rep in 1 2; do
  for W in 1 3 6 12 24; do run "myalg_w3m${W}" 3 240 "w3mul=$W r$rep" "w3m_${W}_r${rep}.log"; done
done

# B. contact off at BOTH levels.  conw kills it in candidate choice; mu = 1e-3*min(w1,w3)*mum
#    still ranks STATES by -mu*gcontact.  With both off the key is w1*gt + w3*gz3 + w2*obj2 +
#    w1*hz, which on P3 (gt = 0) is exactly the objective -- Z2 and Z3 together, no surrogate.
for M in 1.0 0.0; do
    OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_mm${M/./_}.py" 0 "" 0 1.0 "" 0 0.0 "$M" >/dev/null || exit 1
done
for rep in 1 2; do
  for M in 1.0 0.0; do run "myalg_mm${M/./_}" 3 240 "mum=$M r$rep" "mum_${M}_r${rep}.log"; done
done

# D. Where the spread comes from.  P3 swings 9% at conw=1.0 and 0% at conw=0.25, and the worker
#    allocates its budget by probing each operator for a rate then backing the best -- so a
#    probe decided by timing noise redirects everything after it.  If the spread is convergence,
#    a longer budget collapses it and speed work pays twice; if it survives 480s, the allocator
#    is the cause and speed will not touch it.  The finals may give LESS time, so this matters.
for T in 120 480; do
  for rep in 1 2 3; do run myalg_cw1_0 3 $T "budget=$T r$rep" "bud_${T}_r${rep}.log"; done
done
# C. THE GATE -- LAST, and deliberately not a tuning step.
#
#    Picking conw by what keeps P4/P5/P6 intact would fit a constant to the six instances we can
#    see, and if the finals use different ones that is overfitting with extra steps.  So this
#    runs only to learn WHERE contact stops paying, not to choose a number to ship.
#
#    What should ship is not a constant at all.  Contact earns its place when free space is
#    scarce and costs when it is not -- that is a statement about congestion, not about which
#    instance is which -- so the weight belongs downstream of a measured occupancy, where there
#    is nothing left to fit.  These runs say what that function has to reproduce at the two ends.
# C. THE GATE.  conw=0.25 is the P3 winner (92,930 three times out of three, zero spread).
#    Contact is the right instinct at P4/P5/P6 densities, so this is where it is expected to
#    cost.  The arithmetic is brutal: P3 gains ~4,000, but 0.1% of P5 is 9,000 and 0.03% of P6
#    is 8,000 -- either can erase it.  Per-instance values would be overfitting and are not an
#    option, so this decides adoption outright.
OGC_DK=0 python3.12 harness/mkbase.py 0.3 myalg_cw0_25.py 0 "" 0 1.0 "" 0 0.25 >/dev/null || exit 1
for p in 4 5 6; do
    case $p in 4) L=480;; 5) L=600;; 6) L=900;; esac
    run myalg_cw1_0  $p $L "conw=1.0"  "gate_p${p}_1.0.log"
    run myalg_cw0_25 $p $L "conw=0.25" "gate_p${p}_0.25.log"
done

echo "queue1done  $(date -u +%H:%M:%S)"
