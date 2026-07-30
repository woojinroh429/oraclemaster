#!/bin/bash
# Put the working tree back after a container reset.
#
# The container has reset twice in half an hour.  Each time the tree comes back at whatever
# commit the image was built from, `data/` is a dead symlink into /tmp, the compiled engine is
# the stale one from the image, and every generated arm is gone -- while the git history and
# the mirrored logs are safe on the remote.  So recovery is always the same four steps, and
# doing them by hand costs ten minutes of a night that has already lost two queues.
#
#   git fetch origin <branch> && git reset --hard origin/<branch>
#   research/exact_packer/session2/recon/harness/restore.sh
#
# Idempotent: safe to run when nothing is missing.
set -e
cd "$(dirname "$0")/.."

# 1. the hidden instances.  data/ is a symlink into /tmp, which does not survive.
if [ ! -f data/hidden/prob_6.json ]; then
  rm -rf data
  mkdir -p data/hidden
  cp _hidden_backup/prob_*.json data/hidden/
  echo "restored 6 hidden instances from _hidden_backup"
fi

# 2. the engine.  The image ships a stale .so; anything measured against it is measuring the
#    wrong code.  Build to a temp path and mv -- copying over a live .so SIGBUSes any running
#    worker, which killed a P6 curve measurement earlier in this session.
EXT="cpython-312-x86_64-linux-gnu.so"
if ! python3.12 -c "
import importlib.util, sys
s = importlib.util.find_spec('ogc_fast')
sys.exit(0 if s else 1)" 2>/dev/null || [ ogc_fast.cpp -nt "ogc_fast.$EXT" ]; then
  g++ -O3 -shared -std=c++17 -fPIC -w $(python3.12 -m pybind11 --includes) \
      ogc_fast.cpp -o "/tmp/ogc_fast_build.$EXT"
  mv "/tmp/ogc_fast_build.$EXT" "ogc_fast.$EXT"
  echo "rebuilt ogc_fast"
fi

# 3. the arms.  All generated from c80551b by mkbase.py, so none of them is worth tracking --
#    but every one of them has to exist before a queue can run.
python3.12 harness/mkbase.py 0.3 myalg_base.py            >/dev/null
python3.12 harness/mkbase.py 0.5 myalg_c5.py              >/dev/null
python3.12 harness/mkbase.py 0.3 myalg_sh1.py  1.0        >/dev/null
python3.12 harness/mkbase.py 0.3 myalg_co.py   0.0 cohort >/dev/null
python3.12 harness/mkbase.py 0.3 myalg_sp.py   0.0 "" 2.0 >/dev/null
echo "rebuilt arms: orig base c5 sh1 co sp"

# 4. the log mirror.  Without it a reset takes the night's results with it.
if ! pgrep -f '^/bin/bash harness/keep.sh' >/dev/null; then
  setsid nohup harness/keep.sh >/dev/null 2>&1 </dev/null &
  echo "restarted the log mirror"
fi
echo "restore complete"
