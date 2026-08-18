# ALNS 내부 recreate A/B: greedy vs regret. 동일 초기해(baseline rank+bigleft) + 동일 시드.
# 한 프로세스=한 인스턴스(상태오염 없음). mid-density 이득 검증.
import os, sys, json, time, random, argparse
sys.path.insert(0, os.environ.get("ENGINE_DIR","../sv34"))
import myalgorithm as M
from myalgorithm import (_smallright_construct, _state_from_assign, _alns,
                         _bay_unit_weights, _build_operations, _footprint_areas, _demand_ratio)
from utils import check_feasibility

def objof(inst, assign):
    ck=check_feasibility(inst, _build_operations([assign[b] for b in range(len(assign))]))
    return ck

def run(inst, mode, base_assign, bay_unit, alns_secs, seed):
    state=_state_from_assign(inst, {b:dict(a) for b,a in base_assign.items()})
    rng=random.Random(seed)
    dl=time.time()+alns_secs
    t0=time.time()
    improved,_=_alns(inst, state, bay_unit, dl, rng, recreate=mode)
    dt=time.time()-t0
    if len(improved)!=len(inst["blocks"]): return None,dt
    return objof(inst, improved), dt

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("inst")
    ap.add_argument("--cdl",type=float,default=15.0); ap.add_argument("--step",type=int,default=1)
    ap.add_argument("--alns",type=float,default=25.0); ap.add_argument("--seed",type=int,default=12345)
    a=ap.parse_args()
    inst=json.load(open(a.inst)); name=os.path.basename(a.inst).replace(".json",""); n=len(inst["blocks"])
    ar,bc,_=_footprint_areas(inst); ratio=_demand_ratio(inst,ar,bc)
    base=_smallright_construct(inst,a.cdl,0.60,a.step,"bigleft","rank",tiebreak="due")
    if not base or len(base)!=n: print(f"{name}: baseline FAIL"); return
    ckb=objof(inst,base); bay_unit=_bay_unit_weights(inst["bays"])
    print(f"{name} n={n} ratio={ratio:.3f} baseline Z1={ckb['obj1']:.0f} obj={ckb['objective']:.0f}")
    og,dg=run(inst,"greedy",base,bay_unit,a.alns,a.seed)
    orr,dr=run(inst,"regret",base,bay_unit,a.alns,a.seed)
    def fmt(ck): return f"Z1={ck['obj1']:.0f} obj={ck['objective']:.0f}" if ck else "FAIL"
    print(f"  greedy-ALNS: {fmt(og)} ({dg:.0f}s)")
    print(f"  regret-ALNS: {fmt(orr)} ({dr:.0f}s)")
    if og and orr:
        dv=100*(og['objective']-orr['objective'])/og['objective']
        best=min(ckb['objective'],og['objective'],orr['objective'])
        who='regret' if orr['objective']<og['objective'] else 'greedy'
        print(f"  => regret vs greedy: {dv:+.2f}%  | winner={who} | best-of obj={best:.0f}")

if __name__=="__main__": main()
