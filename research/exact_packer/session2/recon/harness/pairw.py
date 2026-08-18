import re, sys, glob, collections
# Pair every arm against the control cell of the SAME instance in the SAME log,
# worker by worker.  Between-run variance cancels; the knob's own effect does not.
rows=[]
for f in glob.glob("results/audit/*.log"):
    tag=None; w=None
    for ln in open(f, errors="replace"):
        m=re.match(r"# \[(.+)\]", ln)
        if m: tag=m.group(1); w=None; continue
        if ln.startswith("WSTAT round=0"):
            v=[int(x) for x in re.findall(r"\b\d{4,}\b", ln)]
            w=v if len(v)==4 else None; continue
        m=re.match(r"(P\d+) +\[(.+?)\]", ln)
        if m and w:
            rows.append((f, m.group(1), m.group(2), w)); w=None
ctrl=re.compile(r"(^|\.)(off|base|plain|ship)(\.|$)")
by=collections.defaultdict(dict)
for f,p,t,w in rows:
    key=(f,p); by[key][t]=w
out=collections.Counter(); tot=collections.Counter()
for (f,p),cells in by.items():
    cs=[t for t in cells if ctrl.search(t)]
    if not cs: continue
    base=cells[cs[0]]
    for t,w in cells.items():
        if t in cs: continue
        arm=re.sub(r"^(r\d+|g|n|s|h|p\d+)\.","",t)
        arm=re.sub(r"\.p?\d+$","",arm)
        for i in range(4):
            tot[arm]+=1
            if w[i]<base[i]*0.995: out[arm]+=1
            elif w[i]>base[i]*1.005: out[arm]-=1
print("%-22s %6s %8s   net wins over control, paired by worker" % ("arm","pairs","net"))
for a,n in sorted(tot.items(), key=lambda kv:-kv[1]):
    if n>=8: print("%-22s %6d %+8d   %+.0f%%" % (a,n,out[a],100.0*out[a]/n))
