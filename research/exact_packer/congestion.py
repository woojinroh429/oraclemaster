"""Congestion profile + peak-clique extractor for low-density (P3-class) bays.

For each bay j (under the pipeline's assignment):
  1. build the co-present AREA profile A_j(tau) over event times (interval graph),
  2. enumerate MAXIMAL cliques (sets of mutually time-overlapping blocks) via an
     event sweep,
  3. report the binding cliques: size, peak area %, count.
This fixes the Gurobi packing model's SCALE (how many blocks per exact subproblem).
"""
import json, os, sys
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); os.chdir(os.path.join(SP,"v71"))
import myalgorithm as M, utils

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

def amin(B,b):
    best=None
    for oi in range(len(B[b]["shape"])):
        bb=M._orient_bbox(B[b],oi); a=(bb[2]-bb[0])*(bb[3]-bb[1])
        if best is None or a<best: best=a
    return best

def maximal_cliques(intervals):
    """intervals: list of (entry, exit, block_id). Return list of maximal cliques
    (each a set of block_ids all mutually overlapping) via event sweep. For interval
    graphs, a maximal clique forms just before each 'exit' when the current set can't
    grow. We emit the current set at each entry that is followed (eventually) by an exit."""
    evs=[]
    for (en,ex,b) in intervals:
        evs.append((en, 0, b))   # enter
        evs.append((ex, 1, b))   # exit (process exits after enters at same time? use half-open)
    # half-open [en,ex): at time t, present = entered<=t and exit>t. Process exits BEFORE
    # enters at equal t so a block exiting at t and one entering at t are NOT co-present.
    evs.sort(key=lambda e:(e[0], -e[1]))  # exits (1) before enters(0)? -e[1]: enter(0)->0, exit(1)->-1 => exit first
    cur=set(); cliques=[]; last_was_enter=False
    for (t,typ,b) in evs:
        if typ==0:
            cur.add(b); last_was_enter=True
        else:
            if last_was_enter and cur:
                cliques.append(set(cur))   # maximal: about to shrink
            cur.discard(b); last_was_enter=False
    # dedup (subset removal)
    cliques=[c for c in cliques if c]
    uniq=[]
    for c in sorted(cliques, key=len, reverse=True):
        if not any(c<=u for u in uniq): uniq.append(c)
    return uniq

for name in ["prob_20","prob_13","prob_17"]:
    d=json.load(open(find(name))); B=d["blocks"]; bays=d["bays"]; n=len(B); m=len(bays)
    os.system("rm -f /dev/shm/psm_* /dev/shm/sem.* 2>/dev/null")
    sol=M.algorithm(d,30)
    ops=sol["operations"]; pt=[b["processing_time"] for b in B]
    assign={}
    for tk,lst in ops.items():
        for op in lst:
            if op.get("type")=="ENTRY": assign[op["block_id"]]=(op["bay_id"], int(tk))
    area=[amin(B,b) for b in range(n)]
    cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    obj=int(utils.check_feasibility(d,sol)["objective"])
    print(f"=== {name} obj={obj} ===", flush=True)
    for j in range(m):
        iv=[(assign[b][1], assign[b][1]+pt[b], b) for b in assign if assign[b][0]==j]
        if not iv: continue
        cliques=maximal_cliques(iv)
        # area of each clique, sort by area
        info=[]
        for c in cliques:
            ar=sum(area[b] for b in c); info.append((ar/cap[j], len(c), ar))
        info.sort(reverse=True)
        top=info[:3]
        nblk=len(iv)
        binding=sum(1 for f,_,_ in info if f>=0.65)
        print(f"  bay{j}: {nblk:3d} blk, {len(cliques):3d} max-cliques, "
              f"peak_clique(area%,size)={[(round(100*f),s) for f,s,_ in top]}  "
              f"cliques>=65%cap: {binding}", flush=True)
