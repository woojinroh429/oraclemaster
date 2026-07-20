"""Scan every bay of an instance: extract the peak clique of blocks that PREFER that
bay, run greedy (st_best) vs cranepack, report where cranepack packs more (the
density lever).  This finds the binding cliques across the whole instance."""
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
STEP=int(sys.argv[2]) if len(sys.argv)>2 else 6
TL=float(sys.argv[3]) if len(sys.argv)>3 else 0.15
d=json.load(open(find(NAME))); B=d["blocks"]; bays=d["bays"]; n=len(B); m=len(bays)
w1=float(d["weights"]["w1"]); w3=float(d["weights"]["w3"])
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)

st=M._load_st3(); bw=[float(b["width"]) for b in bays]; bh=[float(b["height"]) for b in bays]; bu=M._bay_unit_weights(bays)

def orient_layers(bid,o):
    blk=M.Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=o)
    return [np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in blk.layers_at_pos()]

def greedy_pack(clique,j):
    st.st_init(bw,bh,bu); st.st_clear(); gplace={}; cur=[0.0]*m
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
    return gplace

print(f"{NAME}: n={n} m={m} step{STEP} TL={TL}s  (blocks preferring each bay -> peak clique)")
tot_g=0; tot_c=0; wins=0
for j in range(m):
    grp=pref[j]
    if len(grp)<2: continue
    times=sorted(set(B[b]["release_time"] for b in grp))
    best_t=max(times,key=lambda t:sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
    clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]
    if len(clique)<3: continue
    W=bays[j]["width"]; H=bays[j]["height"]
    gplace=greedy_pack(clique,j); gc=len(gplace)
    cli_idx={bid:i for i,bid in enumerate(clique)}
    blocks_in=[]
    for bid in clique:
        ols=[orient_layers(bid,o) for o in range(len(B[bid]["shape"]))]
        obbs=[tuple(float(v) for v in M._orient_bbox(B[bid],o)) for o in range(len(B[bid]["shape"]))]
        en=B[bid]["release_time"]; ex=en+B[bid]["processing_time"]
        blocks_in.append((ols,obbs,[(int(en),int(ex))]))
    warm=[(cli_idx[bid],o,x,y) for bid,(o,x,y) in gplace.items()]
    t0=time.time()
    best,pl,ncol,nedge,bms,sms,_cd,_ed,_wc=CP.pack(blocks_in,float(W),float(H),STEP,TL,seed=12345,warm=warm)
    wall=time.time()-t0
    # exact verify
    sel=[(clique[b],o,x,y) for (b,o,x,y,_e,_x) in pl]; bad=0
    for ii in range(len(sel)):
        for jj in range(ii+1,len(sel)):
            b1,o1,x1,y1=sel[ii]; b2,o2,x2,y2=sel[jj]
            e1=B[b1]["release_time"]; x1e=e1+B[b1]["processing_time"]
            e2=B[b2]["release_time"]; x2e=e2+B[b2]["processing_time"]
            A=M.Block(block_id=b1,block_data=B[b1],x=x1,y=y1,orient_idx=o1)
            Bk=M.Block(block_id=b2,block_data=B[b2],x=x2,y=y2,orient_idx=o2)
            if CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,e1,x1e,e2,x2e): bad+=1
    tot_g+=gc; tot_c+=best
    flag=""
    if best>gc: wins+=1; flag=f"  <== +{best-gc}"
    if bad>0: flag+=f"  ***BAD={bad}***"
    print(f"  bay{j:2d}: clique={len(clique):2d}  greedy={gc:2d}  cranepack={best:2d}  "
          f"[cols={ncol} edges={nedge} {wall*1000:.0f}ms]{flag}")
print(f"  TOTAL greedy={tot_g} cranepack={tot_c} (+{tot_c-tot_g})  bays_improved={wins}")
