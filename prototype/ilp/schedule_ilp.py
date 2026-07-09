# ============================================================================
# 프로토타입 2: 고정패킹 + exact 스케줄 MILP (CP-SAT=Gurobi 대역).
# 참신한 제약: 위치를 이산화하지 않음.  풀 솔버의 연속 패킹(위치)을 FIX -> 지각은 진입시각에만
# 의존(exit=entry+p) -> Gurobi로 진입시각만 exact 최적화.  충돌(그 위치서 공존불가)=disjoint 구간.
# = disjunctive 스케줄링(Gurobi 강점).  이산화 손실 0.  rank 그리디보다 나은 스케줄 있으면 Z1↓.
# ============================================================================
import os, sys, json, time
sys.path.insert(0, os.environ.get("ENGINE_DIR","../ad"))
import myalgorithm as M
from myalgorithm import algorithm, _ogc_fast_engine, _build_operations
from utils import check_feasibility
from ortools.sat.python import cp_model

def parse_assign(inst, sol):
    n=len(inst["blocks"]); ent={}; ext={}
    for t,ops in sol["operations"].items():
        ti=int(t)
        for o in ops:
            if o["type"]=="ENTRY": ent[int(o["block_id"])]=(ti,o["bay_id"],o["x"],o["y"],o["orient_idx"])
            elif o["type"]=="EXIT": ext[int(o["block_id"])]=ti
    return {b:dict(bay=ent[b][1],x=ent[b][2],y=ent[b][3],o=ent[b][4],en=ent[b][0],ex=ext[b]) for b in range(n)}

def conflict_graph(inst, A):
    """두 블록이 그 위치에서 '동시 존재 불가'면 시간 disjoint 충돌. 순수 공간성질(시각 무관)."""
    n=len(inst["blocks"]); B=inst["blocks"]; E=_ogc_fast_engine(inst); conf=[]
    for i in range(n):
        pi=int(B[i]["processing_time"])
        for j in range(i+1,n):
            if A[i]["bay"]!=A[j]["bay"]: continue
            pj=int(B[j]["processing_time"])
            # SEQUENTIAL-entry coexistence: i settled first (present over a long window),
            # j enters later while i is present.  If feasible -> they CAN coexist (order
            # i->j).  Test both orders; disjoint conflict ONLY if BOTH orders infeasible.
            E.clear_all(); E.add(A[i]["bay"],i,A[i]["o"],float(A[i]["x"]),float(A[i]["y"]),0,10000)
            ok1=E.placement_feasible(A[j]["bay"],j,A[j]["o"],float(A[j]["x"]),float(A[j]["y"]),5,5+pj)
            E.clear_all(); E.add(A[j]["bay"],j,A[j]["o"],float(A[j]["x"]),float(A[j]["y"]),0,10000)
            ok2=E.placement_feasible(A[i]["bay"],i,A[i]["o"],float(A[i]["x"]),float(A[i]["y"]),5,5+pi)
            if not (ok1 or ok2): conf.append((i,j))
    return conf

def solve_sched(inst, A, conf, tl=30):
    n=len(inst["blocks"]); B=inst["blocks"]
    H=int(max(b["due_date"] for b in B)+max(b["processing_time"] for b in B)+30)
    m=cp_model.CpModel()
    e=[m.NewIntVar(int(B[i]["release_time"]),H,f"e{i}") for i in range(n)]
    tard=[]
    for i in range(n):
        pi=int(B[i]["processing_time"]); dd=int(B[i]["due_date"])
        t=m.NewIntVar(0,H,f"t{i}"); m.Add(t>=e[i]+pi-dd); tard.append(t)
    for (i,j) in conf:
        pi=int(B[i]["processing_time"]); pj=int(B[j]["processing_time"])
        bvar=m.NewBoolVar(f"o{i}_{j}")
        m.Add(e[i]+pi<=e[j]).OnlyEnforceIf(bvar)
        m.Add(e[j]+pj<=e[i]).OnlyEnforceIf(bvar.Not())
    m.Minimize(sum(tard))
    s=cp_model.CpSolver(); s.parameters.max_time_in_seconds=tl; s.parameters.num_search_workers=4
    st=s.Solve(m)
    if st not in (cp_model.OPTIMAL,cp_model.FEASIBLE): return None,None
    return {i:int(s.Value(e[i])) for i in range(n)}, s.StatusName(st)

def main():
    inst=json.load(open(sys.argv[1])); K=int(sys.argv[2]) if len(sys.argv)>2 else len(inst["blocks"])
    import copy; sub=copy.deepcopy(inst); sub["blocks"]=sub["blocks"][:K]
    tl_full=int(sys.argv[3]) if len(sys.argv)>3 else 40
    sol=algorithm(sub,tl_full); ck0=check_feasibility(sub,sol)
    print(f"full solver: Z1={ck0['obj1']} obj={ck0['objective']} feasible={ck0['feasible']}")
    A=parse_assign(sub,sol)
    t0=time.time(); conf=conflict_graph(sub,A); tc=time.time()-t0
    print(f"conflict graph: {len(conf)} disjoint pairs ({tc:.1f}s)")
    import re
    n=len(sub["blocks"]); B=sub["blocks"]; conf=set(map(tuple,map(sorted,conf)))
    # LAZY-CONFLICT BENDERS: solve schedule -> check -> add violating pairs as disjoint -> repeat
    for it in range(25):
        ent,stt=solve_sched(sub,A,list(conf),tl=30)
        if ent is None: print("MILP failed"); return
        recs={i:{"block_id":i,"bay_id":A[i]["bay"],"x":A[i]["x"],"y":A[i]["y"],"orient_idx":A[i]["o"],
                 "entry_time":ent[i],"exit_time":ent[i]+int(B[i]["processing_time"])} for i in range(n)}
        ck=check_feasibility(sub,_build_operations([recs[i] for i in range(n)]))
        Z1=sum(max(0,ent[i]+int(B[i]["processing_time"])-int(B[i]["due_date"])) for i in range(n))
        if ck["feasible"]:
            print(f"  iter{it}: feasible Z1={ck['obj1']} obj={ck['objective']}  (conf={len(conf)})")
            print(f"=== Z1: full={ck0['obj1']} -> MILP={ck['obj1']}  ({'MILP WINS' if ck['obj1']<ck0['obj1'] else 'tie/worse'}) ===")
            return
        # add newly-discovered conflicts: collision pairs + crane-obstruction pairs
        new=0
        for v in ck.get("violations",[]):
            ps=[int(x) for x in re.findall(r"block[s]? (\d+)",v)]
            for a in range(len(ps)):
                for b in range(a+1,len(ps)):
                    key=tuple(sorted((ps[a],ps[b])))
                    if ps[a]!=ps[b] and key not in conf: conf.add(key); new+=1
        print(f"  iter{it}: MILP Z1(model)={Z1} infeasible, +{new} conflicts (total {len(conf)})")
        if new==0: print("  no new conflicts extractable -> stop"); break

if __name__=="__main__": main()
