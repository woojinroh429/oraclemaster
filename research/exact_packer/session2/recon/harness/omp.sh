#!/bin/bash
# DOES -fopenmp PAY, AND CAN IT BE SHIPPED WITHOUT RISKING THE 400% CPU LIMIT?
#
# HOW THIS CAME UP.  A rebuild of the LNSEQ patch accidentally used harness/buildabi.sh's compiler
# line, which carries -fopenmp; build_submission.sh does not.  ogc_fast.cpp has 2 `#pragma omp
# parallel for` regions and no _OPENMP guards, and -w hides the fact that the pragmas are being
# ignored, so the flag silently decides whether the beam's expansion loop is threaded.  Every
# artifact ever shipped was SERIAL.  On the two cells that ran before the mistake was caught, the
# threaded build read 9,543,933 and 9,988,749 on P20 against the serial build's 10,686,538 and
# 10,284,359 -- mean -6.8%, non-overlapping.  Two cells per side is not a result; this is the
# measurement.
#
# WHAT IS ACTUALLY PARALLELISED, because that sets the risk.  ogc_fast.cpp:2080 and :3008 open a
# parallel region around the beam's per-state expansion, with `#pragma omp for schedule(dynamic)`
# over the beam.  That is the hot loop -- the same thing `accel` bought 2.1% by making cheaper.  So
# the mechanism for a gain is real and is not in dispute.  What is in dispute is the price.
#
# THE PRICE.  myalgorithm.py runs a POOL of worker processes: nw = max(1, cpu_count-1) = 3 on this
# 4-core box.  OpenMP defaults to one thread per core PER PROCESS, so the unpinned threaded build
# asks for 3 x 4 = 12 threads.  The grader caps CPU at 400%.  Exceeding it is a
# disqualification-class failure, not a score loss, which is a different kind of risk from
# everything else measured this session.
#
# THE LIMITATION THAT NO EXPERIMENT ON THIS BOX CAN REMOVE, stated first because it decides how the
# result may be used: this machine has 4 cores, so it CANNOT exhibit more than ~400% no matter what
# the code asks for.  A clean peak reading here is therefore NOT evidence that the grader's box
# stays under the limit -- if the grader has more cores, OpenMP's default thread count rises with
# them.  The only configuration whose CPU is bounded independently of the grader's hardware is one
# with OMP_NUM_THREADS pinned, and that is why arms C and D exist and why arm B, whatever it
# scores, is not shippable as-is.
#
# ARMS.  All run the same source; only the .so and the thread/worker split differ.
#     A  omp_off, shipped                          3 workers x serial          = 3   SHIPPABLE
#     B  omp_on,  OMP_NUM_THREADS unset            3 workers x 4 threads = 12  UNSAFE, diagnostic
#     C  omp_on,  OMP_NUM_THREADS=2, WORKERS=2     2 workers x 2 threads = 4   SHIPPABLE
#     D  omp_on,  OMP_NUM_THREADS=4, WORKERS=1     1 worker  x 4 threads = 4   SHIPPABLE
#
# C and D matter beyond safety: they test whether the gain is THREADING or merely
# OVERSUBSCRIPTION.  The pool's answer is a MINIMUM over draws, so cutting workers from 3 to 2 or 1
# removes draws -- the measured price list says that costs real objective (prob_1 k=6 -> k=3 is
# worth about 6%).  C and D therefore have to win the threading back before they break even, and
# if B wins while C and D lose, the honest reading is that the gain came from using more CPU than
# we are allowed rather than from parallelism.
#
# WHAT WOULD MAKE THIS MISLEAD, named first.  Per-instance noise is 11-23% on the volatile
# instances, and the -6.8% that motivated this sits well inside that.  The most likely outcome is
# that it does not replicate.  Instances are chosen for readability rather than interest: P3's A
# arm returned an identical value in all three lnseq replicates and P5 was byte-identical in all
# six lnseq/holdout cells, so those two are where a real 5% effect cannot hide; P20 is carried
# because it is where the anomaly appeared; P16 and P1 for breadth on the volatile end.
#
# JUDGED, fixed before the run.  Three replicates, paired within replicate, ratio per cell.
#   * PEAK CPU IS A VETO, not a tiebreak.  Any arm whose peak exceeds 380% on this box is rejected
#     outright regardless of objective, and a clean peak is reported as "not disqualifying HERE",
#     never as "safe on the grader".
#   * The objective claim is decided on P3 and P5 -- the two instances where the baseline is
#     reproducible -- with the population mean reported alongside.
#   * ADOPT only if a SHIPPABLE arm (C or D) beats A on the population mean AND does not lose on
#     P3 or P5.  A win confined to arm B closes the branch instead of opening it.
set -u
cd /home/user/oraclemaster/research/exact_packer/session2/recon || exit 1
. harness/lock.sh
lock_acquire omp
S=/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad
D="$PWD/data/stage2"
L=results/audit/omp.log
mkdir -p results/audit; touch $L
ci(){ ( cd "$(git rev-parse --show-toplevel)" \
        && git add research/exact_packer/session2/recon/results/audit/omp.log \
                  research/exact_packer/session2/recon/harness/CURRENT \
                  research/exact_packer/session2/recon/harness/omp.sh \
                  research/exact_packer/session2/recon/harness/cpuwatch.sh \
        && git commit -q -m "in-flight: omp $1" \
        && git push -q origin claude/repair-plan-model-1ig6it ) >/dev/null 2>&1; }
run(){ local tag="$1" tree="$2" p="$3" ev="$4" _s _e
    grep -vE '^# ' $L 2>/dev/null | grep -q "\[$tag\]" && return
    echo "# [$tag] tree=$tree env=$ev" >> $L
    _s=$(date +%s.%N)
    bash harness/cpuwatch.sh "$tag" "$PWD/$L" -- \
        env $ev timeout 200 bash -c "cd '$S/$tree' && exec /usr/bin/python3.12 run1.py myalgorithm $p 60 '[$tag]' --data '$D'" >> $L 2>&1 \
        || echo "P$p [$tag] CRASH rc=$?" >> $L
    _e=$(date +%s.%N)
    echo "# WALL [$tag] $(awk -v a="$_s" -v b="$_e" 'BEGIN{printf "%.2f", b-a}')" >> $L
    ci "$tag"; }
for rep in 1 2 3; do
  for p in 3 5 20 16 1; do
    run "A.p$p.r$rep" omp_off $p "OMP_NUM_THREADS=1"
    run "B.p$p.r$rep" omp_on  $p "OGC_DUMMY=0"
    run "C.p$p.r$rep" omp_on  $p "OMP_NUM_THREADS=2 WORKERS=2"
    run "D.p$p.r$rep" omp_on  $p "OMP_NUM_THREADS=4 WORKERS=1"
  done
done
echo "OMPDONE" >> $L
lock_release omp
