"""cranepack greedy SPACE-TIME re-scheduler for high-density. Keep v71's assignment
(which bay each block is in), but RE-SCHEDULE each bay's blocks to maximise concurrency
(admit as many released-waiting blocks as crane-fit at each event) -> earlier entries ->
less tardiness. Grade vs v71."""
import json, os, sys, time
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP
from collections import defaultdict

def find(nm):
    for sub in ("data/train","data/training_instances/train"):
        p=os.path.join(SP,sub,nm+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_26"
TL=float(sys.argv[2]) if len(sys.argv)>2 else 25
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 6
inst=json.load(open(find(NAME))); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
pt=[b["processing_time"] for b in B]; rel=[b["release_time"] for b in B]; due=[b["due_date"] for b in B]
sol=M.algorithm(inst,TL); ck0=check_feasibility(inst,sol)
place={}
for tk,lst in sol["operations"].items():
    for op in lst:
        if op.get("type")=="ENTRY":
            place[op["block_id"]]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[op["block_id"]])
print(f"{NAME}: v71 obj={ck0['objective']:.0f} Z1={ck0['obj1']:.0f}  [{TL}s]",flush=True)

_olc={}
def OL(bid,o):
    k=(bid,o)
    if k not in _olc: _olc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
    return _olc[k]
_wlc={}
def WL(bid,o,x,y):
    k=(bid,o,x,y)
    if k not in _wlc: _wlc[k]=[np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in M.Block(block_id=bid,block_data=B[bid],x=x,y=y,orient_idx=o).layers_at_pos()]
    return _wlc[k]
def obb(b,o): return M._orient_bbox(B[b],o)

def sched_bay(bay, blocks, TLP=0.3, wallcap=20.0):
    """Greedy: admit as many released-waiting blocks as crane-fit at each event.
    Returns placement dict bid->(o,x,y,en,ex)."""
    W=bays[bay]["width"]; H=bays[bay]["height"]
    waiting=set(blocks); present={}  # bid->(o,x,y,en,ex)
    result={}
    t=min(rel[b] for b in blocks)
    guard=0; _tw=time.time(); ncalls=0
    while waiting and guard<5000:
        if time.time()-_tw>wallcap:
            # budget out: place remaining at their earliest release (no concurrency opt)
            for b in list(waiting):
                result[b]=(place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"],place[b]["ex"]); waiting.discard(b)
            print(f"    bay{bay}: wallcap hit after {ncalls} cranepack calls, {len(result)}/{len(blocks)}",flush=True)
            return result
        guard+=1
        # retire finished
        for b in [b for b,v in present.items() if v[4]<=t]:
            del present[b]
        avail=[b for b in waiting if rel[b]<=t]
        if not avail:
            nxt=min([rel[b] for b in waiting if rel[b]>t] or [t+1])
            t=nxt; continue
        avail=sorted(avail,key=lambda b:(due[b],rel[b]))[:24]   # EDD, cap for tractable cranepack
        # cranepack: place avail among present(frozen), entry=t
        froz=[(WL(b,v[0],v[1],v[2]),int(v[3]),int(v[4])) for b,v in present.items()]
        bin=[]; cli=[]
        for b in avail:
            cli.append(b)
            bin.append(([OL(b,o) for o in range(len(B[b]["shape"]))],
                        [tuple(float(v) for v in obb(b,o)) for o in range(len(B[b]["shape"]))],
                        [(int(t),int(t+pt[b]))]))
        ncalls+=1; res=CP.pack(bin,float(W),float(H),STEP,TLP,seed=1,warm=None,frozen=froz)
        admitted=0
        for (loc,o,x,y,en,ex) in res[1]:
            b=cli[loc]; present[b]=(o,x,y,t,t+pt[b]); result[b]=(o,x,y,t,t+pt[b])
            waiting.discard(b); admitted+=1
        if admitted==0:
            # advance to next exit (space frees) or next release
            cands=[v[4] for v in present.values() if v[4]>t]+[rel[b] for b in waiting if rel[b]>t]
            if not cands:
                # deadlock: force place remaining one-by-one at t (should not happen)
                for b in list(waiting):
                    result[b]=(place[b]["oi"],place[b]["x"],place[b]["y"],t,t+pt[b]); waiting.discard(b)
                break
            t=min(cands)
    return result

t0=time.time()
bybay=defaultdict(list)
for b in place: bybay[place[b]["bay"]].append(b)
newplace={}
for bay in range(m):
    if not bybay[bay]: continue
    r=sched_bay(bay,bybay[bay])
    for b,v in r.items(): newplace[b]=(bay,)+v
sched_t=time.time()-t0

# build + grade
al=[{"block_id":b,"bay_id":newplace[b][0],"orient_idx":newplace[b][1],"x":newplace[b][2],
     "y":newplace[b][3],"entry_time":newplace[b][4],"exit_time":newplace[b][5]} for b in range(n) if b in newplace]
if len(al)<n:
    print(f"  incomplete {len(al)}/{n}")
ck=check_feasibility(inst,M._build_operations(al)) if len(al)==n else {"feasible":False}
if ck.get("feasible"):
    d=ck0['objective']-ck['objective']
    print(f"  cranepack-sched: obj={ck['objective']:.0f} Z1={ck['obj1']:.0f}  delta={d:+.0f} "
          f"({'WIN '+str(round(100*d/ck0['objective'],1))+'%' if d>0 else 'lose'})  [{sched_t:.0f}s]",flush=True)
else:
    print(f"  cranepack-sched: INFEASIBLE/incomplete  [{sched_t:.0f}s]",flush=True)
