"""Step 4: CORRECT order-dependent joint descent-scheduling (min weighted tardiness).
Fixes step3's over-forbidding union by decomposing each candidate pair's crane geometry
into R / DA / DB (fastconf.relation3) and activating them by the TRUE crane timing rule:
  forbidden(co-present) = R  OR  (later-entrant sweeps: eA<=eB?DB:DA)  OR
                                  (earlier-exiter sweeps: exitA<=exitB?DA:DB)
=> allowed overlap regimes:
   R or (DA and DB): sequential only
   only DA:          A-contains-B allowed (eA<=eB and exitB<=exitA)
   only DB:          B-contains-A allowed (eB<=eA and exitA<=exitB)
The CURRENT solution is representable -> CP-SAT is NEVER worse than CURRENT, and it frees
the containment co-presence the union wrongly banned (=> throughput -> earlier entries).
"""
import sys, os, json, math, time
sys.path.insert(0, ".")
_SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(_SP,"research")); sys.path.insert(0, os.path.join(_SP,"cc"))
import numpy as np, myalgorithm as M
from myalgorithm import _orient_bbox, _ogc_fast_engine
from utils import Block, Bay, check_feasibility
import fastconf as FC
from ortools.sat.python import cp_model
from collections import defaultdict

CAP=int(os.environ.get("CAP","14")); GRID=int(os.environ.get("GRID","4")); MAXCAND=int(os.environ.get("MAXCAND","8"))

def build_place(inst, sol):
    B=inst["blocks"]; pt=[b["processing_time"] for b in B]; place={}
    for tk,lst in sol["operations"].items():
        for op in lst:
            if op.get("type")=="ENTRY":
                place[op["block_id"]]=dict(bay=op["bay_id"],x=op["x"],y=op["y"],oi=op["orient_idx"],en=int(tk),ex=int(tk)+pt[op["block_id"]])
    return place

def pick_window(inst, place):
    B=inst["blocks"]; rel=[b["release_time"] for b in B]; m=len(inst["bays"])
    waiters=[b for b in place if place[b]["en"]>rel[b]]; best=None
    for bay in range(m):
        for t in sorted({rel[b] for b in waiters if place[b]["bay"]==bay}):
            wl=[b for b in waiters if place[b]["bay"]==bay and rel[b]<=t<place[b]["en"]]
            if best is None or len(wl)>len(best[2]): best=(bay,t,wl)
    return best

def main(pnum, tl):
    inst=json.load(open(f"{_SP}/data/train/prob_{pnum}.json"))
    B=inst["blocks"]; bays=inst["bays"]; rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]; due=[b["due_date"] for b in B]
    w1=int(inst["weights"]["w1"])
    sol=M.algorithm(inst,tl); check_feasibility(inst,sol); place=build_place(inst,sol)
    win=pick_window(inst,place)
    if not win: print("no window"); return
    bay,t0,waiters=win; bayd=bays[bay]; bw=bayd["width"]; bh=bayd["height"]; bayobj=Bay.from_dict(bayd,bay)
    waiters=sorted(waiters,key=lambda b:-(place[b]["en"]-rel[b]))[:CAP]
    if os.environ.get("FREEBAND"):
        band=int(os.environ["FREEBAND"])
        coupled=[b for b in place if place[b]["bay"]==bay and place[b]["en"]<t0+band and place[b]["ex"]>t0-band]
        coupled=sorted(coupled,key=lambda b:-(place[b]["en"]-rel[b]))[:int(os.environ.get("MAXSET","16"))]
    else: coupled=list(waiters)
    cset=set(coupled); cur_tard=sum(w1*max(0,place[b]["ex"]-due[b]) for b in coupled)

    E=_ogc_fast_engine(inst); E.clear_all()
    for b in place:
        if b in cset: continue
        try: E.add(int(place[b]["bay"]),b,int(place[b]["oi"]),float(place[b]["x"]),float(place[b]["y"]),int(place[b]["en"]),int(place[b]["ex"]))
        except Exception: pass

    Hcap=int(max(due)+max(pt)+5); cand={}
    for b in coupled:
        opts=[]; cur=(place[b]["oi"],place[b]["x"],place[b]["y"]); grid=[]
        for oi in range(len(B[b]["shape"])):
            x0,y0,x1,y1=_orient_bbox(B[b],oi)
            if x1-x0>bw+1e-9 or y1-y0>bh+1e-9: continue
            for ix in range(math.ceil(-x0),math.floor(bw-x1)+1,GRID):
                for iy in range(math.ceil(-y0),math.floor(bh-y1)+1,GRID): grid.append((oi,ix,iy))
        if len(grid)>MAXCAND*3:
            st=max(1,len(grid)//(MAXCAND*3)); grid=grid[::st]
        seen=set()
        for (oi,x,y) in [cur]+grid:
            if (oi,x,y) in seen: continue
            seen.add((oi,x,y)); blk=Block(block_id=b,block_data=B[b],x=x,y=y,orient_idx=oi)
            if not bayobj.contains_block(blk): continue
            e=rel[b]; found=None; sc=0
            while e<=Hcap and sc<400:
                sc+=1
                if E.placement_feasible(bay,b,oi,float(x),float(y),int(e),int(e+pt[b])): found=e; break
                e+=1
            if found is not None: opts.append((oi,x,y,found))
            if len(opts)>=MAXCAND: break
        if not any((o,x,y)==cur for (o,x,y,_e) in opts): opts.append((cur[0],cur[1],cur[2],place[b]["en"]))
        cand[b]=opts

    LP={}
    def lp(b,pi):
        k=(b,pi[0],pi[1],pi[2])
        if k not in LP: LP[k]=FC.layers_arr_poly(inst,b,pi[1],pi[2],pi[0])
        return LP[k]

    mdl=cp_model.CpModel(); sel={}; entry={}
    for b in coupled:
        ks=[mdl.NewBoolVar(f"s{b}_{i}") for i in range(len(cand[b]))]; sel[b]=ks; mdl.AddExactlyOne(ks)
        entry[b]=mdl.NewIntVar(rel[b],Hcap,f"e{b}")
        for i,(oi,x,y,emin) in enumerate(cand[b]): mdl.Add(entry[b]>=emin).OnlyEnforceIf(ks[i])

    cl=list(coupled); npair=0; nfree=0
    # per block-pair timing bools (shared across their placement pairs)
    for ii in range(len(cl)):
        for jj in range(ii+1,len(cl)):
            A=cl[ii]; Bb=cl[jj]; eA=entry[A]; eB=entry[Bb]; pA=pt[A]; pB=pt[Bb]
            abf=None; bbf=None; acon=None; bcon=None
            def mk_abf():
                v=mdl.NewBoolVar(f"abf{A}_{Bb}"); mdl.Add(eA+pA<=eB).OnlyEnforceIf(v); return v
            def mk_bbf():
                v=mdl.NewBoolVar(f"bbf{A}_{Bb}"); mdl.Add(eB+pB<=eA).OnlyEnforceIf(v); return v
            def mk_acon():
                v=mdl.NewBoolVar(f"acon{A}_{Bb}"); mdl.Add(eA<=eB).OnlyEnforceIf(v); mdl.Add(eB+pB<=eA+pA).OnlyEnforceIf(v); return v
            def mk_bcon():
                v=mdl.NewBoolVar(f"bcon{A}_{Bb}"); mdl.Add(eB<=eA).OnlyEnforceIf(v); mdl.Add(eA+pA<=eB+pB).OnlyEnforceIf(v); return v
            for pi_i,pi in enumerate(cand[A]):
                Aa,Ap=lp(A,pi)
                for pj_i,pj in enumerate(cand[Bb]):
                    Ba,Bp=lp(Bb,pj)
                    R,DA,DB=FC.relation3(Aa,Ap,Ba,Bp)
                    if not (R or DA or DB): nfree+=1; continue
                    both=mdl.NewBoolVar(f"b{A}_{pi_i}_{Bb}_{pj_i}")
                    mdl.AddBoolAnd([sel[A][pi_i],sel[Bb][pj_i]]).OnlyEnforceIf(both)
                    mdl.AddBoolOr([sel[A][pi_i].Not(),sel[Bb][pj_i].Not()]).OnlyEnforceIf(both.Not())
                    if abf is None: abf=mk_abf(); bbf=mk_bbf()
                    allowed=[abf,bbf]
                    if R or (DA and DB): pass
                    elif DA:                       # only DA -> A contains B allowed
                        if acon is None: acon=mk_acon()
                        allowed=[abf,bbf,acon]
                    elif DB:                       # only DB -> B contains A allowed
                        if bcon is None: bcon=mk_bcon()
                        allowed=[abf,bbf,bcon]
                    mdl.AddBoolOr(allowed).OnlyEnforceIf(both); npair+=1

    tard=[]
    for b in coupled:
        tv=mdl.NewIntVar(0,Hcap,f"t{b}"); mdl.Add(tv>=entry[b]+pt[b]-due[b]); tard.append(w1*tv)
    mdl.Minimize(sum(tard))
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=float(os.environ.get("CPTL","25")); solver.parameters.num_search_workers=4
    ts=time.time(); stt=solver.Solve(mdl); dt=time.time()-ts
    stn={cp_model.OPTIMAL:"OPT",cp_model.FEASIBLE:"FEAS"}.get(stt,"NONE")
    if stt in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        nt=int(solver.ObjectiveValue()); moved=sum(1 for b in coupled if int(solver.Value(entry[b]))!=place[b]["en"])
        print(f"prob_{pnum} bay{bay}@t{t0} coupled={len(coupled)} pairs(conf={npair} free={nfree}) cands~{sum(len(cand[b]) for b in coupled)//max(1,len(coupled))}/blk")
        print(f"  within-window WEIGHTED-tard  CURRENT={cur_tard}  CP-SAT={nt}  delta={cur_tard-nt} ({stn},{dt:.1f}s) moved={moved}/{len(coupled)}")
    else:
        print(f"prob_{pnum}: {stn} coupled={len(coupled)}")

if __name__=="__main__":
    tl=float(os.environ.get("TL","20"))
    for p in sys.argv[1:]:
        try: main(int(p),tl)
        except Exception as e:
            import traceback; print(f"prob_{p} ERR {e}"); traceback.print_exc()
