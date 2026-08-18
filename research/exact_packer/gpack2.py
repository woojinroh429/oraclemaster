"""Minimal proof-of-concept: on a SMALL co-present block set (a clique) of bay1,
does Gurobi exact set-packing place MORE than the greedy? Small enough to be fast."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v71"))
import myalgorithm as M
import conflictgen as CG
import numpy as np
import gurobipy as gp
from gurobipy import GRB

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

d=json.load(open(find("prob_20"))); B=d["blocks"]; bays=d["bays"]; n=len(B)
j=1; W=bays[j]["width"]; H=bays[j]["height"]
from collections import defaultdict
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)
grp=pref[j]
# pick the peak instant (all preferring at release) and take the co-present clique
rel=[B[b]["release_time"] for b in grp]; pt=[B[b]["processing_time"] for b in grp]
times=sorted(set(rel))
best_t=max(times, key=lambda t: sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]
print(f"bay{j} peak t={best_t}: clique size={len(clique)} blocks (all forced to bay{j}, entry=release)", flush=True)

STEP=int(sys.argv[1]) if len(sys.argv)>1 else 4

def columns(blocks):
    cols=[]
    for bid in blocks:
        bd=B[bid]; en=bd["release_time"]; ex=en+bd["processing_time"]
        for o in range(len(bd["shape"])):
            bb=M._orient_bbox(bd,o)
            xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
            if xlo>xhi or ylo>yhi: continue
            for x in range(xlo,xhi+1,STEP):
                for y in range(ylo,yhi+1,STEP):
                    L=CG.world_layers(d,bid,x,y,o)
                    pts=[p for poly in L if poly for p in poly.exterior.coords]
                    cols.append(dict(bid=bid,x=x,y=y,o=o,en=en,ex=ex,L=L,
                                     bb=(min(p[0] for p in pts),min(p[1] for p in pts),
                                         max(p[0] for p in pts),max(p[1] for p in pts))))
    return cols

t0=time.time(); cols=columns(clique); tcol=time.time()-t0
t0=time.time()
E=[]
for a in range(len(cols)):
    ca=cols[a]
    for b in range(a+1,len(cols)):
        cb=cols[b]
        if ca["bid"]==cb["bid"]: continue
        ax0,ay0,ax1,ay1=ca["bb"]; bx0,by0,bx1,by1=cb["bb"]
        if ax1<=bx0 or bx1<=ax0 or ay1<=by0 or by1<=ay0: continue
        if not (ca["en"]<cb["ex"] and cb["en"]<ca["ex"]): continue
        if CG.conflict(ca["L"],ca["en"],ca["ex"],cb["L"],cb["en"],cb["ex"]): E.append((a,b))
tconf=time.time()-t0
m=gp.Model("p"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",120); m.setParam("Threads",4)
y=[m.addVar(vtype=GRB.BINARY) for _ in cols]
byb=defaultdict(list)
for i,c in enumerate(cols): byb[c["bid"]].append(i)
pl={b:m.addVar(vtype=GRB.BINARY) for b in clique}
for b in clique: m.addConstr(gp.quicksum(y[i] for i in byb[b])==pl[b])
for (a,b) in E: m.addConstr(y[a]+y[b]<=1)
m.setObjective(gp.quicksum(pl.values()), GRB.MAXIMIZE)
ts=time.time(); m.optimize(); tsolve=time.time()-ts
got=int(round(m.ObjVal))

# greedy comparison on the SAME clique
st=M._load_st3(); bw=[float(b["width"]) for b in bays]; bh=[float(b["height"]) for b in bays]; bu=M._bay_unit_weights(bays)
st.st_init(bw,bh,bu); st.st_clear()
w1=float(d["weights"]["w1"]); w3=float(d["weights"]["w3"])
order=sorted(clique,key=lambda b:(B[b]["due_date"],B[b]["release_time"]))
gcount=0; cur=[0.0]*len(bays)
for bid in order:
    bd=B[bid]; rt=bd["release_time"]; pt2=bd["processing_time"]; due=float(bd["due_date"])
    prefs=[float(p) for p in bd["bay_preferences"]]; wl=float(bd["workload"])
    ol=[]; bb2=[]
    for o in range(len(bd["shape"])):
        blk=M.Block(block_id=bid,block_data=bd,x=0.0,y=0.0,orient_idx=o)
        ol.append([np.ascontiguousarray(np.asarray(Lz,dtype=np.float64)) for Lz in blk.resolved_layers()])
        b4=M._orient_bbox(bd,o); bb2.append([float(b4[0]),float(b4[1]),float(b4[2]),float(b4[3])])
    res=st.st_best(ol,bb2,int(rt),int(pt2),due,prefs,w1,w3,list(cur),wl,[int(rt)],1)
    if res[0] and int(res[1])==j:
        _,bay,o,x,yy,en,ex=res
        st.st_add(ol[int(o)],float(x),float(yy),int(en),int(ex),int(bay),wl); cur[j]+=wl; gcount+=1

print(f"clique={len(clique)}: GUROBI max={got} (gap={m.MIPGap:.2f}) vs GREEDY={gcount} "
      f"| cols={len(cols)} conf={len(E)} [col{tcol:.1f}s conf{tconf:.1f}s solve{tsolve:.1f}s]", flush=True)
