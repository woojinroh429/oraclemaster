"""
Robustness stress test: run the algorithm on EXTREME bay shapes far outside the
training range (height 15-29, aspect 1.1-11). Verify it stays FEASIBLE, doesn't
crash, and doesn't blow the time budget. Bays are sized to still fit every block
(checked). Tests: tall (height>>width), square, huge, tiny-but-feasible.
"""
import os, sys, json, copy, time
os.environ.setdefault("ENGINE_DIR", ".")
sys.path.insert(0, ".")
import myalgorithm as M
from utils import check_feasibility

def block_maxdim(inst):
    mx=0
    for blk in inst["blocks"]:
        for orient in blk["shape"]:
            xs=[q[0] for l in orient["layers"] for q in l]; ys=[q[1] for l in orient["layers"] for q in l]
            mx=max(mx, min(max(xs)-min(xs), max(ys)-min(ys)))  # min-dim over orients (rotatable)
    return mx

def with_bays(inst, dims):
    """Replace bays AND fix each block's bay_preferences to the new bay count so the
    instance stays VALID (pref length must == n_bays)."""
    t=copy.deepcopy(inst); m=len(dims)
    t["bays"]=[{"width":w,"height":h} for (w,h) in dims]
    for blk in t["blocks"]:
        pref=blk["bay_preferences"]
        if len(pref)<m:      # extend: repeat/cycle existing prefs for new bays
            pref=pref+[pref[i%len(pref)] for i in range(m-len(pref))]
        else:
            pref=pref[:m]
        blk["bay_preferences"]=pref
    return t

def run(inst, tag):
    try:
        t0=time.time(); sol=M.algorithm(inst,60); dt=time.time()-t0
        ck=check_feasibility(inst,sol)
        return f"{tag}: feasible={ck['feasible']} obj={ck['objective'] if ck['feasible'] else 'N/A'} ({dt:.0f}s)"
    except Exception as e:
        return f"{tag}: !!! CRASH: {type(e).__name__}: {e}"

def main():
    path=sys.argv[1] if len(sys.argv)>1 else "../data/train/prob_22.json"
    inst=json.load(open(path)); nm=os.path.basename(path).replace(".json","")
    md=block_maxdim(inst)  # every block fits a bay if both dims >= md (rotatable)
    s=max(48, md+2)
    print(f"{nm}: {len(inst['blocks'])} blocks, min-dim bound={md} (bays need both dims>= {md})",flush=True)
    configs={
        "TALL 30x90 x2":   [(max(30,s), 90),(max(30,s),90)],
        "SQUARE 55x55 x2": [(55,55),(55,55)],
        "HUGE 220x50 x1":  [(220,50)],
        "TINY-ish 50x35 x3": [(50,35),(50,35),(50,35)],
        "MANY 60x40 x6":   [(60,40)]*6,
        "EXTREME-TALL 34x140 x2": [(max(34,s),140),(max(34,s),140)],
    }
    for tag,dims in configs.items():
        # ensure every bay fits the biggest block (both dims >= md)
        dims=[(max(w,md+1),max(h,md+1)) for (w,h) in dims]
        print("  "+run(with_bays(inst,dims), tag),flush=True)
    print("ALLDONE")

if __name__=="__main__": main()
