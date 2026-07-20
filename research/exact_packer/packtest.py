"""Validate cranepack (pure-C++ MIS packer) vs Gurobi=10 / greedy=7 on prob_20 bay1
clique, and exact-verify returned placements with grader_conflict."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import conflictgen as CG
from utils import Bay
import cranepack as CP
from collections import defaultdict

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
JBAY=int(sys.argv[2]) if len(sys.argv)>2 else 1
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 6
TL=float(sys.argv[4]) if len(sys.argv)>4 else 1.0
SEED=int(sys.argv[5]) if len(sys.argv)>5 else 12345
d=json.load(open(find(NAME))); B=d["blocks"]; bays=d["bays"]; n=len(B)
j=JBAY; W=bays[j]["width"]; H=bays[j]["height"]
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)
grp=pref[j]
times=sorted(set(B[b]["release_time"] for b in grp))
best_t=max(times,key=lambda t:sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]

# ---- greedy baseline (st_best) for warm-start + comparison ----
st=M._load_st3(); bw=[float(b["width"]) for b in bays]; bh=[float(b["height"]) for b in bays]; bu=M._bay_unit_weights(bays)
st.st_init(bw,bh,bu); st.st_clear()
w1=float(d["weights"]["w1"]); w3=float(d["weights"]["w3"]); gplace={}; cur=[0.0]*len(bays)
for bid in sorted(clique,key=lambda b:(B[b]["due_date"],B[b]["release_time"])):
    bd=B[bid]; rt=bd["release_time"]; pt2=bd["processing_time"]; due=float(bd["due_date"])
    prefs=[float(p) for p in bd["bay_preferences"]]; wl=float(bd["workload"]); ol=[];bb2=[]
    for o in range(len(bd["shape"])):
        blk=M.Block(block_id=bid,block_data=bd,x=0.0,y=0.0,orient_idx=o)
        ol.append([np.ascontiguousarray(np.asarray(Lz,dtype=np.float64)) for Lz in blk.resolved_layers()])
        b4=M._orient_bbox(bd,o); bb2.append([float(b4[0]),float(b4[1]),float(b4[2]),float(b4[3])])
    res=st.st_best(ol,bb2,int(rt),int(pt2),due,prefs,w1,w3,list(cur),wl,[int(rt)],1)
    if res[0] and int(res[1])==j:
        _,bay,o,x,yy,en,ex=res; st.st_add(ol[int(o)],float(x),float(yy),int(en),int(ex),int(bay),wl); cur[j]+=wl
        gplace[bid]=(int(o),int(x),int(yy))
gc=len(gplace)

# ---- build cranepack input: per-block (orient_layers world-at-origin, obb, entry, exit) ----
# NOTE: cranepack expects layers_at_pos()-style world coords at (x=0,y=0) origin so the
# C++ side just adds (x,y). Block.layers_at_pos() at x=0,y=0 == resolved-in-world-at-origin.
def orient_layers(bid,o):
    blk=M.Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=o)
    out=[]
    for L in blk.layers_at_pos():
        out.append(np.ascontiguousarray(np.asarray(L,dtype=np.float64)))
    return out

cli_idx={bid:i for i,bid in enumerate(clique)}  # local index for C++
blocks_in=[]
for bid in clique:
    ols=[]; obbs=[]
    for o in range(len(B[bid]["shape"])):
        ols.append(orient_layers(bid,o))
        b4=M._orient_bbox(B[bid],o); obbs.append((float(b4[0]),float(b4[1]),float(b4[2]),float(b4[3])))
    en=B[bid]["release_time"]; ex=en+B[bid]["processing_time"]
    blocks_in.append((ols, obbs, [(int(en), int(ex))]))

warm=[(cli_idx[bid],o,x,y) for bid,(o,x,y) in gplace.items()]

t0=time.time()
best,placements,ncol,nedge,build_ms,solve_ms,_cd,_ed,_wc=CP.pack(blocks_in,float(W),float(H),STEP,TL,seed=SEED,warm=warm)
wall=time.time()-t0

# ---- exact verify with grader_conflict ----
sel=[(clique[b],o,x,y) for (b,o,x,y,_e,_x) in placements]
bad=0
for ii in range(len(sel)):
    for jj in range(ii+1,len(sel)):
        b1,o1,x1,y1=sel[ii]; b2,o2,x2,y2=sel[jj]
        e1=B[b1]["release_time"]; x1e=e1+B[b1]["processing_time"]
        e2=B[b2]["release_time"]; x2e=e2+B[b2]["processing_time"]
        A=M.Block(block_id=b1,block_data=B[b1],x=x1,y=y1,orient_idx=o1)
        Bk=M.Block(block_id=b2,block_data=B[b2],x=x2,y=y2,orient_idx=o2)
        if CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,e1,x1e,e2,x2e): bad+=1

print(f"{NAME} bay{j} clique={len(clique)} step{STEP} TL={TL}s:")
print(f"  CRANEPACK={best}  vs GREEDY={gc}  (Gurobi ref=10)  bad={bad}")
print(f"  cols={ncol} edges={nedge} | build={build_ms:.0f}ms solve={solve_ms:.0f}ms wall={wall*1000:.0f}ms")
print(f"  >>> {'WIN (matches/beats Gurobi)' if best>=10 else ('improves greedy' if best>gc else 'NO GAIN')}"
      f"{'  *** INVALID (bad>0) ***' if bad>0 else ''}")
