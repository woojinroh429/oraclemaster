"""Step 3c: ORDER-DEPENDENT joint descent-scheduling CP-SAT, using cranepack/fastconf's
VALIDATED conflict (0-mismatch vs grader) instead of the order-INDEPENDENT union in
step3_cpsat.py.  That union over-forbids (it bans co-presence if the pair conflicts in
EITHER entry order), which excludes the current-valid solution -> CP-SAT 'OPT' worse than
CURRENT.  Here each conflicting candidate pair gets TWO precomputed flags:
  fAfirst = infeasible if A enters no-later than B (overlapping)
  fBfirst = infeasible if B enters no-later than A
and only the forbidden order is made sequential.  => never-worse than CURRENT, and frees
the asymmetric-conflict co-presence the union wrongly banned.  Compare within-window tard.
"""
import sys, os, json, math, time
sys.path.insert(0, ".")
_SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(_SP, "research"))
sys.path.insert(0, os.path.join(_SP, "cc"))
import numpy as np
import myalgorithm as M
from myalgorithm import _orient_bbox, _ogc_fast_engine
from utils import Block, Bay, check_entry, check_feasibility
import fastconf as FC
from ortools.sat.python import cp_model

CAP = int(os.environ.get("CAP", "12"))
GRID = int(os.environ.get("GRID", "4"))
MAXCAND = int(os.environ.get("MAXCAND", "10"))

def build_solution_placement(inst, sol):
    B = inst["blocks"]; pt = [b["processing_time"] for b in B]
    place = {}
    for tk, lst in sol["operations"].items():
        for op in lst:
            if op.get("type") == "ENTRY":
                place[op["block_id"]] = dict(bay=op["bay_id"], x=op["x"], y=op["y"],
                                             oi=op["orient_idx"], en=int(tk), ex=int(tk)+pt[op["block_id"]])
    return place

def pick_window(inst, place):
    B = inst["blocks"]; rel = [b["release_time"] for b in B]; m = len(inst["bays"])
    waiters = [b for b in place if place[b]["en"] > rel[b]]
    best = None
    for bay in range(m):
        for t in sorted({rel[b] for b in waiters if place[b]["bay"] == bay}):
            wl = [b for b in waiters if place[b]["bay"] == bay and rel[b] <= t < place[b]["en"]]
            if best is None or len(wl) > len(best[2]): best = (bay, t, wl)
    return best

_lp={}
def layers_arr_poly(inst,bid,x,y,o):
    return FC.layers_arr_poly(inst,bid,x,y,o)

def main(pnum, tl):
    _p=f"{_SP}/data/train/prob_{pnum}.json"
    inst = json.load(open(_p))
    B = inst["blocks"]; bays = inst["bays"]
    rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
    sol = M.algorithm(inst, tl); check_feasibility(inst, sol)
    place = build_solution_placement(inst, sol)
    win = pick_window(inst, place)
    if not win: print("no window"); return
    bay, t0, waiters = win
    bayd=bays[bay]; bw=bayd["width"]; bh=bayd["height"]; bayobj=Bay.from_dict(bayd,bay)
    waiters = sorted(waiters, key=lambda b:-(place[b]["en"]-rel[b]))[:CAP]

    if os.environ.get("FREEBAND"):
        band=int(os.environ["FREEBAND"])
        coupled=[b for b in place if place[b]["bay"]==bay and place[b]["en"]<t0+band and place[b]["ex"]>t0-band]
        coupled=sorted(coupled,key=lambda b:-(place[b]["en"]-rel[b]))[:int(os.environ.get("MAXSET","18"))]
    else:
        coupled=list(waiters)
    cset=set(coupled)
    cur_tard=sum(max(0,place[b]["ex"]-due[b]) for b in coupled)

    E=_ogc_fast_engine(inst); E.clear_all()
    for b in place:
        if b in cset: continue
        try: E.add(int(place[b]["bay"]),b,int(place[b]["oi"]),float(place[b]["x"]),float(place[b]["y"]),int(place[b]["en"]),int(place[b]["ex"]))
        except Exception: pass

    Hcap=int(max(due)+max(pt)+5)
    cand={}
    for b in coupled:
        opts=[]; cur=(place[b]["oi"],place[b]["x"],place[b]["y"]); grid=[]
        for oi in range(len(B[b]["shape"])):
            x0,y0,x1,y1=_orient_bbox(B[b],oi)
            if x1-x0>bw+1e-9 or y1-y0>bh+1e-9: continue
            for ix in range(math.ceil(-x0),math.floor(bw-x1)+1,GRID):
                for iy in range(math.ceil(-y0),math.floor(bh-y1)+1,GRID): grid.append((oi,ix,iy))
        if len(grid)>MAXCAND*3:
            stride=max(1,len(grid)//(MAXCAND*3)); grid=grid[::stride]
        seen=set()
        for (oi,x,y) in [cur]+grid:
            if (oi,x,y) in seen: continue
            seen.add((oi,x,y))
            blk=Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=oi)
            if not bayobj.contains_block(blk): continue
            e=rel[b]; found=None; scan=0
            while e<=Hcap and scan<400:
                scan+=1
                if E.placement_feasible(bay,b,oi,float(x),float(y),int(e),int(e+pt[b])): found=e; break
                e+=1
            if found is not None: opts.append((oi,x,y,found))
            if len(opts)>=MAXCAND: break
        if not opts: opts=[(place[b]["oi"],place[b]["x"],place[b]["y"],place[b]["en"])]
        # ensure current placement present as a candidate (feasible against backdrop at its entry)
        if not any((o,x,y)==cur for (o,x,y,_e) in opts):
            opts.append((cur[0],cur[1],cur[2],place[b]["en"]))
        cand[b]=opts

    # ORDER-DEPENDENT conflict via fastconf: fAfirst / fBfirst per candidate pair
    LP={}
    def lp(b,pi):
        k=(b,pi[0],pi[1],pi[2])
        if k not in LP: LP[k]=layers_arr_poly(inst,b,pi[1],pi[2],pi[0])
        return LP[k]
    def forbids(bi,pi,bj,pj):
        Aa,Ap=lp(bi,pi); Ba,Bp=lp(bj,pj)
        pa=pt[bi]; pb=pt[bj]
        # A no-later than B: eA=0, eB=0 (co-present, A rests, B descends). Use eA<=eB via eB=0,eA=0
        fAfirst=FC.conflict(Aa,Ap,0,pa, Ba,Bp,0,pb)          # symmetric co-present at equal entry
        # to separate orders, also test staggered so exit order is A-first vs B-first
        fA=FC.conflict(Aa,Ap,0,pa, Ba,Bp,1,1+pb)             # A strictly first
        fB=FC.conflict(Aa,Ap,1,1+pa, Ba,Bp,0,pb)             # B strictly first
        return (fAfirst or fA), (fAfirst or fB)

    mdl=cp_model.CpModel(); sel={}; entry={}
    for b in coupled:
        ks=[mdl.NewBoolVar(f"s{b}_{i}") for i in range(len(cand[b]))]; sel[b]=ks; mdl.AddExactlyOne(ks)
        e=mdl.NewIntVar(rel[b],Hcap,f"e{b}"); entry[b]=e
        for i,(oi,x,y,emin) in enumerate(cand[b]): mdl.Add(e>=emin).OnlyEnforceIf(ks[i])
    cl=list(coupled); npair=0
    for ii in range(len(cl)):
        for jj in range(ii+1,len(cl)):
            bi=cl[ii]; bj=cl[jj]
            for pi_i,pi in enumerate(cand[bi]):
                for pj_i,pj in enumerate(cand[bj]):
                    fAf,fBf=forbids(bi,pi,bj,pj)
                    if not (fAf or fBf): continue
                    both=mdl.NewBoolVar(f"c{bi}_{pi_i}_{bj}_{pj_i}")
                    mdl.AddBoolAnd([sel[bi][pi_i],sel[bj][pj_i]]).OnlyEnforceIf(both)
                    mdl.AddBoolOr([sel[bi][pi_i].Not(),sel[bj][pj_i].Not()]).OnlyEnforceIf(both.Not())
                    oAB=mdl.NewBoolVar(f"o{bi}_{bj}_{pi_i}_{pj_i}")  # A enters <= B
                    mdl.Add(entry[bi]<=entry[bj]).OnlyEnforceIf([both,oAB])
                    mdl.Add(entry[bj]<=entry[bi]).OnlyEnforceIf([both,oAB.Not()])
                    if fAf: mdl.Add(entry[bj]>=entry[bi]+pt[bi]).OnlyEnforceIf([both,oAB])   # A first forbidden -> sequential
                    if fBf: mdl.Add(entry[bi]>=entry[bj]+pt[bj]).OnlyEnforceIf([both,oAB.Not()])
                    npair+=1
    tard=[]
    for b in coupled:
        tv=mdl.NewIntVar(0,Hcap,f"t{b}"); mdl.Add(tv>=entry[b]+pt[b]-due[b]); tard.append(tv)
    mdl.Minimize(sum(tard))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=float(os.environ.get("CPTL","20")); solver.parameters.num_search_workers=4
    ts=time.time(); st=solver.Solve(mdl); dt=time.time()-ts
    stn={cp_model.OPTIMAL:"OPT",cp_model.FEASIBLE:"FEAS"}.get(st,"NONE")
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        nt=int(solver.ObjectiveValue()); moved=sum(1 for b in coupled if int(solver.Value(entry[b]))!=place[b]["en"] or (cand[b][next(i for i in range(len(cand[b])) if solver.Value(sel[b][i])==1)][:3]!=(place[b]["oi"],place[b]["x"],place[b]["y"])))
        print(f"prob_{pnum} bay{bay}@t{t0} coupled={len(coupled)} pairs={npair} cands~{sum(len(cand[b]) for b in coupled)//max(1,len(coupled))}/blk")
        print(f"  within-window tardiness  CURRENT={cur_tard}  CP-SAT={nt}  delta={cur_tard-nt} ({stn}, {dt:.1f}s)  moved={moved}/{len(coupled)}")
    else:
        print(f"prob_{pnum}: CP-SAT {stn} coupled={len(coupled)}")

if __name__=="__main__":
    tl=float(os.environ.get("TL","25"))
    for p in sys.argv[1:]:
        try: main(int(p),tl)
        except Exception as e:
            import traceback; print(f"prob_{p} ERR {e}"); traceback.print_exc()
