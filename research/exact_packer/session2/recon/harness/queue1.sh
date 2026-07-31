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

# A. prefw at conw=0.  The candidate score was -1.0*ct + position*0.1 + prefw*pen, so contact
#    outweighed preference tenfold and prefw measured "inert" early in the session -- it could
#    never flip an argmin.  With contact off it competes directly, and it targets Z3, which is
#    79% of P3's objective at the current best (462*150 = 69,300 of 87,560).
for P in 0.0 0.5 2.0 8.0; do
    OGC_PREFW=$P OGC_DK=0 python3.12 harness/mkbase.py 0.3 "myalg_pf${P/./_}.py" 0 "" 0 1.0 "" 0 0.0 >/dev/null || exit 1
done
for rep in 1 2; do
  for P in 0.0 0.5 2.0 8.0; do run "myalg_pf${P/./_}" 3 240 "pf=$P r$rep" "pf_${P}_r${rep}.log"; done
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
