"""DESIGN VERIFICATION (before C++): do EXTREME-POINT columns (few hundred) capture the
same packing density as the fine grid (Gurobi=10)?  If yes -> EP design valid -> C++.

EP pool = contact positions: each block against bay walls/corners and against every
OTHER block's bbox edges (using the greedy arrangement as reference frame), plus the
greedy positions themselves.  Exact numba conflict; warm-start; solve.  Compare count
+ Gurobi objective to the step-6 grid reference (10)."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"research"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
import fastconf as FC
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
d=json.load(open(find(NAME))); B=d["blocks"]; bays=d["bays"]; n=len(B)
j=JBAY; W=bays[j]["width"]; H=bays[j]["height"]
pref=defaultdict(list)
for b in range(n):
    p=B[b]["bay_preferences"]; pref[p.index(max(p))].append(b)
grp=pref[j]
times=sorted(set(B[b]["release_time"] for b in grp))
best_t=max(times,key=lambda t:sum(1 for b in grp if B[b]["release_time"]<=t<B[b]["release_time"]+B[b]["processing_time"]))
clique=[b for b in grp if B[b]["release_time"]<=best_t<B[b]["release_time"]+B[b]["processing_time"]]

# per (block,orient) bbox (lx0,ly0,lx1,ly1) so width=lx1-lx0
def obb(bid,o): return M._orient_bbox(B[bid],o)

# greedy arrangement (reference frame + warm-start + baseline)
st=M._load_st3(); bw=[float(b["width"]) for b in bays]; bh=[float(b["height"]) for b in bays]; bu=M._bay_unit_weights(bays)
st.st_init(bw,bh,bu); st.st_clear()
w1=float(d["weights"]["w1"]); w3=float(d["weights"]["w3"]); gplace={}; cur=[0.0]*len(bays)
for bid in sorted(clique,key=lambda b:(B[b]["due_date"],B[b]["release_time"])):
    bd=B[bid]; rt=bd["release_time"]; pt2=bd["processing_time"]; due=float(bd["due_date"])
    prefs=[float(p) for p in bd["bay_preferences"]]; wl=float(bd["workload"]); ol=[];bb2=[]
    for o in range(len(bd["shape"])):
        blk=M.Block(block_id=bid,block_data=bd,x=0.0,y=0.0,orient_idx=o)
        ol.append([np.ascontiguousarray(np.asarray(Lz,dtype=np.float64)) for Lz in blk.resolved_layers()])
        b4=obb(bid,o); bb2.append([float(b4[0]),float(b4[1]),float(b4[2]),float(b4[3])])
    res=st.st_best(ol,bb2,int(rt),int(pt2),due,prefs,w1,w3,list(cur),wl,[int(rt)],1)
    if res[0] and int(res[1])==j:
        _,bay,o,x,yy,en,ex=res; st.st_add(ol[int(o)],float(x),float(yy),int(en),int(ex),int(bay),wl); cur[j]+=wl
        gplace[bid]=(int(o),int(x),int(yy))
gc=len(gplace)

# reference "occupied bbox rectangles" from greedy (world coords)
refrects=[]
for b,(o,x,y) in gplace.items():
    lx0,ly0,lx1,ly1=obb(b,o); refrects.append((x+lx0, y+ly0, x+lx1, y+ly1))

def ep_positions(bid,o):
    """candidate (x,y) for block bid orient o: bay corners + contacts with ref rects."""
    lx0,ly0,lx1,ly1=obb(bid,o); wdt=lx1-lx0; hgt=ly1-ly0
    xlo,xhi=math.ceil(-lx0),math.floor(W-lx1); ylo,yhi=math.ceil(-ly0),math.floor(H-ly1)
    if xlo>xhi or ylo>yhi: return []
    xs=set([xlo,xhi]); ys=set([ylo,yhi])
    for (rx0,ry0,rx1,ry1) in refrects:
        # x so block's left edge = ref right edge:  x+lx0 = rx1 -> x = rx1-lx0
        xs.add(int(round(rx1-lx0)))         # block to the RIGHT of ref
        xs.add(int(round(rx0-lx1)))         # block to the LEFT of ref
        ys.add(int(round(ry1-ly0)))         # block ABOVE ref
        ys.add(int(round(ry0-ly1)))         # block BELOW ref
        ys.add(int(round(ry0-ly0)))         # align bottoms
        xs.add(int(round(rx0-lx0)))         # align lefts
    xs={x for x in xs if xlo<=x<=xhi}; ys={y for y in ys if ylo<=y<=yhi}
    pos=set((x,y) for x in xs for y in ys)
    if bid in gplace and gplace[bid][0]==o: pos.add((gplace[bid][1],gplace[bid][2]))
    return list(pos)

# build EP columns
t0=time.time(); cols=[]
for bid in clique:
    bd=B[bid]; en=bd["release_time"]; ex=en+bd["processing_time"]
    for o in range(len(bd["shape"])):
        for (x,y) in ep_positions(bid,o):
            Aa,Ap=FC.layers_arr_poly(d,bid,x,y,o)
            allpts=np.vstack([a for a in Aa if len(a)>=3])
            cols.append(dict(bid=bid,x=x,y=y,o=o,en=en,ex=ex,arr=Aa,poly=Ap,
                             bb=(allpts[:,0].min(),allpts[:,1].min(),allpts[:,0].max(),allpts[:,1].max())))
tcol=time.time()-t0
# exact conflicts
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
m=gp.Model("p"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",20); m.setParam("Threads",4); m.setParam("MIPFocus",1)
y=[m.addVar(vtype=GRB.BINARY) for _ in cols]
byb=defaultdict(list)
for i,c in enumerate(cols): byb[c["bid"]].append(i)
pl={b:m.addVar(vtype=GRB.BINARY) for b in clique}
for b in clique: m.addConstr(gp.quicksum(y[i] for i in byb[b])==pl[b])
for (a,b) in E: m.addConstr(y[a]+y[b]<=1)
m.setObjective(gp.quicksum(pl.values()), GRB.MAXIMIZE)
for ci,c in enumerate(cols):
    if c["bid"] in gplace and (c["o"],c["x"],c["y"])==gplace[c["bid"]]: y[ci].Start=1
ts=time.time(); m.optimize(); tsolve=time.time()-ts
got=int(round(m.ObjVal))
# exact verify
sel=[i for i in range(len(cols)) if y[i].X>0.5]; bad=0
for ii in range(len(sel)):
    for jj in range(ii+1,len(sel)):
        ca=cols[sel[ii]]; cb=cols[sel[jj]]
        if ca["bid"]==cb["bid"]: continue
        A=M.Block(block_id=ca["bid"],block_data=B[ca["bid"]],x=ca["x"],y=ca["y"],orient_idx=ca["o"])
        Bk=M.Block(block_id=cb["bid"],block_data=B[cb["bid"]],x=cb["x"],y=cb["y"],orient_idx=cb["o"])
        if CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,ca["en"],ca["ex"],cb["en"],cb["ex"]): bad+=1
print(f"EP {NAME} bay{j} clique={len(clique)}: cols={len(cols)} (grid step6=1404) conf={len(E)} "
      f"GUROBI={got} vs GREEDY={gc} gap={m.MIPGap:.2f} bad={bad} [col{tcol:.1f} conf{tconf:.1f} solve{tsolve:.1f}s]",flush=True)
print(f"  >>> VERIFY: EP reaches {got} vs grid-ref 10? {'YES design-valid' if got>=10 else ('PARTIAL' if got>gc else 'NO loses density')}",flush=True)
