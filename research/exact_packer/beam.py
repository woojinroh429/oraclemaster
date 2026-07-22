"""BEAM-SEARCH crane scheduler (single bay).  Minimises total tardiness under the
exact crane descent constraint, keeping a beam of B partial schedules instead of the
greedy single trajectory (hdlns).  At each event several candidate admission sets are
generated (via cranepack under different urgency weightings); each becomes a beam child;
children are ranked by accumulated tardiness + a valid waiting-tardiness lower bound and
pruned to top-B.  Compares per-bay Z1 to v77 on prob_30.
Usage: python3.12 beam.py prob_30 [B=4] [step=4] [wallcap_per_bay=90]
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
BW=int(sys.argv[2]) if len(sys.argv)>2 else 4
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 4
WCAP=float(sys.argv[4]) if len(sys.argv)>4 else 90.0
TLP=0.4
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
def area(b): bb=obb(b,0); return (bb[2]-bb[0])*(bb[3]-bb[1])

def admit(bay, avail, present, t, weights):
    """One cranepack admission at time t: which of avail get placed (crane-fit vs present)."""
    W=bays[bay]["width"]; H=bays[bay]["height"]
    froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
    binL=[]
    for b in avail:
        binL.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                     [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                     [(int(t),int(t+pt[b]))]))
    res=CP.pack(binL,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz,weights=[float(w) for w in weights])
    got={}
    for (loc,o,x,y,en,ex) in res[1]:
        b=avail[loc]; got[b]=(o,x,y,t,t+pt[b])
    return got

def waitLB(waiting, t):
    s=0
    for b in waiting:
        e=max(t, rel[b])
        s+=max(0, e+pt[b]-due[b])
    return s

def beam_bay(bay, blocks, wallcap):
    if not blocks: return {}, 0
    t0min=min(rel[b] for b in blocks)
    # state: dict(present, waiting, t, tard, result)
    init=dict(present={}, waiting=set(blocks), t=t0min, tard=0, result={})
    beam=[init]; tw=time.time(); guard=0
    def key(s): return s["tard"]+waitLB(s["waiting"], s["t"])
    while any(s["waiting"] for s in beam) and guard<20000:
        if time.time()-tw>wallcap: break
        guard+=1
        children=[]
        for s in beam:
            if not s["waiting"]:
                children.append(s); continue
            t=s["t"]; present=dict(s["present"])
            for b in [b for b,v in present.items() if v[4]<=t]: del present[b]
            avail=[b for b in s["waiting"] if rel[b]<=t]
            if not avail:
                nxt=min([rel[b] for b in s["waiting"] if rel[b]>t] or [t+1])
                children.append(dict(present=present, waiting=set(s["waiting"]), t=nxt, tard=s["tard"], result=s["result"])); continue
            av=sorted(avail,key=lambda b:(due[b],rel[b]))[:24]
            # candidate weightings -> diverse admission sets
            wsets=[
                [1000.0/max(1,due[b]-t-pt[b]) for b in av],          # urgency
                [1.0 for b in av],                                    # uniform (max count)
                [float(area(b)) for b in av],                         # big-first
            ]
            seen=set()
            for wts in wsets:
                got=admit(bay, av, present, t, wts)
                if not got: continue
                sig=frozenset(got.keys())
                if sig in seen: continue
                seen.add(sig)
                np_=dict(present); res_=dict(s["result"]); wt_=set(s["waiting"]); tard_=s["tard"]
                for b,v in got.items():
                    np_[b]=v; res_[b]=v; wt_.discard(b)
                    tard_+=max(0, v[4]-due[b])
                # advance time to next event
                cands=[v[4] for v in np_.values() if v[4]>t]+[rel[b] for b in wt_ if rel[b]>t]
                nt=min(cands) if cands else t+1
                children.append(dict(present=np_, waiting=wt_, t=nt, tard=tard_, result=res_))
            # also a HOLD candidate: admit nothing, jump to next exit (leave room for future)
            cands=[v[4] for v in present.values() if v[4]>t]
            if cands:
                children.append(dict(present=present, waiting=set(s["waiting"]), t=min(cands), tard=s["tard"], result=s["result"]))
        if not children: break
        children.sort(key=key)
        beam=children[:BW]
    done=[s for s in beam if not s["waiting"]]
    if not done: return None, None
    best=min(done, key=lambda s:s["tard"])
    return best["result"], best["tard"]

# v77 per-bay
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
print(f"{NAME}: v77 obj={objv:.0f} Z1={z1v:.0f}  (BEAM width={BW} step={STEP})",flush=True)
tot_v77=0; tot_beam=0
for j in range(m):
    bl=bybay[j]
    if not bl: continue
    v77z1=sum(max(0,place[b]["ex"]-due[b]) for b in bl); tot_v77+=v77z1
    t0=time.time(); r,tard=beam_bay(j, bl, WCAP)
    if r is None:
        print(f"  bay{j}: {len(bl)}blk BEAM FAILED (no full schedule)  v77={v77z1} [{time.time()-t0:.0f}s]",flush=True); tot_beam=None; continue
    if tot_beam is not None: tot_beam+=tard
    win="WIN -"+str(round(100*(v77z1-tard)/max(1,v77z1)))+"%" if tard<v77z1 else ("+"+str(int(tard-v77z1)))
    print(f"  bay{j}: {len(bl)}blk  BEAM bay-Z1={tard:.0f}  v77={v77z1}  {win}  [{time.time()-t0:.0f}s]",flush=True)
if tot_beam is not None:
    print(f"\n{NAME}: BEAM total per-bay Z1={tot_beam:.0f}  vs v77 Z1={tot_v77:.0f}  {'WIN' if tot_beam<tot_v77 else 'no win'}",flush=True)
