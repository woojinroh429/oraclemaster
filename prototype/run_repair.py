# degenerate zero-area 접촉 리페어 프로토타입: 위반 블록만 엔진으로 재배치(entry 지연)해
# 공식 checker feasible로 만든다. 저밀도라 지연/이동 여유 있음.
import sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myalgorithm import _smallright_construct, _build_operations, _ogc_fast_engine
from utils import check_feasibility

def _viol_blocks(ck):
    bs=set()
    for v in ck.get("violations",[]):
        for mnum,kind in re.findall(r"block (\d+) (entry|exit) obstructed", v):
            bs.add(int(mnum))
        # also spatial collisions "blocks A and B" style
        for a,b in re.findall(r"blocks (\d+) and (\d+)", v):
            bs.add(int(a)); bs.add(int(b))
    return bs

def repair(prob, recs, budget=30.0):
    B=prob["blocks"]; n=len(B); m=len(prob["bays"]); bay_list=list(range(m))
    R={b:dict(recs[b]) for b in range(n)}
    t0=time.time()
    for it in range(40):
        ck=check_feasibility(prob,_build_operations([R[b] for b in range(n)]))
        if ck["feasible"]: return R, True, it
        if time.time()-t0>budget: return R, False, it
        viol=_viol_blocks(ck)
        if not viol: return R, False, it
        progressed=False
        for b in sorted(viol):
            # b 제외 엔진 구성
            E=_ogc_fast_engine(prob); E.clear_all()
            for bb in range(n):
                if bb==b: continue
                r=R[bb]; E.add(r["bay_id"],bb,r["orient_idx"],float(r["x"]),float(r["y"]),int(r["entry_time"]),int(r["exit_time"]))
            rel=B[b]["release_time"]; pt=B[b]["processing_time"]
            cur_en=R[b]["entry_time"]
            placed=False
            # entry를 현재+1부터 지연시켜 재배치, 공식 checker로 검증
            for en in range(cur_en+1, cur_en+60):
                res=E.find_best_placement(b,bay_list,[en])
                if res and res[0]:
                    _,bj,oi,x,y,ren,rex=res
                    trial=dict(R); trial[b]={"block_id":b,"bay_id":int(bj),"x":int(x),"y":int(y),"orient_idx":int(oi),"entry_time":int(ren),"exit_time":int(rex)}
                    ck2=check_feasibility(prob,_build_operations([trial[k] for k in range(n)]))
                    # 전체 위반수 감소 or feasible 이면 채택
                    if ck2["feasible"] or len(ck2.get("violations",[]))<len(ck.get("violations",[])):
                        R=trial; progressed=True; placed=True; break
            if placed: break
        if not progressed: return R, False, it
    return R, check_feasibility(prob,_build_operations([R[b] for b in range(n)]))["feasible"], 40

if __name__=="__main__":
    path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 60.0
    prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path)); n=len(prob["blocks"])
    os.environ["OGC_NOFALLBACK"]="1"
    recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
    ck0=check_feasibility(prob,_build_operations(list(recs.values())))
    print(f"{nm} n={n} 구성 feasible={ck0['feasible']} stage={ck0['stage']} 위반={len(ck0.get('violations',[]))}",flush=True)
    if not ck0["feasible"]:
        R,ok,its=repair(prob,{b:recs[b] for b in range(n)})
        ckf=check_feasibility(prob,_build_operations([R[b] for b in range(n)]))
        z1=sum(max(0,R[b]["exit_time"]-prob["blocks"][b]["due_date"]) for b in range(n))
        print(f"  리페어 후 feasible={ckf['feasible']} (반복 {its}) Z1={z1} obj={ckf['objective'] if ckf['feasible'] else 'N/A'}",flush=True)
