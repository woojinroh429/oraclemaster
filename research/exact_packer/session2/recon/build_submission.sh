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
cp "$HERE/myalgorithm.py" "$HERE/utils.py" "$OUT/"

echo "== packaging =="
( cd "$OUT" && zip -j -q submit_recon.zip myalgorithm.py utils.py *.$EXT )
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
