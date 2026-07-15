"""
Crane-aware SCOPED window reschedule POC (option A, tractable form).
For each tardy block, take {block} + its top-K spatial blockers in the same bay,
fix everything else as obstacles, enumerate bounded columns (incl. current), compute
EXACT pairwise crane conflicts via the engine (add/remove), and solve a set-packing
CP-SAT minimizing the set's total tardiness. Current columns are always included so
the result is never-worse. Measure realized objective before/after.
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

def gen_columns(inst, E_base, b, bays, curcol, CAP=16, TSTEPS=4, PSTEP=4):
    """self-feasible columns vs the fixed base. Always include curcol first."""
    B=inst["blocks"]; pt=B[b]["processing_time"]; rlo=B[b]["release_time"]; rhi=B[b]["due_date"]-pt
    cols=[curcol]
    if rhi<rlo: rhi=rlo
    ts=sorted(set(int(rlo+ (rhi-rlo)*k//max(1,TSTEPS-1)) for k in range(TSTEPS)))
    for en in ts:
        ex=en+pt
        for bay in range(len(bays)):
            W=bays[bay]["width"]; H=bays[bay]["height"]
            for oi in range(len(B[b]["shape"])):
                x0,y0,x1,y1=bbox(B,b,oi)
                if (x1-x0)>W or (y1-y0)>H: continue
                for ix in range(int(np.ceil(-x0)),int(np.floor(W-x1))+1,PSTEP):
                    for iy in range(int(np.ceil(-y0)),int(np.floor(H-y1))+1,PSTEP):
                        if E_base.placement_feasible(bay,b,oi,float(ix),float(iy),en,ex):
                            cols.append({"block_id":b,"bay_id":bay,"x":ix,"y":iy,
                                         "orient_idx":oi,"entry_time":en,"exit_time":ex})
                            if len(cols)>=CAP: return cols
    return cols

def tard(inst,col):
    return max(0, col["exit_time"]-inst["blocks"][col["block_id"]]["due_date"])

def conflict(E_base, ca, cb):
    """exact pairwise crane conflict with base fixed. add/remove on E_base."""
    if ca["bay_id"]!=cb["bay_id"]: return False
    if not (ca["entry_time"]<cb["exit_time"] and cb["entry_time"]<ca["exit_time"]): return False
    # later-entering descends past earlier
    early,late = (ca,cb) if ca["entry_time"]<=cb["entry_time"] else (cb,ca)
    bay=int(early["bay_id"])
    try:
        E_base.add(bay,int(early["block_id"]),int(early["orient_idx"]),float(early["x"]),
                   float(early["y"]),int(early["entry_time"]),int(early["exit_time"]))
    except Exception:
        return True
    ok=E_base.placement_feasible(bay,int(late["block_id"]),int(late["orient_idx"]),
                                 float(late["x"]),float(late["y"]),int(late["entry_time"]),int(late["exit_time"]))
    try: E_base.remove(bay,int(early["block_id"]))
    except Exception: pass
    return not ok

def main():
    from ortools.sat.python import cp_model
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_28.json"
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]
    sol=M.algorithm(inst,60); assign=reconstruct(inst,sol)
    ck0=check_feasibility(inst,M._build_operations([assign[b] for b in sorted(assign)]))
    print(f"{os.path.basename(path)}: baseline obj={ck0['objective']:.0f} Z1={ck0['obj1']:.0f}",flush=True)
    deadline=time.time()+40
    tardy=sorted([b for b in assign if tard(inst,assign[b])>0], key=lambda b:-tard(inst,assign[b]))
    total_moves=0
    for tb in tardy:
        if time.time()>deadline: break
        p=assign[tb]; bay=p["bay_id"]
        # blockers: same-bay blocks overlapping tb's interval, nearest in x
        overl=[b for b in assign if b!=tb and assign[b]["bay_id"]==bay
               and assign[b]["entry_time"]<p["exit_time"] and assign[b]["exit_time"]>p["entry_time"]]
        overl.sort(key=lambda b:abs(assign[b]["x"]-p["x"]))
        K=6; grp=[tb]+overl[:K]
        # base engine = all blocks NOT in grp
        E=M._ogc_fast_engine(inst); E.clear_all()
        for b,a in assign.items():
            if b in grp: continue
            try: E.add(int(a["bay_id"]),b,int(a["orient_idx"]),float(a["x"]),float(a["y"]),
                       int(a["entry_time"]),int(a["exit_time"]))
            except Exception: pass
        # columns
        colmap={b:gen_columns(inst,E,b,bays,assign[b]) for b in grp}
        # conflicts
        mdl=cp_model.CpModel(); z={}
        for b in grp:
            for ci,c in enumerate(colmap[b]): z[(b,ci)]=mdl.NewBoolVar(f"z{b}_{ci}")
            mdl.Add(sum(z[(b,ci)] for ci in range(len(colmap[b])))==1)
        gl=list(grp)
        for ii in range(len(gl)):
            for jj in range(ii+1,len(gl)):
                b1,b2=gl[ii],gl[jj]
                for c1i,c1 in enumerate(colmap[b1]):
                    for c2i,c2 in enumerate(colmap[b2]):
                        if conflict(E,c1,c2):
                            mdl.Add(z[(b1,c1i)]+z[(b2,c2i)]<=1)
        # objective: minimize group tardiness (+ tiny position stability tiebreak)
        mdl.Minimize(sum(z[(b,ci)]*int(tard(inst,colmap[b][ci])) for b in grp for ci in range(len(colmap[b]))))
        sv=cp_model.CpSolver(); sv.parameters.max_time_in_seconds=3.0; sv.parameters.num_search_workers=4
        st=sv.Solve(mdl)
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            newg={}
            for b in grp:
                for ci in range(len(colmap[b])):
                    if sv.Value(z[(b,ci)]): newg[b]=colmap[b][ci]; break
            trial=copy.deepcopy(assign)
            for b in grp: trial[b]=newg[b]
            ck=check_feasibility(inst,M._build_operations([trial[b] for b in sorted(trial)]))
            if ck["feasible"] and ck["objective"]<ck0["objective"]-1e-9:
                assign=trial; total_moves+=1
                gain=ck0["objective"]-ck["objective"]; ck0=ck
                print(f"  block {tb}: improved obj to {ck['objective']:.0f} (Z1={ck['obj1']:.0f}) gain={gain:.0f}",flush=True)
    ckf=check_feasibility(inst,M._build_operations([assign[b] for b in sorted(assign)]))
    print(f"FINAL obj={ckf['objective']:.0f} Z1={ckf['obj1']:.0f} groups_improved={total_moves}",flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
