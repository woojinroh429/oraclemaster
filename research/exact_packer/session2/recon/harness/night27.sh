#!/bin/bash
# Four GRASP2 runs all landed 28.06-28.14M against plain GRASP k=6's 27,786,975, so memory and
# adaptation are costing rather than paying here.  Two reasons visible in the logs: the reactive
# weights stay near 1.0 (3:1.11 4:0.76 6:0.69 8:0.78) because incumbents are rare -- one to three
# per run is no signal to learn a k from in 42 draws -- and every elite is a near-greedy order,
# so biasing toward where they agree reinforces the greedy instead of finding what departs from
# it.  Seed 777 drew 42 times and never beat draw 1.
#
# But the comparison is not fair yet: plain GRASP k=6 has exactly ONE sample.  27,786,975 could
# be a lucky draw.  Three more seeds, same settings, before anything is concluded -- and one
# long run to see whether the plain version keeps improving when the budget doubles, which is
# the property that made it interesting.
cd "$(dirname "$0")/.."
busy() { pgrep -f '^python3\.12 harness/(run1|beam2|mech|dissect|bigleft|polish|grasp|grasp2)\.py' >/dev/null; }
while busy; do sleep 20; done
for s in 4242 31337 99; do
  python3.12 harness/grasp.py 6 600 300 6 flatbl $s >> _n/g4.log 2>&1
done
echo G4-DONE >> _n/g4.log
python3.12 harness/grasp.py 6 1500 300 6 flatbl 777 >> _n/g4.log 2>&1
echo G4B-DONE >> _n/g4.log
