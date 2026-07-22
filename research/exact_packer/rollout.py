"""ROLLOUT (pilot-method) crane scheduler: adds 1-step look-ahead to the greedy
event-driven admission.  At each event, for each CANDIDATE admission set (full
urgency-greedy vs the set minus its least-urgent block = 'leave room for future'),
GREEDILY roll the schedule out to completion and score total tardiness; commit the
candidate with the lowest rolled-out tardiness.  Tests whether look-ahead cuts the
greedy per-bay Z1 our engine floors at.  Compares to v77 on prob_30 bays.
Usage: python3.12 rollout.py prob_30 [bays=0] [step=6] [cap=150]
"""
import json, os, sys, time
import numpy as np
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_30"
TGT=[int(x) for x in sys.argv[2].split(",")] if len(sys.argv)>2 else None
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 6
CAP=float(sys.argv[4]) if len(sys.argv)>4 else 150.0
TLP=0.35
def find(nm):
    for s in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,s,nm+".json")
        if os.path.exists(p): return p
d=json.load(open(find(NAME))); B=d["blocks"]; n=len(B); bays=d["bays"]; m=len(bays)
rel=[B[b]["release_time"] for b in range(n)]; pt=[B[b]["processing_time"] for b in range(n)]; due=[B[b]["due_date"] for b in range(n)]
_olc={}; _wlc={}
def OL(b,o):
    if (b,o) not in _olc: _olc[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[(b,o)]
def WL(b,o,x,y):
    k=(b,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

def cpack(bay, avail, present, t, weights):
    W=bays[bay]["width"]; H=bays[bay]["height"]
    froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
    binL=[([OL(b,o) for o in range(len(B[b]["shape"]))],
           [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
           [(int(t),int(t+pt[b]))]) for b in avail]
    res=CP.pack(binL,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz,weights=[float(w) for w in weights])
    return {avail[loc]:(o,x,y,t,t+pt[b_i]) for (loc,o,x,y,en,ex),b_i in [(r,avail[r[0]]) for r in res[1]]}

KROLL=10   # k-step rollout depth (then estimate the tail with a valid waiting LB)
def waitLB(waiting, t):
    return sum(max(0, max(t,rel[b])+pt[b]-due[b]) for b in waiting)

def greedy_finish(bay, present, waiting, t, tard, guard_cap):
    """k-step greedy rollout: admit up to KROLL blocks, then estimate the remaining tail
    with a valid waiting-tardiness lower bound.  Returns an ESTIMATE of total tardiness
    (cheap enough to call as a pilot look-ahead at every event)."""
    present=dict(present); waiting=set(waiting); guard=0; steps=0
    while waiting and guard<guard_cap:
        if steps>=KROLL: return tard + waitLB(waiting, t)
        guard+=1
        for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1]); t=nxt; continue
        av=sorted(avail,key=lambda b:(due[b],rel[b]))[:20]
        wts=[1000.0/max(1,due[b]-t-pt[b]) for b in av]
        got=cpack(bay, av, present, t, wts)
        if not got:
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands: return None
            t=min(cands); continue
        for b,v in got.items(): present[b]=v; waiting.discard(b); tard+=max(0,v[4]-due[b])
        steps+=1
        nc=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
        t=min(nc) if nc else t+1
    return tard if not waiting else None

def rollout_bay(bay, blocks, cap):
    present={}; waiting=set(blocks); result={}; tard=0
    t=min(rel[b] for b in blocks); tw=time.time(); guard=0
    while waiting and guard<8000:
        if time.time()-tw>cap: return None,None
        guard+=1
        for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1]); t=nxt; continue
        av=sorted(avail,key=lambda b:(due[b],rel[b]))[:20]
        wts=[1000.0/max(1,due[b]-t-pt[b]) for b in av]
        full=cpack(bay, av, present, t, wts)
        if not full:
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands: return None,None
            t=min(cands); continue
        # candidate admission sets: A=full greedy, B=full minus least-urgent admitted
        adm_full=list(full.keys())
        cands=[full]
        if len(adm_full)>=2:
            least=max(adm_full, key=lambda b:(due[b]-t))  # least urgent (largest slack)
            subset=[b for b in av if b!=least]
            sub=cpack(bay, subset, present, t, [1000.0/max(1,due[b]-t-pt[b]) for b in subset])
            if sub and frozenset(sub.keys())!=frozenset(full.keys()): cands.append(sub)
        # rollout each candidate -> pick min total tardiness
        best=None; bestc=None
        for got in cands:
            np_=dict(present); wt_=set(waiting); td_=tard
            for b,v in got.items(): np_[b]=v; wt_.discard(b); td_+=max(0,v[4]-due[b])
            nxt_cands=[v[4] for v in np_.values() if v[4]>t]+[rel[b] for b in wt_ if rel[b]>t]
            nt=min(nxt_cands) if nxt_cands else t+1
            roll=greedy_finish(bay, np_, wt_, nt, td_, 6000)
            if roll is not None and (best is None or roll<best): best=roll; bestc=got
        if bestc is None: bestc=full
        for b,v in bestc.items(): present[b]=v; result[b]=v; waiting.discard(b); tard+=max(0,v[4]-due[b])
        cands2=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
        t=min(cands2) if cands2 else t+1
    if waiting: return None,None
    return result, tard

best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": pl[op["block_id"]]=dict(bay=op["bay_id"],ex=int(tk)+pt[op["block_id"]])
        best=(ck["objective"],ck["obj1"],pl)
objv,z1v,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
print(f"{NAME}: v77 Z1={z1v:.0f}  (ROLLOUT step={STEP})",flush=True)
tgt=TGT if TGT is not None else list(range(m))
for j in tgt:
    bl=bybay[j]
    if not bl: continue
    v77z1=sum(max(0,place[b]["ex"]-due[b]) for b in bl)
    t0=time.time(); r,td=rollout_bay(j, bl, CAP)
    if r is None:
        print(f"  bay{j}: {len(bl)}blk ROLLOUT failed/timeout  v77={v77z1} [{time.time()-t0:.0f}s]",flush=True); continue
    win="WIN -"+str(round(100*(v77z1-td)/max(1,v77z1)))+"%" if td<v77z1 else ("+"+str(int(td-v77z1)))
    print(f"  bay{j}: {len(bl)}blk  ROLLOUT bay-Z1={td:.0f}  v77={v77z1}  {win}  [{time.time()-t0:.0f}s]",flush=True)
