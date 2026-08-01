#!/bin/bash
# CRANE-RULE CUTS instead of area tightening.  The last direction with an argument behind it.
#
# THE DEFECT.  _assign is already a Benders/LBBD loop: CP-SAT proposes an assignment, _realise
# tries to pack it, and where it spills the loop multiplies that bay's capacity factor by 0.90.
# But the row CP-SAT solves under is AREA --
#
#     sum(x[b][k] * area[b] for b present at t) <= cap[k] * capf[k]
#
# -- and area does not bind on P3.  Measured: first-choice demand over capacity is 0.48 for bay
# 0, 0.12 for bay 1, 0.15 for bay 2.  The master optimises under a constraint that forbids
# nothing, proposes an assignment near the 36,765 bound, _realise fails on the CRANE rule, and
# the loop tightens area, which was never the reason.  The capacity-aware bound is 36,765 and we
# sit at 86,665; that entire gap is this.
#
# THE CUT, AND WHY IT COSTS NOTHING.  _realise already knows which block failed which bay -- it
# does hot[want[b]] += 1 the moment feasible_scan comes back empty under the descent rule, and
# throws the identity away.  Recording it adds no oracle call:
#
#     S = {b} + the blocks the plan put in bay k whose [ent,ext) overlaps b's window
#     sum(x[q][k] for q in S) <= |S| - 1
#
# A statement about the crane rule rather than about area, produced by the packer itself.
#
# HONEST LIMIT.  _realise packs greedily in a fixed order, so its failure is evidence and not a
# proof: some S it rejects may be packable in another order, and the cut would then exclude a
# feasible assignment.  Two things bound that -- the cut forbids only the EXACT full set, so
# near-identical assignments survive, and everything is still scored on the true objective
# inside best-of, so a wrong cut costs search quality and never correctness.
#
# Three pairs, interleaved, against the same build with the cuts off.
set -u
cd "$(dirname "$0")/.." || exit 1
mkdir -p results
exec 8>"/tmp/ogc_$(basename "$0").lock"
flock -n 8 || { echo "another $(basename "$0") is already running"; exit 0; }
exec 9>/tmp/ogc_experiment.lock
flock 9 || exit 1

OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 OGC_CUT=1 \
    python3.12 harness/mkbase.py 0.3 myalg_cut.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
OGC_DK=0 OGC_FASTOBJ=1 OGC_BRK=1 \
    python3.12 harness/mkbase.py 0.3 myalg_brk.py 0 "" 0 1.0 "" 0 "" >/dev/null || exit 1
python3.12 -c "
import inspect, myalg_cut as A, myalg_brk as C
a, c = inspect.getsource(A), inspect.getsource(C)
assert a.count('badsets.append') == 2, a.count('badsets.append')
assert 'def _assign_once(prob_info, ent, ext, bay, capf, tl, cuts=())' in a
assert 'mdl.Add(sum(x[q][_ck] for q in _cs) <= len(_cs) - 1)' in a
assert 's, spill, hot, _bad = _realise(' in a and 'min(left * 0.4, 8.0), _cuts)' in a
assert 'badsets' not in c, 'control must not carry the cuts'
assert a.count('_realise(') == 2 and c.count('_realise(') == 2, 'all call sites must match arity'
print('cut arm and control verified')" || exit 1

run () {  # module tag outfile
    [ -s "results/\$3" ] && return
    echo "=== \$3  (\$2)  \$(date -u +%H:%M:%S)"
    python3.12 harness/run1.py "\$1" 3 240 "\$2" > "results/\$3" 2>&1
    tail -1 "results/\$3"
    ( cd ../../.. && git add -f "research/exact_packer/session2/recon/results/\$3" >/dev/null 2>&1 \
      && git commit -q -m "result: \$2" >/dev/null 2>&1 )
}

for rep in 1 2 3; do
    run myalg_cut "cranecut r$rep" "q27_cut_r${rep}.log"
    run myalg_brk "areacut r$rep"  "q27_area_r${rep}.log"
done
echo "queue27done  $(date -u +%H:%M:%S)"
