# 혼잡 시간창 재패킹 (window-LNS, 실제 엔진).
#  나머지 freeze -> 창 블록만 bigleft 스코어링으로 순서 여러개 시도 재배치 -> Z1 개선시 채택.
import sys, os, json, time, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import myalgorithm as MA
from myalgorithm import (_smallright_construct, _build_operations, _ogc_fast_engine,
                         _orient_bbox, _footprint_areas)
from utils import check_feasibility

path=sys.argv[1]; DL=float(sys.argv[2]) if len(sys.argv)>2 else 150.0
BUD=float(sys.argv[3]) if len(sys.argv)>3 else 300.0
WIN=int(sys.argv[4]) if len(sys.argv)>4 else 20      # 창 반경
AMAX=int(sys.argv[5]) if len(sys.argv)>5 else 60     # 창 블록 상한
prob=json.load(open(path)); nm=prob.get("name",os.path.basename(path))
B=prob["blocks"]; n=len(B); m=len(prob["bays"]); bay_list=list(range(m))
bw=[prob["bays"][j]["width"] for j in range(m)]; bh=[prob["bays"][j]["height"] for j in range(m)]
due=[b["due_date"] for b in B]; rel=[b["release_time"] for b in B]; pt=[b["processing_time"] for b in B]
areas,_,SC=_footprint_areas(prob)
# 면적순위(작은블록 게이트용)
_o=sorted(range(n),key=lambda i:areas[i],reverse=True); ra=[0.0]*n
for p,i in enumerate(_o): ra[i]=p/max(1,n-1)

recs=_smallright_construct(prob,DL,0.60,1,"bigleft","rank")
if not recs or len(recs)!=n: print("구성 실패"); sys.exit()
R={b:dict(recs[b]) for b in range(n)}
def Z1(Rd): return sum(max(0,Rd[b]["exit_time"]-due[b]) for b in range(n))
def evalfull(Rd): return check_feasibility(prob,_build_operations([Rd[b] for b in range(n)]))
ck0=evalfull(R); curZ1=ck0["obj1"]
print(f"=== {nm} (n={n}) | window-LNS 재패킹 | 시작 Z1={curZ1:.0f} feas={ck0['feasible']} | WIN={WIN} AMAX={AMAX} ===",flush=True)

BAND=0.6
def repack(A, order, frozen):
    """frozen: list of (bay,bbox,en,ex). A를 order대로 bigleft 재배치. dict{b:rec} 또는 None."""
    E=_ogc_fast_engine(prob); E.clear_all()
    for (j,bb2,en,ex,bid,oi,x,y) in frozen:
        E.add(j,bid,oi,float(x),float(y),int(en),int(ex))
    placed_A=[]   # (j,(x0,y0,x1,y1),en,ex)
    outR={}
    def free_span(j,cur,cx0,cx1,cy0):
        band=bh[j]*BAND; occ=[]
        for (fj,(x0,y0,x1,y1),en,ex,*_) in frozen:
            if fj==j and en<=cur<ex and y0<band: occ.append((x0,x1))
        for (pj,(x0,y0,x1,y1),en,ex) in placed_A:
            if pj==j and en<=cur<ex and y0<band: occ.append((x0,x1))
        if cy0<band: occ.append((cx0,cx1))
        occ.sort(); c=0.0; fm=0.0
        for a,b_ in occ:
            if a>c: fm=max(fm,a-c)
            if b_>c: c=b_
        return max(fm, bw[j]-c)
    def place(b,cur):
        ex=cur+pt[b]; best=None; bestsc=None; sml=ra[b]>=0.60
        for j in bay_list:
            for oi in range(len(B[b]["shape"])):
                x0,y0,x1,y1=_orient_bbox(B[b],oi); w=x1-x0; h=y1-y0
                if w>bw[j]+1e-9 or h>bh[j]+1e-9: continue
                lox=math.ceil(-x0); hix=math.floor(bw[j]-x1)
                loy=math.ceil(-y0); hiy=math.floor(bh[j]-y1)
                for ix in range(lox,hix+1):
                    for iy in range(loy,hiy+1):
                        if E.placement_feasible(j,b,oi,float(ix),float(iy),cur,ex):
                            wx=ix+x0; wy=iy+y0
                            if sml: sc=(-free_span(j,cur,wx,wx+w,wy),wy,wx,j)
                            else:   sc=(h,wx,wy,j)
                            if bestsc is None or sc<bestsc: bestsc=sc; best=(j,oi,ix,iy,wx,wy,x0,y0,x1,y1)
        return best,ex
    # 이벤트 루프: A를 릴리즈부터 순서대로. 각 이벤트 cur에서 order대로 배치 시도.
    import heapq
    pend=set(A); eh=[]; t0=time.time()
    orl=sorted(A,key=lambda b:rel[b]); ri=0; cur=min(rel[b] for b in A)
    keyrank={b:order.index(b) for b in A}
    guard=0
    while True:
        while ri<len(orl) and rel[orl[ri]]<=cur: pend.add(orl[ri]); ri+=1
        while eh and eh[0][0]<=cur: heapq.heappop(eh)
        placed_now=[]
        for b in sorted(pend,key=lambda b:keyrank[b]):
            res,ex=place(b,cur)
            if res:
                j,oi,ix,iy,wx,wy,x0,y0,x1,y1=res
                E.add(j,b,oi,float(ix),float(iy),cur,ex)
                bbox=(ix+x0,iy+y0,ix+x1,iy+y1)
                placed_A.append((j,bbox,cur,ex))
                outR[b]={"block_id":b,"bay_id":j,"x":ix,"y":iy,"orient_idx":oi,"entry_time":cur,"exit_time":ex}
                heapq.heappush(eh,(ex,b)); placed_now.append(b)
        for b in placed_now: pend.discard(b)
        if not pend and ri>=len(orl) and not eh: break
        c=[]
        if ri<len(orl): c.append(rel[orl[ri]])
        if eh: c.append(eh[0][0])
        if pend and not eh and ri>=len(orl): c.append(cur+1)
        cur=min(c) if c else cur+1; guard+=1
        if guard>100000 or time.time()-t0>60: break
    if len(outR)!=len(A): return None
    return outR

# frozen 표현 만들기 helper
def make_frozen(A):
    Aset=set(A); fr=[]
    for b in range(n):
        if b in Aset: continue
        r=R[b]; x0,y0,x1,y1=_orient_bbox(B[b],r["orient_idx"])
        fr.append((r["bay_id"],(r["x"]+x0,r["y"]+y0,r["x"]+x1,r["y"]+y1),
                   r["entry_time"],r["exit_time"],b,r["orient_idx"],r["x"],r["y"]))
    return fr

t0=time.time(); it=0; accepted=0
while time.time()-t0<BUD:
    it+=1
    # 대기 카운트로 peak 창 찾기
    tmax=max(R[b]["exit_time"] for b in range(n)); tmin=min(rel)
    waitcnt=[0]*(tmax+2)
    for b in range(n):
        for t in range(rel[b],R[b]["entry_time"]):
            if 0<=t<=tmax: waitcnt[t]+=1
    pk=max(range(tmin,tmax+1),key=lambda t:waitcnt[t])
    w0,w1=pk-WIN,pk+WIN
    # 창에 '존재'하는 모든 블록 = 재배치 대상 (최대 자유)
    A=[b for b in range(n) if R[b]["entry_time"]<w1 and R[b]["exit_time"]>w0]
    if len(A)>AMAX:
        A=sorted(A,key=lambda b:abs(R[b]["entry_time"]-pk))[:AMAX]
    if len(A)<2: print("  창 블록 부족"); break
    frozen=make_frozen(A)
    A_tard0=sum(max(0,R[b]["exit_time"]-due[b]) for b in A)
    # 순서 후보
    orders=[]
    rank_o=sorted(A,key=lambda b:(ra[b], due[b]))  # 대략 rank(면적)
    edd_o=sorted(A,key=lambda b:due[b])
    ar_o=sorted(A,key=lambda b:areas[b],reverse=True)
    rel_o=sorted(A,key=lambda b:(rel[b],due[b]))
    orders=[("orig",sorted(A,key=lambda b:R[b]["entry_time"])),("rank",rank_o),
            ("edd",edd_o),("area",ar_o),("rel",rel_o)]
    for s in range(20):
        o=list(rank_o);
        for _ in range(max(1,len(o)//5)):
            i=(s*7+_*13)%len(o); j=(s*11+_*17+1)%len(o); o[i],o[j]=o[j],o[i]
        orders.append((f"pert{s}",o))
    best=None; bestT=A_tard0
    for tag,order in orders:
        if time.time()-t0>BUD: break
        out=repack(A,order,frozen)
        if out is None: continue
        at=sum(max(0,out[b]["exit_time"]-due[b]) for b in A)
        if at<bestT-1e-9: bestT=at; best=out
    if best is not None:
        newR=dict(R); newR.update(best)
        ck=evalfull(newR)
        if ck["feasible"] and ck["obj1"]<curZ1-1e-9:
            R=newR; curZ1=ck["obj1"]; accepted+=1
            print(f"  it{it} peak@{pk} |A|={len(A)} A_tard {A_tard0}->{bestT} => Z1 {curZ1:.0f} (채택)",flush=True)
        else:
            print(f"  it{it} peak@{pk} |A|={len(A)} A_tard {A_tard0}->{bestT} but full Z1 no-improve/infeas",flush=True)
            break
    else:
        print(f"  it{it} peak@{pk} |A|={len(A)} A_tard0={A_tard0} 개선없음",flush=True)
        break
ckf=evalfull(R)
print(f"=== 최종 Z1={ckf['obj1']:.0f} (시작 {ck0['obj1']:.0f}, Δ={ck0['obj1']-ckf['obj1']:+.0f}) accepted={accepted} ({time.time()-t0:.0f}s) feas={ckf['feasible']} ===",flush=True)
