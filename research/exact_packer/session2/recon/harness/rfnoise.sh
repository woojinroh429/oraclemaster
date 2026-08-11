#!/bin/bash
# THE NOISE FLOOR PART A NEEDED AND DID NOT HAVE.
#
# rfship part A compares HEAD's module against the edited one on instances the gate does not fire
# on, expecting identical numbers.  P21 came back 1,014,768 against 1,087,112 -- a 7.1% gap on an
# instance where the two modules execute the same bytecode.
#
# THE STRUCTURAL ARGUMENT SAYS THAT GAP CANNOT BE THE EDIT.  The whole diff is one string literal
# inside `if _lo <= _pu <= _thr and float(timelimit) <= _tlim`.  P21's peak_util is 0.999994886689,
# below _lo=1.00, so the branch is not entered, nothing is injected into os.environ, and RESFRAC
# keeps its 0.35 default in both.  There is no path by which the literal is read.
#
# THE LIKELY CAUSE IS THE CLOCK.  wbudget = timelimit - reserve - elapsed - 1.0 and the rounds run
# until it is gone, so how many iterations happen depends on wall-clock speed.  P21 ran 42 s and
# 43 s of its 60 -- clock-bound, and free to differ.  P1's control returns 556,718 on all three
# gaterf replicates for the opposite reason: at reserve 0.50 it converges and stops at 30 s of 60,
# so the clock never binds and the run is reproducible by accident, not by design.
#
# THAT DISTINCTION MATTERS BEYOND THIS CHECK.  Every "byte-identical" claim made today rests on
# comparing single runs, and this says such a comparison is only meaningful where the run
# terminates early.  RESFRAC 0.05 makes runs clock-bound by construction -- 57 s of 60 -- so the
# ship is being judged on exactly the regime where single draws are least reliable.
#
# ARMS.  The same module, HEAD's, twice on each part-A instance.  Nothing else changes.
#
# WHAT IT DECIDES.  If prev-vs-prev spread covers the prev-vs-new gaps, part A is uninformative
# rather than failed and the structural argument stands on its own.  If prev-vs-prev is tight and
# prev-vs-new is not, then the edit reaches instances it must not and NOTHING ships -- that would
# mean the gate leaks, which is the one outcome that stops the submission outright.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
while [ "$(cat harness/CURRENT 2>/dev/null)" != "idle" ]; do sleep 15; done
echo rfnoise > harness/CURRENT
L=results/audit/rfnoise.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/rfnoise.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/rfnoise.sh \
        && git commit -q -m "in-flight: rfnoise $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" mod="$2" p="$3" envs="$4"
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag]" >> $L
    env $envs timeout 220 /usr/bin/python3.12 harness/run1.py $mod $p 60 \
        "[$tag]" --data data/stage2 >> $L 2>&1 || echo "P$p [$tag] CRASH rc=$?" >> $L
    ci "$tag"; }

# two more draws of the SAME module on each part-A instance, so each has three from prev and one
# from new and the question becomes whether new sits inside prev's own range.
for rep in 2 3; do
  for p in 21 4 2 9 34; do
    run "n.p$p.prev.r$rep" myalg_prev $p "WORKERS=4"
  done
done
echo "RFNOISEDONE" >> $L
echo idle > harness/CURRENT
