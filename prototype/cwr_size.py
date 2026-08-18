"""
Sizing probe for crane-aware window rescheduling (option A).
Find the congested bay+window driving tardiness on prob_28, list competing blocks,
and estimate column counts (entry-time x orient x coarse position) so we know the
CP-SAT set-packing is tractable before building it.
"""
import os, sys, json
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import numpy as np
import myalgorithm as M

def reconstruct(inst, sol):
    ops=sol["operations"]; place={}
    for ts,lst in ops.items():
        t=int(ts)
        for o in lst:
            b=o["block_id"]
            if o["type"]=="ENTRY":
                place.setdefault(b,{}).update(bay=o["bay_id"],x=o["x"],y=o["y"],oi=o["orient_idx"],en=t,bid=b)
            else: place.setdefault(b,{})["ex"]=t
    for b,p in place.items():
        if "ex" not in p: p["ex"]=p["en"]+inst["blocks"][b]["processing_time"]
    return place

def bbox(B,b,oi):
    L=B[b]["shape"][oi]["layers"]; xs=[q[0] for l in L for q in l]; ys=[q[1] for l in L for q in l]
    return min(xs),min(ys),max(xs),max(ys)

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_28.json"
    inst=json.load(open(path)); B=inst["blocks"]; bays=inst["bays"]; nbay=len(bays)
    sol=M.algorithm(inst,60); place=reconstruct(inst,sol)
    # tardy blocks
    tardy=[(b,max(0,p["ex"]-B[b]["due_date"])) for b,p in place.items() if max(0,p["ex"]-B[b]["due_date"])>0]
    tardy.sort(key=lambda x:-x[1])
    print(f"{os.path.basename(path)}: {len(tardy)} tardy blocks, total Z1={sum(t for _,t in tardy)}")
    # congested window: the release-time with the most co-present tardy-ish blocks per bay
    # Consider a window [t0,t1] and the blocks whose interval overlaps it in a given bay.
    for target_b,tv in tardy[:1]:
        p=place[target_b]; bay=p["bay"]; W=bays[bay]["width"]; H=bays[bay]["height"]
        en,ex=p["en"],p["ex"]; rel=B[target_b]["release_time"]
        # window = [rel, ex]; blocks in this bay overlapping [rel,ex]
        win=[b for b,q in place.items() if q["bay"]==bay and q["en"]<ex and q["ex"]>rel]
        print(f" target block {target_b} tard={tv} bay={bay} {W}x{H} window[{rel},{ex}] competing={len(win)}")
        # estimate columns per block: entry times x orients x coarse positions (step 3)
        tot_cols=0
        for b in win:
            pt=B[b]["processing_time"]; rlo=B[b]["release_time"]; rhi=B[b]["due_date"]-pt
            nt=max(1,min(6, rhi-rlo+1))
            cols=0
            for oi in range(len(B[b]["shape"])):
                x0,y0,x1,y1=bbox(B,b,oi)
                if (x1-x0)>W or (y1-y0)>H: continue
                nx=len(range(int(np.ceil(-x0)),int(np.floor(W-x1))+1,3))
                ny=len(range(int(np.ceil(-y0)),int(np.floor(H-y1))+1,3))
                cols+=nx*ny
            tot_cols+=cols*nt
        print(f"   est columns (all blocks, step3, <=6 times): {tot_cols}  avg/block={tot_cols/max(len(win),1):.0f}")
    print("ALLDONE")

if __name__=="__main__": main()
