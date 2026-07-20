"""Coarse-to-fine packer: step-6 global solve, then FINE local refinement near the
coarse solution to compact and squeeze in more blocks."""
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

def mkcol(bid,x,y,o):
    en=B[bid]["release_time"]; ex=en+B[bid]["processing_time"]
    Aa,Ap=FC.layers_arr_poly(d,bid,x,y,o)
    allpts=np.vstack([a for a in Aa if len(a)>=3])
    return dict(bid=bid,x=x,y=y,o=o,en=en,ex=ex,arr=Aa,poly=Ap,
                bb=(allpts[:,0].min(),allpts[:,1].min(),allpts[:,0].max(),allpts[:,1].max()))

def solve(cols, warm, tl):
    E=[]
    for a in range(len(cols)):
        ca=cols[a]; ax0,ay0,ax1,ay1=ca["bb"]
        for b in range(a+1,len(cols)):
            cb=cols[b]
            if ca["bid"]==cb["bid"]: continue
            bx0,by0,bx1,by1=cb["bb"]
            if ax1<=bx0 or bx1<=ax0 or ay1<=by0 or by1<=ay0: continue
            if not(ca["en"]<cb["ex"] and cb["en"]<ca["ex"]): continue
            if FC.conflict(ca["arr"],ca["poly"],ca["en"],ca["ex"],cb["arr"],cb["poly"],cb["en"],cb["ex"]): E.append((a,b))
    m=gp.Model("p"); m.setParam("OutputFlag",0); m.setParam("TimeLimit",tl); m.setParam("Threads",4); m.setParam("MIPFocus",1)
    y=[m.addVar(vtype=GRB.BINARY) for _ in cols]
    byb=defaultdict(list)
    for i,c in enumerate(cols): byb[c["bid"]].append(i)
    pl={b:m.addVar(vtype=GRB.BINARY) for b in set(c["bid"] for c in cols)}
    for b in pl: m.addConstr(gp.quicksum(y[i] for i in byb[b])==pl[b])
    for (a,b) in E: m.addConstr(y[a]+y[b]<=1)
    m.setObjective(gp.quicksum(pl.values()), GRB.MAXIMIZE)
    for ci,c in enumerate(cols):
        if warm.get(c["bid"])==(c["o"],c["x"],c["y"]): y[ci].Start=1
    m.optimize()
    sel={cols[i]["bid"]:(cols[i]["o"],cols[i]["x"],cols[i]["y"]) for i in range(len(cols)) if y[i].X>0.5}
    return int(round(m.ObjVal)), sel, len(E)

# ---- Phase 1: coarse step 6 ----
t0=time.time()
STEP=6; cc=[]
for bid in clique:
    for o in range(len(B[bid]["shape"])):
        bb=M._orient_bbox(B[bid],o)
        xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
        if xlo>xhi or ylo>yhi: continue
        for x in range(xlo,xhi+1,STEP):
            for y in range(ylo,yhi+1,STEP): cc.append(mkcol(bid,x,y,o))
g1,S1,e1=solve(cc,{},15)
t1=time.time()-t0
print(f"Phase1 (step6): placed={g1} cols={len(cc)} conf={e1} [{t1:.1f}s]",flush=True)

# ---- Phase 2: fine refinement near S1 ----
t0=time.time()
WIN=5; FINE=1; cf=[]
placed=set(S1.keys())
for bid in clique:
    bb_o=lambda o: M._orient_bbox(B[bid],o)
    if bid in S1:
        o,cx,cy=S1[bid]; bb=bb_o(o)
        xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
        for x in range(max(xlo,cx-WIN),min(xhi,cx+WIN)+1,FINE):
            for y in range(max(ylo,cy-WIN),min(yhi,cy+WIN)+1,FINE): cf.append(mkcol(bid,x,y,o))
    else:  # unplaced: coarse step-4 whole bay, all orient (chance to slot in)
        for o in range(len(B[bid]["shape"])):
            bb=bb_o(o); xlo,xhi=math.ceil(-bb[0]),math.floor(W-bb[2]); ylo,yhi=math.ceil(-bb[1]),math.floor(H-bb[3])
            if xlo>xhi or ylo>yhi: continue
            for x in range(xlo,xhi+1,4):
                for y in range(ylo,yhi+1,4): cf.append(mkcol(bid,x,y,o))
g2,S2,e2=solve(cf,S1,20)
t2=time.time()-t0
# exact verify final
bad=0; selc=[(b,)+v for b,v in S2.items()]
for ii in range(len(selc)):
    for jj in range(ii+1,len(selc)):
        b1,o1,x1,y1=selc[ii]; b2,o2,x2,y2=selc[jj]
        e1_=B[b1]["release_time"]; x1e=e1_+B[b1]["processing_time"]; e2_=B[b2]["release_time"]; x2e=e2_+B[b2]["processing_time"]
        A=M.Block(block_id=b1,block_data=B[b1],x=x1,y=y1,orient_idx=o1); Bk=M.Block(block_id=b2,block_data=B[b2],x=x2,y=y2,orient_idx=o2)
        if CG.grader_conflict(Bay(width=W,height=H,id=j),A,Bk,e1_,x1e,e2_,x2e): bad+=1
print(f"Phase2 (fine ±{WIN} refine): placed={g2} cols={len(cf)} conf={e2} bad={bad} [{t2:.1f}s]",flush=True)
print(f">>> COARSE-TO-FINE: step6={g1} -> refined={g2}  (greedy=7)  {'IMPROVED!' if g2>g1 else 'no gain'}",flush=True)
