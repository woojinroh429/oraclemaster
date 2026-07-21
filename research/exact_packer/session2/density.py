"""Light density/objective profiler (NO solving): pick MODERATE high-density instances
(Z1-relevant but not ultra-dense) for a cranepack/VLNS high-density experiment."""
import json, os, glob
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
def bbox_area(shape0):
    pts=[p for L in shape0["layers"] for p in L]
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return (max(xs)-min(xs))*(max(ys)-min(ys))
rows=[]
for f in sorted(glob.glob(f"{SP}/data/training_instances/train/*.json")):
    d=json.load(open(f)); B=d["blocks"]; bays=d["bays"]; w=d["weights"]
    n=len(B); m=len(bays)
    baycap=sum(bb["width"]*bb["height"] for bb in bays)
    # time-congestion proxy: peak simultaneous footprint-area / total bay area
    events=[]
    for b in B:
        a=bbox_area(b["shape"][0])            # orient-0 bbox area (proxy)
        e=b["release_time"]; x=e+b["processing_time"]
        events.append((e,a)); events.append((x,-a))
    events.sort()
    cur=0; peak=0
    for t,da in events: cur+=da; peak=max(peak,cur)
    util=peak/baycap
    # structural tardiness: blocks with release+proc>due are ALWAYS tardy -> force Z1>0
    forced=sum(1 for b in B if b["release_time"]+b["processing_time"]>b["due_date"])
    ffrac=forced/max(1,n)
    name=os.path.basename(f)[:-5]
    rows.append((name,n,m,round(util,2),forced,round(ffrac,2),w["w1"]))
rows.sort(key=lambda r:r[5])
print(f"{'inst':9}{'n':>4}{'m':>3}{'util':>6}{'forced':>7}{'ffrac':>7}  regime")
for r in rows:
    reg="LOW-density (Z1~0)" if r[4]==0 else ("MODERATE high-density" if r[5]<0.3 else "HIGH-density")
    flag="  <-- experiment target" if 0<r[4] and r[5]<0.3 else ""
    print(f"{r[0]:9}{r[1]:>4}{r[2]:>3}{r[3]:>6}{r[4]:>7}{r[5]:>7}  {reg}{flag}")
