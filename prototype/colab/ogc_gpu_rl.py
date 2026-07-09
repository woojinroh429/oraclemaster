# ============================================================================
# OGC 2026 — 고밀도 지각(Z1) 최소화 전략 탐색 (Colab)
# ----------------------------------------------------------------------------
# 방법: OpenAI-ES(진화탐색) + 신경망 dispatch/position 정책.
#   패킹 시뮬은 미분불가 -> backprop 대신 ES(보상만 사용, 견고).
#   ★ feasibility는 공식 utils(check_entry/check_exit/check_collisions)를 사용한다.
#     => 시뮬이 만드는 해가 공식 checker를 통과(유효). (빠른 비트마스크 근사는
#        크레인 exit-sweep을 못 맞춰 무효해를 냈음 -> 정확성 우선으로 공식배치 사용.)
#
# ── 속도/GPU에 대한 정직한 설명 ─────────────────────────────────────────
#   공식 크레인 체크가 shapely 기반이라 롤아웃은 CPU-bound·느리다(그래서 실엔진이
#   C++인 것). GPU는 신경망 정책 forward만 가속. 롤아웃은 CPU 멀티프로세스 병렬.
#   "시간 오래 걸려도 OK" 전제하에, 소수 고밀도 인스턴스 + 수백 세대로 전략 탐색.
#   더 빠르게: 인스턴스 수↓, n작은 것부터, POP↓, 캔디데이트 위치 top-K 제한.
#
# ── 요구 파일 (같은 폴더) ───────────────────────────────────────────────
#   utils.py, baseline_greedy.py  (공식 baseline에서 복사).  + shapely, numpy, torch.
#
# ── 사용법 (Colab) ──────────────────────────────────────────────────────
#   1) 런타임>GPU. 2) !pip install shapely numpy torch
#   3) utils.py, baseline_greedy.py, 고밀도 instances/*.json 업로드
#   4) python ogc_gpu_rl.py   (학습, best_policy.pt 주기저장)
#   5) python eval_export.py  (학습정책->유효 operations 해 저장)
# ============================================================================
import os, sys, json, math, time, glob, random
import numpy as np
from utils import Bay, Block, check_entry, check_exit, check_collisions, check_feasibility
from baseline_greedy import _block_bbox, _candidate_positions, _find_earliest_slot

CFG = dict(
    INSTANCE_DIR="./instances", POP=64, GENS=400, SIGMA=0.1, LR=0.02, HIDDEN=64,
    TOPK_POS=12,                      # 위치 후보 top-K (속도)
    N_WORKERS=max(1, os.cpu_count() or 2), SEED=0, EVAL_EVERY=10,
)

def _polyarea(L):
    a=0.0
    for k in range(len(L)):
        x1,y1=L[k]; x2,y2=L[(k+1)%len(L)]; a+=x1*y2-x2*y1
    return abs(a)/2

def prep_instance(path):
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]; n=len(B); m=len(bays)
    due=np.array([b["due_date"] for b in B],float); rel=np.array([b["release_time"] for b in B],float)
    pt=np.array([b["processing_time"] for b in B],float); wl=np.array([b["workload"] for b in B],float)
    ar=np.array([_polyarea(B[i]["shape"][0]["layers"][0]) for i in range(n)])
    # per-orient bbox
    bboxes=[[ _block_bbox(B[i],o) for o in range(len(B[i]["shape"])) ] for i in range(n)]
    widv=np.array([min(bb[2]-bb[0] for bb in bboxes[i]) for i in range(n)])
    hgtv=np.array([min(bb[3]-bb[1] for bb in bboxes[i]) for i in range(n)])
    slack=due-rel-pt
    def rk(v,rev):
        o=np.argsort(-v if rev else v); r=np.zeros(n); r[o]=np.arange(n)/max(1,n-1); return r
    BF=np.stack([rk(due,False),rk(ar,True),rk(pt,True),rk(widv,True),rk(hgtv,True),
                 rk(slack,False), due/(due.max()+1),pt/(pt.max()+1),ar/(ar.max()+1)],axis=1).astype(np.float32)
    w=inst["weights"]; A=[bays[j]["width"]*bays[j]["height"] for j in range(m)]; avg=sum(A)/m; u=[avg/a for a in A]
    return dict(name=inst.get("name",os.path.basename(path)),inst=inst,B=B,bays=bays,n=n,m=m,
                due=due,rel=rel,pt=pt,wl=wl,BF=BF,u=u,bboxes=bboxes,
                prefs=[B[i]["bay_preferences"] for i in range(n)],
                w1=w["w1"],w2=w["w2"],w3=w["w3"])

POS_FEATS=5
def rollout(P, priority, pos_w, want_assign=False):
    """공식 크레인/충돌 체크로 배치. priority(신경망) 순서, 위치는 pos_w 스코어 최소."""
    B=P["B"]; bays=P["bays"]; n=P["n"]; m=P["m"]; due=P["due"]; rel=P["rel"]; pt=P["pt"]; wl=P["wl"]
    u=P["u"]; prefs=P["prefs"]; bboxes=P["bboxes"]
    Bay_objs=[Bay(width=bays[j]["width"],height=bays[j]["height"]) for j in range(m)]
    placed={j:[] for j in range(m)}; sched={j:[] for j in range(m)}; loads=[0.0]*m
    assign={}
    order=sorted(range(n),key=lambda b:priority[b])   # 정적 우선순위(신경망)
    for b in order:
        bd=B[b]; R=int(rel[b]); Pn=int(pt[b]); D=int(due[b]); best=None
        for j in range(m):
            bw=bays[j]["width"]; bh=bays[j]["height"]
            newload=loads[j]+wl[b]
            imb=max((abs(u[j]*newload-u[k]*loads[k]) for k in range(m) if k!=j),default=0.0)
            for o in range(len(bd["shape"])):
                x0,y0,x1,y1=bboxes[b][o]
                if (x1-x0)>bw+1e-6 or (y1-y0)>bh+1e-6: continue
                cands=_candidate_positions(bw,bh,placed[j],(x0,y0,x1,y1))
                if len(cands)>CFG["TOPK_POS"]:
                    cands=sorted(cands,key=lambda c:(c[1],c[0]))[:CFG["TOPK_POS"]]  # bottom-left 근처만
                for (px,py) in cands:
                    blk=Block(block_id=b,block_data=bd,x=float(px),y=float(py),orient_idx=o)
                    en,ex=_find_earliest_slot(blk,Bay_objs[j],placed[j],sched[j],R,Pn)
                    if en is None: continue
                    wx=px+x0; wy=py+y0; h=y1-y0; w=x1-x0
                    ov=0.0
                    for pb in placed[j]:
                        bb=pb.bounding_rect(); dx=min(wx+w,bb[2])-max(wx,bb[0]); dy=min(wy+h,bb[3])-max(wy,bb[1])
                        if dx>0 and dy>0: ov+=dx*dy
                    fs=bw-(wx+w)
                    fv=np.array([wx/max(1,bw),wy/max(1,bh),h/max(1,bh),
                                 -ov/max(1,bw*bh),-fs/max(1,bw)],np.float32)
                    ps=float(fv@pos_w)
                    if best is None or ps<best[0]: best=(ps,j,o,px,py,en,ex,blk)
        if best is None: return None
        _,j,o,px,py,en,ex,blk=best
        placed[j].append(blk); sched[j].append((en,ex)); loads[j]+=wl[b]
        assign[b]=dict(bay=j,o=o,x=int(px),y=int(py),en=int(en),ex=int(ex),
                       tard=max(0,ex-D),pref=max(prefs[b])-prefs[b][j])
    if len(assign)!=n: return None
    if want_assign: return assign
    Z1=sum(a["tard"] for a in assign.values()); Z3=sum(a["pref"] for a in assign.values())
    bl=[0.0]*m
    for b,a in assign.items(): bl[a["bay"]]+=wl[b]
    Z2=math.floor(max((abs(u[i]*bl[i]-u[k]*bl[k]) for i in range(m) for k in range(i+1,m)),default=0.0))
    return P["w1"]*Z1+P["w2"]*Z2+P["w3"]*Z3, Z1, Z2, Z3

# ---- 신경망 정책 + ES (torch, 있으면 GPU) ----
def build_torch():
    import torch, torch.nn as nn
    dev=torch.device("cuda" if torch.cuda.is_available() else "cpu")
    class Policy(nn.Module):
        def __init__(s,d,h):
            super().__init__()
            s.net=nn.Sequential(nn.Linear(d,h),nn.Tanh(),nn.Linear(h,h),nn.Tanh(),nn.Linear(h,1))
            s.pos=nn.Parameter(torch.tensor([0.3,1.0,0.2,0.0,0.0]))
        def priority(s,BF): return s.net(BF).squeeze(-1)
    return torch,nn,dev,Policy
def flat(model):
    import torch; return torch.cat([p.data.reshape(-1) for p in model.parameters()])
def unflat(model,vec):
    import torch; i=0
    for p in model.parameters():
        k=p.numel(); p.data.copy_(vec[i:i+k].view_as(p)); i+=k

_W_PS=None; _W_MODEL=None
def _winit(paths,d,h):
    global _W_PS,_W_MODEL
    import torch; torch.set_num_threads(1)
    _W_PS=[prep_instance(p) for p in paths]
    _,_,_,Policy=build_torch(); _W_MODEL=Policy(d,h)
def _weval(vec):
    import torch; unflat(_W_MODEL,torch.tensor(vec))
    posw=_W_MODEL.pos.detach().cpu().numpy(); tot=0.0
    for P in _W_PS:
        with torch.no_grad(): pri=_W_MODEL.priority(torch.tensor(P["BF"])).cpu().numpy()
        r=rollout(P,pri,posw)
        if r is None: return 1e18
        tot+=r[0]
    return tot/len(_W_PS)

def main():
    random.seed(CFG["SEED"]); np.random.seed(CFG["SEED"])
    paths=sorted(glob.glob(os.path.join(CFG["INSTANCE_DIR"],"*.json")))
    assert paths, f"인스턴스 없음: {CFG['INSTANCE_DIR']}/*.json"
    print("인스턴스:",[os.path.basename(p) for p in paths])
    torch,nn,dev,Policy=build_torch()
    print("device:",dev,"| GPU:",torch.cuda.is_available(),"| workers:",CFG["N_WORKERS"])
    P0=prep_instance(paths[0]); d=P0["BF"].shape[1]
    model=Policy(d,CFG["HIDDEN"]).to(dev); theta=flat(model).clone(); D=theta.numel()
    print(f"정책 파라미터 {D} | pop {CFG['POP']} | gens {CFG['GENS']}")
    import multiprocessing as mp
    pool=mp.Pool(CFG["N_WORKERS"],initializer=_winit,initargs=(paths,d,CFG["HIDDEN"]))
    sigma=CFG["SIGMA"]; lr=CFG["LR"]; rng=np.random.RandomState(CFG["SEED"]); best=(1e18,None)
    for g in range(CFG["GENS"]):
        eps=rng.randn(CFG["POP"]//2,D).astype(np.float32); eps=np.concatenate([eps,-eps])
        th=theta.cpu().numpy(); cand=[th+sigma*eps[k] for k in range(CFG["POP"])]
        fits=np.array(pool.map(_weval,cand))
        if np.all(fits>=1e17): print(f"gen{g}: 전부 배치실패"); continue
        rn=(fits.argsort().argsort()/(len(fits)-1)-0.5)
        grad=(eps.T@(-rn))/(CFG["POP"]*sigma)
        theta=theta+lr*torch.tensor(grad,dtype=theta.dtype)
        if fits.min()<best[0]: best=(float(fits.min()),theta.cpu().numpy().copy())
        if g%2==0: print(f"gen{g:>4} best={best[0]:.0f} gen={fits.min():.0f} sig={sigma:.3f}",flush=True)
        sigma=max(0.02,sigma*0.999)
        if g%CFG["EVAL_EVERY"]==0 and best[1] is not None:
            unflat(model,torch.tensor(best[1]).to(dev)); torch.save(model.state_dict(),"best_policy.pt")
    pool.close()
    print(f"=== 완료 best_obj={best[0]:.0f} | best_policy.pt 저장 (해는 공식 checker 통과) ===")

if __name__=="__main__": main()
