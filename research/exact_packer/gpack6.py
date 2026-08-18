"""EXACT pairwise (numba) conflict + greedy warm-start + MIPFocus=1.
The exact model admits the greedy solution -> valid warm-start. Test solve speed."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import fastconf as FC
from utils import Bay
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1]; JBAY=int(sys.argv[2]); STEP=int(sys.argv[3]); TL=float(sys.argv[4]) if len(sys.argv)>4 else 30
d=json.load(open(find(NAME))); B=d["blocks"]; bays=d["bays"]; n=len(B)
j=JBAY; W=bays[j]["width"]; H=bays[j]["height"]
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)
grp=pref[j]
times=sorted(set(B[b]["release_time"] for b in grp))
best_t=max(times,key=lambda t:sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]

# greedy (warm-start + baseline)
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

# columns (include greedy positions)
t0=time.time(); cols=[]
for bid in clique:
    bd=B[bid]; en=bd["release_time"]; ex=en+bd["processing_time"]
    for o in range(len(bd["shape"])):
        bb=M._orient_bbox(bd,o)
        xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
        if xlo>xhi or ylo>yhi: continue
        gx=set(range(xlo,xhi+1,STEP)); gy=set(range(ylo,yhi+1,STEP))
        if bid in gplace and gplace[bid][0]==o: gx.add(gplace[bid][1]); gy.add(gplace[bid][2])
        for x in sorted(gx):
            for y in sorted(gy):
                if not(xlo<=x<=xhi and ylo<=y<=yhi): continue
                Aa,Ap=FC.layers_arr_poly(d,bid,x,y,o)
                allpts=np.vstack([a for a in Aa if len(a)>=3])
                cols.append(dict(bid=bid,x=x,y=y,o=o,en=en,ex=ex,arr=Aa,poly=Ap,
                                 bb=(allpts[:,0].min(),allpts[:,1].min(),allpts[:,0].max(),allpts[:,1].max())))
tcol=time.time()-t0
# exact pairwise conflicts (numba)
t0=time.time(); E=[]
for a in range(len(cols)):
    ca=cols[a]; ax0,ay0,ax1,ay1=ca["bb"]
    for b in range(a+1,len(cols)):
        cb=cols[b]
        if ca["bid"]==cb["bid"]: continue
        bx0,by0,bx1,by1=cb["bb"]
        if ax1<=bx0 or bx1<=ax0 or ay1<=by0 or by1<=ay0: continue
        if not(ca["en"]<cb["ex"] and cb["en"]<ca["ex"]): continue
        if FC.conflict(ca["arr"],ca["poly"],ca["en"],ca["ex"],cb["arr"],cb["poly"],cb["en"],cb["ex"]): E.append((a,b))
tconf=time.time()-t0

m=gp.Model("p"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",TL); m.setParam("Threads",4)
m.setParam("MIPFocus",1)
y=[m.addVar(vtype=GRB.BINARY) for _ in cols]
byb=defaultdict(list)
for i,c in enumerate(cols): byb[c["bid"]].append(i)
pl={b:m.addVar(vtype=GRB.BINARY) for b in clique}
for b in clique: m.addConstr(gp.quicksum(y[i] for i in byb[b])==pl[b])
for (a,b) in E: m.addConstr(y[a]+y[b]<=1)
m.setObjective(gp.quicksum(pl.values()), GRB.MAXIMIZE)
# warm start (greedy is exact-feasible)
gcolidx={}
for ci,c in enumerate(cols):
    if c["bid"] in gplace and (c["o"],c["x"],c["y"])==gplace[c["bid"]]: gcolidx[c["bid"]]=ci
for v in y: v.Start=0
for b,ci in gcolidx.items(): y[ci].Start=1
ts=time.time(); m.optimize(); tsolve=time.time()-ts
got=int(round(m.ObjVal))
print(f"{NAME} bay{j} clique={len(clique)} step{STEP}: GUROBI={got} (gap={m.MIPGap:.3f}) vs GREEDY={gc} (+{got-gc}) "
      f"| cols={len(cols)} conf={len(E)} warm={len(gcolidx)} [col{tcol:.1f} conf{tconf:.1f} solve{tsolve:.1f}s]",flush=True)
