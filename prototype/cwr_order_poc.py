"""
Idea #1: ORDER-AWARE window exact-recreate. Rip a congested window of co-active
blocks; jointly decide each block's (orientation, x, y, ENTRY TIME) -> entry time
encodes descent order, so the CP can REORDER (let a pinned block enter before its
current blockers). Everything outside the window is fixed. Pairwise crane conflicts
are exact and order-dependent (the earlier-entering block is present for the later
one's descent). Objective: minimize window tardiness. Current columns are included
so the result is never-worse. If window tardiness drops vs greedy, backbone-LNS
(searching order, not position) is a real lever.
"""
import os, sys, json, time, copy
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M
from utils import check_feasibility

def reconstruct(inst, sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay_id=o["bay_id"],x=o["x"],y=o["y"],
                    orient_idx=o["orient_idx"],entry_time=t,block_id=b)
            else: place.setdefault(b,{})["exit_time"]=t
    for b,p in place.items():
        if "exit_time" not in p: p["exit_time"]=p["entry_time"]+inst["blocks"][b]["processing_time"]
    return place

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def tard(B,col): return max(0, col["exit_time"]-B[col["block_id"]]["due_date"])

def gen_cols(inst, Ebase, b, cur, CAP=22, NT=4, PSTEP=3):
    """columns = (orient,x,y,entry,exit) self-feasible vs fixed base; multiple entry
    times so the CP can reorder. Current placement included first."""
    B=inst["blocks"]; bays=inst["bays"]; pt=B[b]["processing_time"]
    rlo=B[b]["release_time"]; rhi=max(rlo, B[b]["due_date"]-pt)
    cols=[dict(cur)]
    ts=sorted(set([rlo]+[int(rlo+(rhi-rlo)*k/max(1,NT-1)) for k in range(NT)]+[cur["entry_time"]]))
    for en in ts:
        ex=en+pt
        for bay in range(len(bays)):
            W=bays[bay]["width"]; H=bays[bay]["height"]
            for oi in range(len(B[b]["shape"])):
                x0,y0,x1,y1=bbox(B,b,oi)
                if (x1-x0)>W or (y1-y0)>H: continue
                for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1,PSTEP):
                    for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1,PSTEP):
                        if Ebase.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex):
                            cols.append({"block_id":b,"bay_id":bay,"x":ix,"y":iy,
                                "orient_idx":oi,"entry_time":en,"exit_time":ex})
                            if len(cols)>=CAP: return cols
    return cols

def conflict(E, ca, cb):
    # crane descent is pairwise-decomposable (blocked iff it hits SOME present block),
    # so this is an EXACT 2-block check. clear_all first -> no state pollution.
    if ca["bay_id"]!=cb["bay_id"]: return False
    if not (ca["entry_time"]<cb["exit_time"] and cb["entry_time"]<ca["exit_time"]): return False
    early,late=(ca,cb) if ca["entry_time"]<=cb["entry_time"] else (cb,ca)
    bay=int(early["bay_id"])
    E.clear_all()
    try: E.add(bay,int(early["block_id"]),int(early["orient_idx"]),float(early["x"]),float(early["y"]),int(early["entry_time"]),int(early["exit_time"]))
    except Exception: return True
    ok=E.placement_feasible(bay,int(late["block_id"]),int(late["orient_idx"]),float(late["x"]),float(late["y"]),int(late["entry_time"]),int(late["exit_time"]))
    return not ok

def main():
    from ortools.sat.python import cp_model
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_28.json"
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
    sol=M.algorithm(inst,60); assign=reconstruct(inst,sol)
    ck0=check_feasibility(inst, M._build_operations([assign[b] for b in sorted(assign)]))
    print(f"{os.path.basename(path)}: base obj={ck0['objective']:.0f} Z1={ck0['obj1']:.0f}",flush=True)
    # busiest bay, window = time with most tardy co-active blocks
    by_bay={}
    for b,a in assign.items(): by_bay.setdefault(a["bay_id"],[]).append(b)
    bayj=max(by_bay,key=lambda j:len(by_bay[j])); mem=by_bay[bayj]
    def tardy_at(t): return [b for b in mem if assign[b]["entry_time"]<=t<assign[b]["exit_time"] and tard(B,assign[b])>0]
    times=sorted({assign[b]["entry_time"] for b in mem})
    T=max(times,key=lambda t:len(tardy_at(t)))
    # window = co-active blocks around T in this bay, most-tardy first, cap 14
    ex_win=T+ max(1, int(np.median([B[b]["processing_time"] for b in mem])))
    W=[b for b in mem if assign[b]["entry_time"]<ex_win and assign[b]["exit_time"]>T]
    W=sorted(W, key=lambda b:-tard(B,assign[b]))[:14]
    wt0=sum(tard(B,assign[b]) for b in W)
    print(f" bay={bayj} window T={T} |W|={len(W)} window-tardiness={wt0}",flush=True)
    # base engine = everything except W
    E=M._ogc_fast_engine(inst); E.clear_all()
    for b,a in assign.items():
        if b in W: continue
        try: E.add(int(a["bay_id"]),b,int(a["orient_idx"]),float(a["x"]),float(a["y"]),int(a["entry_time"]),int(a["exit_time"]))
        except Exception: pass
    colmap={b:gen_cols(inst,E,b,assign[b]) for b in W}
    for b in W:
        print(f"   block {b} tard={tard(B,assign[b])} cols={len(colmap[b])}",flush=True)
    # CP-SAT
    mdl=cp_model.CpModel(); z={}
    for b in W:
        for ci in range(len(colmap[b])): z[(b,ci)]=mdl.NewBoolVar(f"z{b}_{ci}")
        mdl.Add(sum(z[(b,ci)] for ci in range(len(colmap[b])))==1)
    for ii in range(len(W)):
        for jj in range(ii+1,len(W)):
            b1,b2=W[ii],W[jj]
            for c1i,c1 in enumerate(colmap[b1]):
                for c2i,c2 in enumerate(colmap[b2]):
                    if conflict(E,c1,c2): mdl.Add(z[(b1,c1i)]+z[(b2,c2i)]<=1)
    mdl.Minimize(sum(z[(b,ci)]*int(tard(B,colmap[b][ci])) for b in W for ci in range(len(colmap[b]))))
    sv=cp_model.CpSolver(); sv.parameters.max_time_in_seconds=15.0; sv.parameters.num_search_workers=4
    st=sv.Solve(mdl)
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        newg={}
        for b in W:
            for ci in range(len(colmap[b])):
                if sv.Value(z[(b,ci)]): newg[b]=colmap[b][ci]; break
        wt1=sum(tard(B,newg[b]) for b in W)
        trial=copy.deepcopy(assign)
        for b in W: trial[b]=newg[b]
        ck=check_feasibility(inst, M._build_operations([trial[b] for b in sorted(trial)]))
        print(f" CP window-tardiness {wt0} -> {wt1} | realized feasible={ck['feasible']} "
              f"obj {ck0['objective']:.0f} -> {ck['objective']:.0f} Z1 {ck0['obj1']:.0f}->{ck['obj1']:.0f} "
              f"status={sv.StatusName(st)}",flush=True)
    else:
        print(f" CP no solution ({sv.StatusName(st)})",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
