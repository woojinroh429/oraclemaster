"""cranepack-powered Z3 relocator + A/B vs the shipped _z3_relocate.

Mirrors _z3_relocate's loop (move a preference-violating block into a more-preferred
bay by freeing time-neighbours and repacking F+b), but the repack uses the C++
cranepack set-packing (full grid, frozen obstacles, 100x faster) instead of the
COLCAP=20 CP-SAT.  Same exact-objective never-worse gate.  Measures the REAL grader
objective (check_feasibility) from an identical starting assignment."""
import json, os, sys, time, math
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v71")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v71"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

def orient_layers(B,bid,o):
    blk=M.Block(block_id=bid, block_data=B[bid], x=0, y=0, orient_idx=o)
    return [np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in blk.layers_at_pos()]

def world_layers(B,bid,o,x,y):
    blk=M.Block(block_id=bid, block_data=B[bid], x=x, y=y, orient_idx=o)
    return [np.ascontiguousarray(np.asarray(L,dtype=np.float64)) for L in blk.layers_at_pos()]

def z3_relocate_cp(prob_info, assign, bay_unit, deadline, FREE=10, STEP=6, TLpack=0.25, seed=12345):
    """cranepack version of _z3_relocate. Returns updated assign (never-worse-gated)."""
    B=prob_info["blocks"]; n=len(B); bays=prob_info["bays"]; m=len(bays)
    if n==0 or m<2: return assign
    w=prob_info["weights"]; w2=w["w2"]; w3=w["w3"]
    rel=[B[b]["release_time"] for b in range(n)]
    pt=[B[b]["processing_time"] for b in range(n)]
    due=[B[b]["due_date"] for b in range(n)]
    mxp=[max(B[b]["bay_preferences"]) for b in range(n)]
    bu=bay_unit
    # place[b] = [bay, oi, x, y, en, ex]
    place={}
    for b,a in assign.items():
        place[b]=[a["bay_id"],a["orient_idx"],a["x"],a["y"],int(a["entry_time"]),int(a["exit_time"])]

    # precompute per-block orient layers-at-origin + obb (candidates use entry=release)
    olcache={}; obbcache={}
    def ols(bid):
        if bid not in olcache:
            olcache[bid]=[orient_layers(B,bid,o) for o in range(len(B[bid]["shape"]))]
            obbcache[bid]=[tuple(float(v) for v in M._orient_bbox(B[bid],o)) for o in range(len(B[bid]["shape"]))]
        return olcache[bid],obbcache[bid]

    def ent_cands(b):
        lo=rel[b]; hi=due[b]-pt[b]
        if hi<=lo: return [lo] if (lo>=0 and lo+pt[b]<=due[b]) else []
        cs=sorted(set(lo+((hi-lo)*k)//2 for k in range(3)))
        return [t for t in cs if t>=0 and t+pt[b]<=due[b]]

    def try_insert(b,J):
        if time.time()>deadline-1.0: return None
        W=bays[J]["width"]; H=bays[J]["height"]
        inbay=[x for x in place if x!=b and place[x][0]==J]
        Fall=[x for x in inbay if not (place[x][5]<=rel[b] or due[b]<=place[x][4])]
        Fall.sort(key=lambda x: abs(place[x][4]-rel[b]))
        F=Fall[:FREE]
        Fset=set(F)
        frozen_blocks=[x for x in inbay if x not in Fset]
        cands=F+[b]
        blocks_in=[]
        for g in cands:
            ee=[(en,en+pt[g]) for en in ent_cands(g)]
            if not ee: return None            # cannot place g without tardiness
            ol,ob=ols(g); blocks_in.append((ol,ob,ee))
        froz=[]
        for x in frozen_blocks:
            bay,oi,fx,fy,fen,fex=place[x]
            froz.append((world_layers(B,x,oi,fx,fy),int(fen),int(fex)))
        best,pl,ncol,nedge,bms,sms,_cd,_ed,_wc=CP.pack(
            blocks_in,float(W),float(H),STEP,TLpack,seed=seed,warm=None,frozen=froz)
        if best<len(cands): return None   # could not place ALL of F+b
        newsel={}
        for (loc,o,x,y,en,ex) in pl:
            g=cands[loc]; newsel[g]=[J,o,x,y,int(en),int(ex)]
        return newsel

    def cur_obj():
        load=[0.0]*m; z3=0.0
        for b in place:
            j=place[b][0]; load[j]+=B[b]["workload"]; z3+=mxp[b]-B[b]["bay_preferences"][j]
        vals=[bu[j]*load[j] for j in range(m)]
        return w2*math.floor(max(vals)-min(vals))+w3*z3

    base=cur_obj()
    for _pass in range(6):
        if time.time()>deadline-0.5: break
        cands=sorted([b for b in place if mxp[b]-B[b]["bay_preferences"][place[b][0]]>0],
                     key=lambda b:-(mxp[b]-B[b]["bay_preferences"][place[b][0]]))
        moved=0
        for b in cands:
            if time.time()>deadline-0.5: break
            j=place[b][0]; prefs=B[b]["bay_preferences"]
            targets=sorted([jt for jt in range(m) if prefs[jt]>prefs[j]],key=lambda jt:-prefs[jt])
            for jt in targets:
                newsel=try_insert(b,jt)
                if newsel is None: continue
                old={g:list(place[g]) for g in newsel}
                for g,c in newsel.items(): place[g]=c
                no=cur_obj()
                if no<base-1e-6: base=no; moved+=1; break
                else:
                    for g in old: place[g]=old[g]
        if moved==0: break
    return {b:{"block_id":b,"bay_id":place[b][0],"orient_idx":place[b][1],
               "x":place[b][2],"y":place[b][3],"entry_time":place[b][4],
               "exit_time":place[b][5]} for b in place}

# ---------------- A/B harness ----------------
if __name__=="__main__":
    NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
    SEEDT=float(sys.argv[2]) if len(sys.argv)>2 else 15.0   # exact_reassign seed budget
    RELT=float(sys.argv[3]) if len(sys.argv)>3 else 15.0    # relocate budget each
    FREE=int(sys.argv[4]) if len(sys.argv)>4 else 10
    inst=json.load(open(find(NAME))); prob_info=inst
    bay_unit=M._bay_unit_weights(inst["bays"])
    def score(a):
        sol=M._build_operations(list(a.values()))
        ck=check_feasibility(inst,sol)
        return ck["objective"] if ck["feasible"] else float("inf"), ck["feasible"]
    # starting assignment via exact_reassign -- CACHED so old vs new see identical start
    import pickle
    cache=os.path.join(SP,"research",f"_seed_{NAME}.pkl")
    t0=time.time()
    if os.path.exists(cache):
        best_a=pickle.load(open(cache,"rb"))
        print(f"{NAME}: loaded cached seed assign")
    else:
        res=M._exact_reassign(prob_info,bay_unit,time.time()+SEEDT,mip_cap=6.0,mode="feedback")
        if not (res and res[0]):
            print("no seed assignment"); sys.exit(1)
        best_a={b:dict(v) for b,v in res[0].items()}
        pickle.dump(best_a,open(cache,"wb"))
    o0,f0=score(best_a)
    print(f"{NAME}: seed assign obj={o0:.0f} feas={f0}  [{time.time()-t0:.1f}s]")

    # OLD relocate
    import copy
    a_old=copy.deepcopy(best_a)
    t=time.time()
    a_old=M._z3_relocate(prob_info,a_old,bay_unit,time.time()+RELT)
    oo,fo=score(a_old); told=time.time()-t
    print(f"  OLD _z3_relocate : obj={oo:.0f} feas={fo}  (delta {oo-o0:+.0f})  [{told:.1f}s]")

    # NEW cranepack relocate
    a_new=copy.deepcopy(best_a)
    t=time.time()
    a_new=z3_relocate_cp(prob_info,a_new,bay_unit,time.time()+RELT,FREE=FREE)
    on,fn=score(a_new); tnew=time.time()-t
    print(f"  NEW cranepack    : obj={on:.0f} feas={fn}  (delta {on-o0:+.0f})  [{tnew:.1f}s]  FREE={FREE}")
    print(f"  >>> cranepack vs old: {on:.0f} vs {oo:.0f}  ({'WIN' if on<oo-1e-6 else ('tie' if abs(on-oo)<1e-6 else 'lose')})")

    # STACKED: old -> cranepack (provably never-worse than old; captures extra gains)
    a_stk=copy.deepcopy(a_old)
    t=time.time()
    a_stk=z3_relocate_cp(prob_info,a_stk,bay_unit,time.time()+RELT,FREE=FREE)
    ost,fst=score(a_stk); tstk=time.time()-t
    print(f"  STACK old+crane  : obj={ost:.0f} feas={fst}  (vs old {ost-oo:+.0f})  [{tstk:.1f}s]  "
          f"{'EXTRA GAIN' if ost<oo-1e-6 else 'no extra'}")
    print(f"  >>> BEST-of(old,crane,stack)={min(oo,on,ost):.0f}  vs old {oo:.0f}  "
          f"({'IMPROVED' if min(oo,on,ost)<oo-1e-6 else 'tie'})")
