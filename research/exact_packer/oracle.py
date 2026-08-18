"""Phase 2 building block: crane-feasibility ORACLE.

Given an assignment ext[b] -> bay, decide whether it is crane-feasible (an on-time
Z1=0 packing exists) and, if not, return an infeasible CORE: (bay j, set S of
blocks) such that S cannot all co-reside in bay j on time.  The core drives the
LBBD combinatorial cut  sum_{b in S} x[b,j] <= |S|-1.

Uses the shipped decoder (_smallright_construct with forced ext_bay) as the
feasibility check, then localises the failure to the peak-congestion time-window
of the offending bay.
"""
import os, sys, time, json, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71"))
import myalgorithm as M
from utils import check_feasibility

def crane_oracle(d, ext, deadline_s=6.0):
    """Return (feasible:bool, core:(bay,set_of_block_ids) or None, obj1, realized_ops).
    feasible == (a forced-bay on-time packing was found with Z1==0)."""
    n=len(d["blocks"])
    recs=M._smallright_construct(d, time.time()+deadline_s, step=1, mode="prefaware", ext_bay=ext)
    if not recs or len(recs)!=n:
        # decoder could not even place all blocks in forced bays -> use the most
        # over-subscribed bay's peak window as the core
        return False, _peak_core(d, ext), None, None
    sol=M._build_operations([recs[b] for b in range(n)])
    r=check_feasibility(d, sol)
    if r.get("feasible") and r.get("obj1",1)==0:
        return True, None, 0.0, sol
    # infeasible (tardy): find tardy blocks and localise
    B=d["blocks"]
    tardy=[]
    for b in range(n):
        a=recs[b]
        if a is None: tardy.append(b); continue
        ex=a.get("exit_time", a["entry_time"]+B[b]["processing_time"])
        if ex > B[b]["due_date"]+1e-9: tardy.append(b)
    core=_tardy_core(d, ext, tardy)
    return False, core, (r.get("obj1") if r.get("feasible") else None), None

def _peak_core(d, ext):
    """Most over-subscribed (bay, peak-window blocks) by area."""
    B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
    def amin(b):
        best=None
        for oi in range(len(B[b]["shape"])):
            bb=M._orient_bbox(B[b],oi); a=(bb[2]-bb[0])*(bb[3]-bb[1])
            if best is None or a<best: best=a
        return best
    area=[amin(b) for b in range(n)]
    cap=[bays[j]["width"]*bays[j]["height"] for j in range(m)]
    rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
    best=None
    for j in range(m):
        for t in sorted(set(rel)):
            present=[b for b in range(n) if ext[b]==j and rel[b]<=t<rel[b]+pt[b]]
            s=sum(area[b] for b in present)
            ratio=s/cap[j]
            if present and (best is None or ratio>best[0]):
                best=(ratio, j, set(present))
    if best is None: return None
    return (best[1], best[2])

def _tardy_core(d, ext, tardy):
    """Core = tardy blocks plus their time-overlapping same-bay neighbours."""
    if not tardy: return _peak_core(d, ext)
    B=d["blocks"]; n=len(B)
    rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]
    # group tardy by bay, pick the bay with most tardy
    from collections import Counter
    cnt=Counter(ext[b] for b in tardy)
    j=cnt.most_common(1)[0][0]
    tj=[b for b in tardy if ext[b]==j]
    lo=min(rel[b] for b in tj); hi=max(rel[b]+pt[b] for b in tj)
    S=set(b for b in range(n) if ext[b]==j and rel[b]<hi and rel[b]+pt[b]>lo)
    return (j, S)

if __name__=="__main__":
    # smoke test: run the AREA-optimal assignment through the oracle
    sys.path.insert(0, os.path.join(SP,"research"))
    from gmaster import build_master, find
    for nm in ["prob_20","prob_13"]:
        d=json.load(open(find(nm)))
        mdl,x,meta=build_master(d, tl=10.0); mdl.optimize()
        n,m=meta[0],meta[1]
        ext=[next(j for j in range(m) if x[b,j].X>0.5) for b in range(n)]
        feas,core,o1,_=crane_oracle(d, ext)
        cs=("bay %d, |S|=%d"%(core[0],len(core[1]))) if core else "none"
        print(f"{nm}: area-opt feasible={feas} obj1={o1} core=({cs})", flush=True)
