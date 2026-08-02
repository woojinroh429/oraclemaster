#!/bin/bash
# Reproducible submission build: compiles all 5 C++ engine modules from source and
# assembles the submission zip (Python + .so).  Robust to fresh containers: everything
# is built from the committed sources in this directory.
#   usage:  bash build_submission.sh [output_dir]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/submit_build}"
rm -rf "$OUT"; mkdir -p "$OUT"

INC="$(python3.12 -m pybind11 --includes)"
EXT="cpython-312-x86_64-linux-gnu.so"
CXXFLAGS="-O3 -shared -std=c++17 -fPIC -w"

echo "== compiling 5 engine modules =="
for m in ogc_fast ogc_geom ogc_state cranepack st3dtcs; do
  echo "  - $m"
  g++ $CXXFLAGS $INC "$HERE/$m.cpp" -o "$OUT/$m.$EXT"
done

echo "== copying python =="
# SHIP brk.  The exact bay-repack is a separate module by design -- it is a self-contained
# operator with its own cost model, and folding 797 lines of it into the pipeline file would
# make both harder to read for no benefit.  myalgorithm.py imports it; if the import fails the
# roster entry is simply absent and the pipeline runs exactly as it did without it.
#
# WHAT IS ACTUALLY ESTABLISHED, at the real budgets:
#
#                 brk on        brk off
#     P1          11,280        11,280        same
#     P2          31,368        31,368        same
#     P3          80,795        96,990        brk by 16,195
#     P4       1,781,181     1,780,253        brk worse by 928 (0.05%) -- a tie
#     P5       9,044,458     not measured
#     P6      29,651,637    30,297,335*       brk better
#
#     * that figure came from myalg_orig, not from the lean build, which has never been
#       measured on P5 or P6 at all.  So the honest claim is: brk wins P3 decisively, ties
#       P1/P2/P4, and P5/P6 lack a matched control.  It is not "verified better everywhere",
#       and the control runs are queued.
#
# The 797 lines buy 16.7% on P3 and cost nothing measurable anywhere else.
# myalgorithm.py IS the algorithm now -- 1,466 lines, generated once from mkbase and committed,
# not regenerated here.  The previous 6,675-line file is myalg_legacy.py and is kept only because
# the GRASP harnesses read its construction; nothing ships from it.
cp "$HERE/myalgorithm.py" "$OUT/myalgorithm.py"
cp "$HERE/bayrepack.py" "$OUT/"
cp "$HERE/utils.py" "$OUT/"

echo "== packaging =="
( cd "$OUT" && zip -j -q submit_recon.zip myalgorithm.py bayrepack.py utils.py *.$EXT )
echo "== done: $OUT/submit_recon.zip =="
( cd "$OUT" && unzip -l submit_recon.zip )

echo ""
echo "== smoke test (import + one solve) =="
python3.12 - "$OUT" <<'PY'
import sys,os,json,glob
OUT=sys.argv[1]; sys.path.insert(0,OUT); os.environ["ENGINE_DIR"]=OUT
import myalgorithm as M
from utils import check_feasibility
# find any training instance
cand=None
for base in ("data/train","data/training_instances/train"):
    for root in ("/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad",):
        p=os.path.join(root,base,"prob_30.json")
        if os.path.exists(p): cand=p; break
if cand:
    d=json.load(open(cand)); sol=M.algorithm(d,15); ck=check_feasibility(d,sol)
    print("SMOKE prob_30: obj=%.0f Z1=%.0f feas=%s HAVE_OGC_FAST=%s"%(
        ck["objective"],ck["obj1"],ck["feasible"],getattr(M,"HAVE_OGC_FAST","?")))
else:
    print("SMOKE: import OK (no local instance to solve)")
PY
