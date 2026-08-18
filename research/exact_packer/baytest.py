"""DIAGNOSE the per-bay oracle on prob_38's dense bays.
Extract v77's per-bay block sets + per-bay Z1, then run the event-driven
resched_bay with FULL instrumentation: seated/total, stall reason
(timeout / logical-stuck / guard), events, wall time, and the resulting
bay-Z1 if it seats all.  This tells us whether None is a timeout or a real
deadlock, and how far the current oracle is from v77 per bay.
Usage: python3.12 baytest.py prob_38 [step=4] [wallcap=120]
"""
import json, os, sys, time
import numpy as np
from collections import defaultdict
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v77")); os.environ["ENGINE_DIR"]=os.path.join(SP,"v77")
sys.path.insert(0, os.path.join(SP,"cc"))
import myalgorithm as M
from utils import check_feasibility
import cranepack as CP

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_38"
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 4
WCAP=float(sys.argv[3]) if len(sys.argv)>3 else 120.0
TLP=0.4
def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
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
def area(b): return M._orient_bbox.__self__ if False else (obb(b,0)[2]-obb(b,0)[0])*(obb(b,0)[3]-obb(b,0)[1])

def resched_verbose(bay, blocks, wallcap):
    W=bays[bay]["width"]; H=bays[bay]["height"]
    waiting=set(blocks); present={}; result={}
    t=min(rel[b] for b in blocks); guard=0; tw=time.time(); events=0; packcalls=0; packtime=0.0
    reason="ok"
    while waiting and guard<20000:
        if time.time()-tw>wallcap: reason=f"TIMEOUT@seated={len(result)}/{len(blocks)}"; break
        guard+=1; events+=1
        for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1]); t=nxt; continue
        avail=sorted(avail,key=lambda b:(due[b],rel[b]))[:24]
        froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
        binL=[]; wts=[]
        for b in avail:
            binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                         [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                         [(int(t),int(t+pt[b]))]))
            slack=max(1,due[b]-t-pt[b]); wts.append(1000.0/slack)
        _p0=time.time()
        res=CP.pack(binL,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz,weights=wts); packcalls+=1; packtime+=time.time()-_p0
        adm=0
        for (loc,o,x,y,en,ex) in res[1]:
            b=avail[loc]; present[b]=(o,x,y,t,t+pt[b]); result[b]=(o,x,y,t,t+pt[b]); waiting.discard(b); adm+=1
        if adm==0:
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands:
                reason=f"LOGICAL-STUCK@seated={len(result)}/{len(blocks)} present={len(present)}"; break
            t=min(cands)
    if guard>=20000 and waiting: reason=f"GUARD@seated={len(result)}/{len(blocks)}"
    z1=sum(max(0,v[4]-due[b]) for b,v in result.items()) if not waiting else None
    return result, reason, dict(events=events, packcalls=packcalls, packtime=packtime, wall=time.time()-tw, seated=len(result), total=len(blocks), z1=z1)

# v77 baseline + per-bay sets/Z1
best=None
for _ in range(2):
    sol=M.algorithm(d,30); ck=check_feasibility(d,sol)
    if ck["feasible"] and (best is None or ck["objective"]<best[0]):
        pl={}
        for tk,lst in sol["operations"].items():
            for op in lst:
                if op.get("type")=="ENTRY": pl[op["block_id"]]=dict(bay=op["bay_id"],en=int(tk),ex=int(tk)+pt[op["block_id"]])
        best=(ck["objective"],ck["obj1"],pl)
objv,z1v,place=best
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
print(f"{NAME}: v77 obj={objv:.0f} Z1={z1v:.0f}  (oracle step={STEP} wallcap={WCAP})",flush=True)
for j in range(m):
    bl=bybay[j]; v77z1=sum(max(0,place[b]["ex"]-due[b]) for b in bl)
    print(f"  bay{j}: {len(bl)} blocks  bay={bays[j]['width']}x{bays[j]['height']}  v77 bay-Z1={v77z1}",flush=True)

print("  --- running resched oracle per bay ---",flush=True)
for j in range(m):
    bl=bybay[j]
    if not bl: continue
    v77z1=sum(max(0,place[b]["ex"]-due[b]) for b in bl)
    res,reason,st=resched_verbose(j, bl, WCAP)
    z1s=f"oracle bay-Z1={st['z1']}" if st['z1'] is not None else "FAILED"
    win=""
    if st['z1'] is not None:
        win = f"  ({'WIN -'+str(round(100*(v77z1-st['z1'])/max(1,v77z1)))+'%' if st['z1']<v77z1 else '+'+str(st['z1']-v77z1)})"
    print(f"  bay{j}: {z1s} (v77 {v77z1}){win}  reason={reason}  seated={st['seated']}/{st['total']} "
          f"events={st['events']} packs={st['packcalls']} packt={st['packtime']:.1f}s wall={st['wall']:.1f}s",flush=True)
