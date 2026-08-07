#!/bin/bash
# WIDEN THE w3mul GRID THE OPENING AXES ACTUALLY USE.
#
# w3mul is the beam's bias toward preferred bays, applied on top of the instance's true w3 to
# correct the greedy lookahead's undervaluation of preference: a non-preferred bay is a permanent
# loss, while tardiness can sometimes be recovered later.  The shipped values are
#
#     axis     0     1     2     3     4     5
#     w3mul   1.0   3.0   3.0   1.0   6.0   1.5
#
# and _AXES has not changed since 08-02 10:18 -- before 08-03 02:21, when the final set was
# identified as a different problem.
#
# TWO REASONS THAT GRID IS AIMED SOMEWHERE ELSE (results/audit/w3mul_grid.md).
#
# The exchange rate w1/w3 -- units of preference per unit of tardiness -- has median 84.5 on the
# preliminary set and 23.3 on the final one.  Twenty of the forty final instances are below 20x,
# where the preliminary lower quartile was 44x.  Preference carries roughly 3.6x more value than
# the set the grid was tuned on.
#
# And with nw = 4 the live wids are 0..3, so only axes 0..3 ever open a run: the opening grid is
# 1.0, 3.0, 3.0, 1.0 -- TWO distinct values.  The widest entry, 6.0, sits on axis 4 and never opens.
#
# ARMS.  Positional replacement, everything else untouched.
#     base     1.0,3.0,3.0,1.0,6.0,1.5     shipped
#     spread   1.0,3.0,6.0,12.0,6.0,1.5    keep the low end, widen the OPENING four upward
#     up       3.0,6.0,12.0,24.0,6.0,1.5   shift the opening four up entirely
#     dn       0.5,1.0,2.0,4.0,6.0,1.5     shift DOWN -- the control
#
# The dn arm is not filler.  Without it a win for spread or up is equally explained by "any change
# to the grid helps", which is the reading this session has had to retract more than once.  If dn
# wins too, the direction argued from the weight distributions is wrong and the effect is
# perturbation, not preference.
#
# Same twelve instances as ortho, drawn with a fixed seed and stratified by exchange-rate band and
# block count, because the prediction is band-dependent: the widening should pay most where
# preference is worth most (low w1/w3) and least where it is nearly a tiebreak (P2 at 88.9x).
# Reading it pooled would average those against each other, which is the mistake bytype.md
# documents.
#
# myalg_w3.py is myalgorithm.py plus the OGC_W3GRID knob, which is inert when unset -- the base arm
# is therefore the shipped code path, and the comparison is internal to one file.
set -u
cd "$(dirname "$0")/.." || exit 1
echo w3grid > harness/CURRENT
L=results/audit/w3grid.log
mkdir -p results/audit; touch $L

run(){ # rep arm prob grid
    local tag="r$1.$2.$3"
    # SKIP ON A RESULT, NOT ON THE MARKER.  The marker is written BEFORE the run, so a queue
    # killed mid-cell leaves an orphan "# [tag]" line with no result -- and this test then
    # matched it on resume and skipped the cell forever.  Nine such orphans existed across
    # today's logs, including one this session was actively waiting on (w3grid r1.dn.26).
    # In a paired design a lost arm silently invalidates the whole instance.  Excluding the
    # marker lines makes the test key on evidence the run finished.
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $4 OGC_WSTAT=1 timeout 960 /usr/bin/python3.12 harness/run1.py myalg_w3 $3 240 \
        "[$tag]" --data data/stage2 >> $L 2>&1 \
        || echo "P$3 [$tag] HANG-OR-CRASH rc=$?" >> $L
    ( cd "$(git rev-parse --show-toplevel)" \
      && git add research/exact_packer/session2/recon/results/audit/w3grid.log \
      && git commit -q -m "in-flight: w3grid $tag" ) >/dev/null 2>&1
}

ORDER="4 26 20 2 13 5 6 1 32 31 38 35"
for rep in 1 2; do
    for p in $ORDER; do
        run $rep base   $p ""
        run $rep spread $p "OGC_W3GRID=1.0,3.0,6.0,12.0,6.0,1.5"
        run $rep up     $p "OGC_W3GRID=3.0,6.0,12.0,24.0,6.0,1.5"
        run $rep dn     $p "OGC_W3GRID=0.5,1.0,2.0,4.0,6.0,1.5"
    done
    echo "REPDONE $rep" >> $L
done
echo "W3GRIDDONE" >> $L
echo idle > harness/CURRENT
