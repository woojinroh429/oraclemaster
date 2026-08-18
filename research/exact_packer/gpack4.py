"""Fast exact clique packer: numba conflict + footprint cell-clique Gurobi model.
Cell-cliques (columns sharing a footprint subcell => <=1) compress the model and
capture nearly all conflicts; residual crane-only pairs added exact via numba.
Goal: fast solve (<10s) that beats greedy."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import fastconf as FC, raster as RS
from utils import Bay
import conflictgen as CG
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"; JBAY=int(sys.argv[2]) if len(sys.argv)>2 else 1
STEP=int(sys.argv[3]) if len(sys.argv)>3 else 3
d=json.load(open(find(NAME))); B=d["blocks"]; bays=d["bays"]; n=len(B)
j=JBAY; W=bays[j]["width"]; H=bays[j]["height"]
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)
grp=pref[j]
times=sorted(set(B[b]["release_time"] for b in grp))
best_t=max(times,key=lambda t:sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]
print(f"{NAME} bay{j} {W}x{H} clique={len(clique)}",flush=True)

# footprint bitmap per (block,orient): union of layers, rasterized+dilated
Rr=RS.R
fpcache={}
def footprint(bid,o):
    key=(bid,o)
    if key in fpcache: return fpcache[key]
    bms=RS.layer_bitmaps(d,bid,o)
    # union all layers into common subcell frame
    sxs=[g[1] for g in bms if g[0] is not None]; sys_=[g[2] for g in bms if g[0] is not None]
    if not sxs: fpcache[key]=(None,0,0); return fpcache[key]
    minx=min(sxs); miny=min(sys_)
    maxx=max(g[1]+g[0].shape[1] for g in bms if g[0] is not None)
    maxy=max(g[2]+g[0].shape[0] for g in bms if g[0] is not None)
    U=np.zeros((maxy-miny,maxx-minx),bool)
    for g,sx,sy in bms:
        if g is None: continue
        U[sy-miny:sy-miny+g.shape[0], sx-minx:sx-minx+g.shape[1]]|=g
    fpcache[key]=(U,minx,miny); return fpcache[key]

# build columns + occupied subcells (footprint shifted to placement)
t0=time.time(); cols=[]
for bid in clique:
    bd=B[bid]; en=bd["release_time"]; ex=en+bd["processing_time"]
    for o in range(len(bd["shape"])):
        bb=M._orient_bbox(bd,o)
        xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
        if xlo>xhi or ylo>yhi: continue
        U,minx,miny=footprint(bid,o)
        if U is None: continue
        ys,xs=np.where(U)
        for x in range(xlo,xhi+1,STEP):
            for y in range(ylo,yhi+1,STEP):
                # occupied subcells at this placement
                sc_x=xs+minx+x*Rr; sc_y=ys+miny+y*Rr
                cols.append(dict(bid=bid,x=x,y=y,o=o,en=en,ex=ex,scx=sc_x,scy=sc_y))
tcol=time.time()-t0

# cell -> columns covering it (only among co-present -> here all clique co-present)
t0=time.time()
cell2cols=defaultdict(list)
for ci,c in enumerate(cols):
    for sx,sy in zip(c["scx"],c["scy"]):
        cell2cols[(sx,sy)].append(ci)
tcell=time.time()-t0

m=gp.Model("p"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",30); m.setParam("Threads",4)
y=[m.addVar(vtype=GRB.BINARY) for _ in cols]
byb=defaultdict(list)
for i,c in enumerate(cols): byb[c["bid"]].append(i)
pl={b:m.addVar(vtype=GRB.BINARY) for b in clique}
for b in clique: m.addConstr(gp.quicksum(y[i] for i in byb[b])==pl[b])
ncon=0
for cell,cl in cell2cols.items():
    if len(cl)>1:
        m.addConstr(gp.quicksum(y[i] for i in cl)<=1); ncon+=1
m.setObjective(gp.quicksum(pl.values()), GRB.MAXIMIZE)
ts=time.time(); m.optimize(); tsolve=time.time()-ts
sel=[i for i in range(len(cols)) if y[i].X>0.5]
got=int(round(m.ObjVal))

# exact verify with grader (footprint cliques are conservative -> should be feasible; check)
bad=0
for ii in range(len(sel)):
    for jj in range(ii+1,len(sel)):
        ca=cols[sel[ii]]; cb=cols[sel[jj]]
        if ca["bid"]==cb["bid"]: continue
        A=M.Block(block_id=ca["bid"],block_data=B[ca["bid"]],x=ca["x"],y=ca["y"],orient_idx=ca["o"])
        Bk=M.Block(block_id=cb["bid"],block_data=B[cb["bid"]],x=cb["x"],y=cb["y"],orient_idx=cb["o"])
        if CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,ca["en"],ca["ex"],cb["en"],cb["ex"]): bad+=1
print(f"GUROBI(cell-clique)={got} gap={m.MIPGap:.2f} exact_bad_pairs={bad} | cols={len(cols)} cliques={ncon} "
      f"[col{tcol:.1f} cell{tcell:.1f} solve{tsolve:.1f}s]",flush=True)

# greedy
st=M._load_st3(); bw=[float(b["width"]) for b in bays]; bh=[float(b["height"]) for b in bays]; bu=M._bay_unit_weights(bays)
st.st_init(bw,bh,bu); st.st_clear()
w1=float(d["weights"]["w1"]); w3=float(d["weights"]["w3"]); gc=0; cur=[0.0]*len(bays)
for bid in sorted(clique,key=lambda b:(B[b]["due_date"],B[b]["release_time"])):
    bd=B[bid]; rt=bd["release_time"]; pt2=bd["processing_time"]; due=float(bd["due_date"])
    prefs=[float(p) for p in bd["bay_preferences"]]; wl=float(bd["workload"]); ol=[];bb2=[]
    for o in range(len(bd["shape"])):
        blk=M.Block(block_id=bid,block_data=bd,x=0.0,y=0.0,orient_idx=o)
        ol.append([np.ascontiguousarray(np.asarray(Lz,dtype=np.float64)) for Lz in blk.resolved_layers()])
        b4=M._orient_bbox(bd,o); bb2.append([float(b4[0]),float(b4[1]),float(b4[2]),float(b4[3])])
    res=st.st_best(ol,bb2,int(rt),int(pt2),due,prefs,w1,w3,list(cur),wl,[int(rt)],1)
    if res[0] and int(res[1])==j:
        _,bay,o,x,yy,en,ex=res; st.st_add(ol[int(o)],float(x),float(yy),int(en),int(ex),int(bay),wl); cur[j]+=wl; gc+=1
print(f"--> GUROBI={got} vs GREEDY={gc} (delta +{got-gc}) [bad={bad}]",flush=True)
