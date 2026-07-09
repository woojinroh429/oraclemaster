# 방향 seed가 ALNS 후에도 유효한가? construction=bigleft vs =DIR -> 동일 ALNS -> 최종 obj 비교.
# 한 프로세스=한 인스턴스, 동일 시드. (window-LNS 교훈: construction-stage 말고 full-solver로 판정)
import os, sys, json, time, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as M
from myalgorithm import (_smallright_construct, _state_from_assign, _alns,
                         _bay_unit_weights, _build_operations, _footprint_areas, _demand_ratio)
from utils import check_feasibility

def objof(inst, assign):
    return check_feasibility(inst, _build_operations([assign[b] for b in range(len(assign))]))

def seed_plus_alns(inst, mode, cdl, step, alns_secs, seed, bay_unit):
    recs=_smallright_construct(inst,cdl,0.60,step,mode,"rank",tiebreak="due")
    if not recs or len(recs)!=len(inst["blocks"]): return None,None
    ck0=objof(inst,recs)
    if not ck0.get("feasible"): return None,None
    state=_state_from_assign(inst,{b:dict(a) for b,a in recs.items()})
    rng=random.Random(seed); dl=time.time()+alns_secs
    improved,_=_alns(inst,state,bay_unit,dl,rng)
    if len(improved)!=len(inst["blocks"]): return ck0,None
    ckf=objof(inst,improved)
    return ck0,(ckf if ckf.get("feasible") else None)

def main():
    path=sys.argv[1]; DIR=sys.argv[2]; cdl=float(sys.argv[3]); step=int(sys.argv[4]); alns=float(sys.argv[5])
    inst=json.load(open(path)); name=os.path.basename(path).replace(".json",""); n=len(inst["blocks"])
    ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc); bu=_bay_unit_weights(inst["bays"])
    c0b,cfb=seed_plus_alns(inst,"bigleft",cdl,step,alns,777,bu)
    c0d,cfd=seed_plus_alns(inst,DIR,cdl,step,alns,777,bu)
    def z(c): return f"{c['obj1']:.0f}/{c['objective']:.0f}" if c else "FAIL"
    print(f"{name} r={ratio:.3f} | bigleft seed {z(c0b)} ->ALNS {z(cfb)} | {DIR} seed {z(c0d)} ->ALNS {z(cfd)}")
    if cfb and cfd:
        dv=100*(cfb['objective']-cfd['objective'])/cfb['objective']
        print(f"   => after ALNS, {DIR} vs bigleft: {dv:+.2f}%  winner={'DIR' if cfd['objective']<cfb['objective'] else 'bigleft/tie'}")

if __name__=="__main__": main()
