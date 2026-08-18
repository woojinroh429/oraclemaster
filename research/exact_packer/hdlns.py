"""High-density metaheuristic: per-bay cranepack re-scheduling (LNS repair).
Start from v77's solution; per bay, re-admit blocks event-by-event using cranepack's
weighted-MIS (urgency = 1/slack) to maximise the ON-TIME concurrent set at each event
-> earlier entries -> less tardiness.  Keep ONLY if the full (utils-checked) objective
improves.  Tests on several high-density instances.
Usage: python3.12 hdlns.py prob_38 [step=4] [tlp=0.4]
"""
import json, os, sys, time
import numpy as np
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from collections import defaultdict
NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 4
TLP=float(sys.argv[3]) if len(sys.argv)>3 else 0.4
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
best=None
for _ in range(2):
    sol=M.algorithm(inst,30); ck=check_feasibility(inst,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": b=op["block_id"]; pl[b]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[b])
        best=(ck["objective"],ck["obj1"],pl)
objv,z1v,place=best
print(f"{NAME}: v77 obj={objv:.0f} Z1={z1v:.0f}  (cranepack re-sched step={STEP})",flush=True)
_olc={}; _wlc={}
def OL(b,o):
    if (b,o) not in _olc: _olc[(b,o)]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[(b,o)]
def WL(b,o,x,y):
    k=(b,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)

def resched_bay(bay, blocks, wallcap):
    """Event-driven: at each event admit the max WEIGHTED (urgency) crane-fit set via
    cranepack, placed at the current time.  Returns {b:(o,x,y,en,ex)} or None."""
    W=bays[bay]["width"]; H=bays[bay]["height"]
    waiting=set(blocks); present={}; result={}
    t=min(rel[b] for b in blocks); guard=0; tw=time.time()
    while waiting and guard<6000:
        if time.time()-tw>wallcap: return None
        guard+=1
        for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1]); t=nxt; continue
        # urgency weight: earlier due / tighter slack -> higher weight
        avail=sorted(avail,key=lambda b:(due[b],rel[b]))[:24]
        froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
        binL=[]; wts=[]
        for b in avail:
            binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                         [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                         [(int(t),int(t+pt[b]))]))
            slack=max(1,due[b]-t-pt[b]); wts.append(1000.0/slack)   # urgency weight
        res=CP.pack(binL,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz,weights=wts)
        adm=0
        for (loc,o,x,y,en,ex) in res[1]:
            b=avail[loc]; present[b]=(o,x,y,t,t+pt[b]); result[b]=(o,x,y,t,t+pt[b]); waiting.discard(b); adm+=1
        if adm==0:
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands: return None
            t=min(cands)
    if waiting: return None
    return result

t0=time.time()
newplace=dict(place); improved_bays=0
for bay in range(m):
    bl=bybay[bay]
    if not bl: continue
    r=resched_bay(bay, bl, wallcap=25.0)
    if r is None:
        continue
    # tentatively apply to this bay, grade full
    trial=dict(newplace)
    for b,v in r.items(): trial[b]=dict(bay=bay,oi=v[0],x=v[1],y=v[2],en=v[3],ex=v[4])
    al=[{"block_id":b,"bay_id":trial[b]["bay"],"orient_idx":trial[b]["oi"],"x":trial[b]["x"],"y":trial[b]["y"],"entry_time":trial[b]["en"],"exit_time":trial[b]["ex"]} for b in range(n)]
    ck=check_feasibility(inst,M._build_operations(al))
    if ck["feasible"] and ck["objective"]<=objv:
        newplace=trial; objv=ck["objective"]; improved_bays+=1
al=[{"block_id":b,"bay_id":newplace[b]["bay"],"orient_idx":newplace[b]["oi"],"x":newplace[b]["x"],"y":newplace[b]["y"],"entry_time":newplace[b]["en"],"exit_time":newplace[b]["ex"]} for b in range(n)]
ck=check_feasibility(inst,M._build_operations(al))
d=best[0]-ck["objective"] if ck["feasible"] else -1
print(f"  after re-sched ({improved_bays} bays improved): obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}  "
      f"{'WIN -'+str(round(100*d/best[0],1))+'%' if ck['feasible'] and d>0 else 'no gain'}  [{time.time()-t0:.0f}s]",flush=True)
