# ============================================================================
# OGC 2026 — 실엔진(C++) 위 ES 학습 (Colab). 고밀도 지각 최소화 dispatch 정책.
# ----------------------------------------------------------------------------
# ★ 핵심: fitness = 실엔진 _smallright_construct(공식 크레인/충돌, 유효 해) 의 공식
#   objective. 신경망 정책이 per-block priority를 내면 engine의 ext_entry로 주입 ->
#   그 순서로 bigleft 배치 -> 공식 check_feasibility objective. ES가 신경망 최적화.
#   => 시뮬-실엔진 불일치(전이문제) 원천 소멸. 해는 항상 공식 checker 통과.
#   GPU: 신경망 forward. 엔진 구성: CPU(멀티프로세스 병렬).
#
# ── Colab 준비 (중요) ───────────────────────────────────────────────────
#   .so는 cpython-3.12용이라 Colab Python을 3.12로 맞춰야 로드됨.
#   방법(예):
#     !sudo apt-get update && sudo apt-get install -y python3.12 python3.12-venv
#     !python3.12 -m venv /content/venv312 && source /content/venv312/bin/activate
#     !/content/venv312/bin/pip install ortools numba shapely numpy torch
#   그리고 submit_v35의 파일들을 ./engine/ 에 업로드:
#     myalgorithm.py, utils.py, ogc_state*.so, ogc_geom*.so, ogc_fast*.so
#   인스턴스는 ./instances/*.json (고밀도, n=100 권장: 빠름).
#   실행: /content/venv312/bin/python es_real_engine.py
#   (엔진 .so가 안 뜨면 _smallright_construct가 실패 -> Python 3.12 필수)
# ============================================================================
import os, sys, json, math, time, glob, random
import numpy as np

ENGINE_DIR = os.environ.get("ENGINE_DIR", "./engine")
sys.path.insert(0, ENGINE_DIR)

CFG = dict(
    INSTANCE_DIR="./instances",
    DEADLINE=35.0,        # 엔진 구성 예산(초). n=100~35, n=250는 100+ 필요(느림)
    STEP=1,               # 1=고품질/느림, 2=빠름/약간낮음
    POP=32, GENS=300, SIGMA=0.15, LR=0.03, HIDDEN=64,
    N_WORKERS=max(1, os.cpu_count() or 2), SEED=0, EVAL_EVERY=10,
    TIEBREAK="due",
)

# 엔진 로드
import myalgorithm as ENG
from myalgorithm import _smallright_construct, _build_operations, _orient_bbox
from utils import check_feasibility
BIG = 1e18

def prep(path):
    inst=json.load(open(path)); B=inst["blocks"]; n=len(B)
    due=np.array([b["due_date"] for b in B],float); rel=np.array([b["release_time"] for b in B],float)
    pt=np.array([b["processing_time"] for b in B],float)
    def area(i):
        L=B[i]["shape"][0]["layers"][0]; a=0.0
        for k in range(len(L)):
            x1,y1=L[k]; x2,y2=L[(k+1)%len(L)]; a+=x1*y2-x2*y1
        return abs(a)/2
    ar=np.array([area(i) for i in range(n)])
    widv=np.zeros(n); hgtv=np.zeros(n)
    for i in range(n):
        ws=[]; hs=[]
        for o in range(len(B[i]["shape"])):
            x0,y0,x1,y1=_orient_bbox(B[i],o); ws.append(x1-x0); hs.append(y1-y0)
        widv[i]=min(ws); hgtv[i]=min(hs)
    slack=due-rel-pt
    def rk(v,rev):
        o=np.argsort(-v if rev else v); r=np.zeros(n); r[o]=np.arange(n)/max(1,n-1); return r
    BF=np.stack([rk(due,False),rk(ar,True),rk(pt,True),rk(widv,True),rk(hgtv,True),
                 rk(slack,False), due/(due.max()+1),pt/(pt.max()+1),ar/(ar.max()+1)],axis=1).astype(np.float32)
    return dict(name=inst.get("name",os.path.basename(path)),inst=inst,n=n,BF=BF)

def fitness_one(P, priority):
    ext=[float(x) for x in priority]
    try:
        recs=_smallright_construct(P["inst"], CFG["DEADLINE"], 0.60, CFG["STEP"],
                                   "bigleft", "rank", ext_entry=ext, tiebreak=CFG["TIEBREAK"])
    except Exception:
        return BIG
    if not recs or len(recs)!=P["n"]: return BIG
    ck=check_feasibility(P["inst"], _build_operations(list(recs.values())))
    return float(ck["objective"]) if ck.get("feasible") else BIG

# ---- 신경망 정책 (torch/GPU) ----
def build_torch():
    import torch, torch.nn as nn
    dev=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    class Policy(nn.Module):
        def __init__(s,d,h):
            super().__init__()
            s.net=nn.Sequential(nn.Linear(d,h),nn.Tanh(),nn.Linear(h,h),nn.Tanh(),nn.Linear(h,1))
        def priority(s,BF): return s.net(BF).squeeze(-1)
    return torch,nn,dev,Policy
def flat(m):
    import torch; return torch.cat([p.data.reshape(-1) for p in m.parameters()])
def unflat(m,vec):
    import torch; i=0
    for p in m.parameters():
        k=p.numel(); p.data.copy_(vec[i:i+k].view_as(p)); i+=k

_PS=None; _MODEL=None
def _winit(paths,d,h):
    global _PS,_MODEL
    import torch; torch.set_num_threads(1)
    _PS=[prep(p) for p in paths]
    _,_,_,Policy=build_torch(); _MODEL=Policy(d,h)
def _weval(vec):
    import torch; unflat(_MODEL,torch.tensor(vec)); tot=0.0
    for P in _PS:
        with torch.no_grad(): pri=_MODEL.priority(torch.tensor(P["BF"])).cpu().numpy()
        f=fitness_one(P,pri)
        if f>=BIG: return BIG
        tot+=f
    return tot/len(_PS)

def main():
    print("engine:", "HAVE_CPP=",getattr(ENG,"HAVE_CPP",None),"HAVE_OGC_FAST=",getattr(ENG,"HAVE_OGC_FAST",None))
    assert getattr(ENG,"HAVE_OGC_FAST",False), "엔진 .so 미로드! Colab Python을 3.12로 맞추고 .so 업로드 필요."
    random.seed(CFG["SEED"]); np.random.seed(CFG["SEED"])
    paths=sorted(glob.glob(os.path.join(CFG["INSTANCE_DIR"],"*.json")))
    assert paths, f"인스턴스 없음: {CFG['INSTANCE_DIR']}/*.json"
    print("인스턴스:",[os.path.basename(p) for p in paths])
    torch,nn,dev,Policy=build_torch()
    print("device:",dev,"| GPU:",torch.cuda.is_available(),"| workers:",CFG["N_WORKERS"])
    P0=prep(paths[0]); d=P0["BF"].shape[1]
    model=Policy(d,CFG["HIDDEN"]).to(dev); theta=flat(model).clone(); D=theta.numel()
    # baseline(rank) 기준 출력
    rankpri=P0["BF"][:,0]+P0["BF"][:,1]
    print(f"참고 rank fitness({P0['name']}):", fitness_one(P0, rankpri))
    print(f"정책파라미터 {D} | pop {CFG['POP']} | gens {CFG['GENS']} | deadline {CFG['DEADLINE']}s step{CFG['STEP']}")
    import multiprocessing as mp
    pool=mp.Pool(CFG["N_WORKERS"],initializer=_winit,initargs=(paths,d,CFG["HIDDEN"]))
    sigma=CFG["SIGMA"]; lr=CFG["LR"]; rng=np.random.RandomState(CFG["SEED"]); best=(BIG,None)
    for g in range(CFG["GENS"]):
        eps=rng.randn(CFG["POP"]//2,D).astype(np.float32); eps=np.concatenate([eps,-eps])
        th=theta.cpu().numpy(); cand=[th+sigma*eps[k] for k in range(CFG["POP"])]
        fits=np.array(pool.map(_weval,cand))
        if np.all(fits>=BIG): print(f"gen{g}: 전부 실패"); continue
        rn=(fits.argsort().argsort()/(len(fits)-1)-0.5)
        grad=(eps.T@(-rn))/(CFG["POP"]*sigma)
        theta=theta+lr*torch.tensor(grad,dtype=theta.dtype)
        if fits.min()<best[0]: best=(float(fits.min()),theta.cpu().numpy().copy())
        print(f"gen{g:>4} best={best[0]:.0f} gen={fits.min():.0f} sig={sigma:.3f}",flush=True)
        sigma=max(0.03,sigma*0.995)
        if g%CFG["EVAL_EVERY"]==0 and best[1] is not None:
            unflat(model,torch.tensor(best[1]).to(dev)); torch.save(model.state_dict(),"best_policy.pt")
            np.save("best_theta.npy", best[1])
    pool.close()
    print(f"=== 완료 best_obj={best[0]:.0f} (실엔진 공식objective) | best_policy.pt 저장 ===")
    print("이 정책은 실엔진에서 학습됐으므로 전이문제 없음. submit에 반영하려면 ext_entry로 주입.")

if __name__=="__main__": main()
