"""cranepack-oracle Very Large Neighborhood Search for the LOW-DENSITY assignment.

Master decision = block->bay assignment (Z2+Z3 objective).  Sub-oracle = cranepack:
decides per-bay crane feasibility AND realises placements, and (weighted) picks the
best subset to keep when a bay is over-subscribed.

VLNS move = reopt_bay(J): empty bay J's would-be pool (its current blocks + blocks
elsewhere that PREFER J), let cranepack pick the max-preference-weighted subset that
crane-fits in J; bumped blocks relocate to a feasible fallback bay.  Every trial is
gated on the exact grader objective (never-worse best).  Order/bay perturbation + SA
acceptance give the metaheuristic its diversification."""
import json, os, sys, time, math, copy, random
SP="/tmp/claude-0/-home-user-oraclemaster/55043662-747d-5eda-b837-388adc057292/scratchpad"
sys.path.insert(0, os.path.join(SP,"v72")); sys.path.insert(0, os.path.join(SP,"cc"))
os.chdir(os.path.join(SP,"v72"))
import numpy as np, myalgorithm as M
from utils import check_feasibility
import cranepack as CP

def find(n):
    for sub in ("data/training_instances/train","data/train"):
        p=os.path.join(SP,sub,n+".json")
        if os.path.exists(p): return p

class Engine:
    def __init__(self, inst, STEP=6, TLpack=0.2):
        self.inst=inst; self.B=inst["blocks"]; self.bays=inst["bays"]
        self.n=len(self.B); self.m=len(self.bays)
        self.w=inst["weights"]; self.w2=self.w["w2"]; self.w3=self.w["w3"]
        self.bu=M._bay_unit_weights(self.bays)
        self.rel=[b["release_time"] for b in self.B]
        self.pt=[b["processing_time"] for b in self.B]
        self.due=[b["due_date"] for b in self.B]
        self.mxp=[max(b["bay_preferences"]) for b in self.B]
        self.prefs=[b["bay_preferences"] for b in self.B]
        self.wl=[b["workload"] for b in self.B]
        self.STEP=STEP; self.TLpack=TLpack
        self._olc={}; self._obc={}

    def ols(self,bid):
        if bid not in self._olc:
            self._olc[bid]=[[np.ascontiguousarray(np.asarray(L,dtype=np.float64))
                             for L in M.Block(block_id=bid,block_data=self.B[bid],x=0,y=0,orient_idx=o).layers_at_pos()]
                            for o in range(len(self.B[bid]["shape"]))]
            self._obc[bid]=[tuple(float(v) for v in M._orient_bbox(self.B[bid],o))
                            for o in range(len(self.B[bid]["shape"]))]
        return self._olc[bid], self._obc[bid]
    def world(self,bid,o,x,y):
        return [np.ascontiguousarray(np.asarray(L,dtype=np.float64))
                for L in M.Block(block_id=bid,block_data=self.B[bid],x=x,y=y,orient_idx=o).layers_at_pos()]

    def ent_cands(self,b):
        lo=self.rel[b]; hi=self.due[b]-self.pt[b]
        if hi<=lo: return [lo] if (lo>=0 and lo+self.pt[b]<=self.due[b]) else []
        cs=sorted(set(lo+((hi-lo)*k)//2 for k in range(3)))
        return [t for t in cs if t>=0 and t+self.pt[b]<=self.due[b]]

    def score(self, assign):
        sol=M._build_operations([{"block_id":b,"bay_id":a[0],"orient_idx":a[1],
                                  "x":a[2],"y":a[3],"entry_time":a[4],"exit_time":a[5]}
                                 for b,a in assign.items()])
        ck=check_feasibility(self.inst,sol)
        return (ck["objective"] if ck["feasible"] else float("inf")), ck["feasible"]

    def obj_assign(self, assign):
        """fast internal Z2+Z3 (low-density, Z1=0) from bay assignment only."""
        load=[0.0]*self.m; z3=0.0
        for b,a in assign.items():
            j=a[0]; load[j]+=self.wl[b]; z3+=self.mxp[b]-self.prefs[b][j]
        vals=[self.bu[j]*load[j] for j in range(self.m)]
        return self.w2*math.floor(max(vals)-min(vals))+self.w3*z3

    def cp_place(self, J, cand, frozen_place, weights, seed, step=None, single_entry=False, tl=None):
        """cranepack: place max-weight subset of `cand` blocks in bay J, `frozen_place`
        = list of (bid,o,x,y,en,ex) fixed obstacles.  Returns {b:(o,x,y,en,ex)}.
        step/single_entry/tl let the metaheuristic use a coarser+cheaper repack."""
        W=self.bays[J]["width"]; H=self.bays[J]["height"]
        blocks_in=[]
        for b in cand:
            if single_entry:
                en=self.rel[b]
                if en+self.pt[b]>self.due[b]: return None
                ee=[(en,en+self.pt[b])]
            else:
                ee=[(e,e+self.pt[b]) for e in self.ent_cands(b)]
                if not ee: return None
            ol,ob=self.ols(b); blocks_in.append((ol,ob,ee))
        froz=[(self.world(bid,o,x,y),int(en),int(ex)) for (bid,o,x,y,en,ex) in frozen_place]
        res=CP.pack(blocks_in,float(W),float(H), step or self.STEP, tl or self.TLpack,
                    seed=seed,warm=None,frozen=froz,weights=[float(x) for x in weights])
        pl=res[1]
        return {cand[loc]:(o,x,y,int(en),int(ex)) for (loc,o,x,y,en,ex) in pl}

    def fallback_bay(self, assign, b, avoid, seed):
        """place bumped block b into its best OTHER crane-feasible bay (keep current
        bay contents frozen).  Returns (J,o,x,y,en,ex) or None."""
        order=sorted([j for j in range(self.m) if j!=avoid], key=lambda j:-self.prefs[b][j])
        for J in order:
            inbay=[(x,assign[x]) for x in assign if x!=b and assign[x][0]==J]
            froz=[(x, a[1],a[2],a[3],a[4],a[5]) for (x,a) in inbay]
            got=self.cp_place(J,[b],froz,[1.0],seed,step=8,single_entry=True,tl=0.05)
            if got and b in got:
                o,x,y,en,ex=got[b]; return (J,o,x,y,en,ex)
        return None

    def reopt_bay(self, assign, J, seed, allow_bump=True):
        """VLNS move: repack bay J from (its blocks + blocks preferring J).  cranepack
        picks the max-preference-weighted crane-fitting subset; bumped current-J blocks
        relocate to a fallback bay.  Returns a trial assignment (feasible) or None."""
        curJ=[b for b in assign if assign[b][0]==J]
        pull=[b for b in assign if assign[b][0]!=J and self.prefs[b][J]>self.prefs[b][assign[b][0]]]
        if allow_bump:
            cand=curJ+pull; froz=[]
        else:
            cand=pull; froz=[(b,)+tuple(assign[b][1:]) for b in curJ]  # keep curJ frozen
        if not cand: return None
        weights=[float(self.prefs[b][J]) for b in cand]
        placed=self.cp_place(J,cand,froz,weights,seed)
        if placed is None: return None
        trial=copy.deepcopy(assign)
        for b,(o,x,y,en,ex) in placed.items(): trial[b]=(J,o,x,y,en,ex)
        # bumped current-J blocks (allow_bump path) must relocate elsewhere
        bumped=[b for b in curJ if b not in placed]
        for b in bumped:
            fb=self.fallback_bay(trial,b,J,seed)
            if fb is None: return None      # could not re-home -> move invalid
            trial[b]=fb
        return trial

    # ---- descent = the validated cranepack FREE~10 relocator (M._z3_relocate_cp) ----
    def _to_dict(self, assign):
        return {b:{"block_id":b,"bay_id":a[0],"orient_idx":a[1],"x":a[2],"y":a[3],
                   "entry_time":a[4],"exit_time":a[5]} for b,a in assign.items()}
    def _to_tuple(self, dassign):
        return {b:(a["bay_id"],a["orient_idx"],a["x"],a["y"],int(a["entry_time"]),int(a["exit_time"]))
                for b,a in dassign.items()}
    def descent(self, assign, budget, FREE=10):
        da=M._z3_relocate_cp(self.inst, self._to_dict(assign), self.bu,
                             time.time()+budget, FREE=FREE, STEP=self.STEP, TLpack=self.TLpack)
        return self._to_tuple(da)

    def ruin_recreate(self, assign, k, rng, seed):
        """LNS perturbation: remove k blocks (biased to preference-violators) and
        cranepack-reinsert them (random pref order) into a feasible bay -> a diverse but
        feasible complete assignment."""
        trial=copy.deepcopy(assign)
        # pick k removal targets: prefer blocks paying Z3 (spilled), plus some random
        spilled=[b for b in trial if self.prefs[b][trial[b][0]]<self.mxp[b]]
        pool=spilled if spilled else list(trial.keys())
        rng.shuffle(pool)
        victims=pool[:k]
        for b in victims: del trial[b]
        # reinsert in random order, each into its best feasible bay (cranepack single-insert)
        rng.shuffle(victims)
        for b in victims:
            order=sorted(range(self.m), key=lambda j:-self.prefs[b][j])
            placed=False
            for J in order:
                inbay=[(x,trial[x]) for x in trial if trial[x][0]==J]
                froz=[(x,a[1],a[2],a[3],a[4],a[5]) for (x,a) in inbay]
                got=self.cp_place(J,[b],froz,[1.0],seed)
                if got and b in got:
                    o,x,y,en,ex=got[b]; trial[b]=(J,o,x,y,int(en),int(ex)); placed=True; break
            if not placed:
                trial[b]=assign[b]   # revert this block if nowhere fits
        return trial

    def window_repack(self, assign, rng, seed, WIN=6, npull=2, step=8):
        """ONE cranepack call.  Take bay J, a WIN-sized time-window of its blocks + a few
        spilled blocks preferring J; cranepack keeps the max-PREFERENCE-weighted subset
        (may DROP a low-pref block and ADD a high-pref/pulled one -> rearrangement, the
        move a sequential insert descent cannot make).  Dropped-from-J blocks relocate to
        a fallback bay.  Returns a feasible trial or None."""
        cand_bays=[j for j in range(self.m) if sum(1 for b in assign if assign[b][0]==j)>=2]
        if not cand_bays: return None
        J=rng.choice(cand_bays)
        inbay=[x for x in assign if assign[x][0]==J]
        seed_b=rng.choice(inbay)
        st=assign[seed_b][4]
        window=sorted(inbay,key=lambda x:abs(assign[x][4]-st))[:WIN]
        pull=[b for b in assign if assign[b][0]!=J and self.prefs[b][J]>self.prefs[b][assign[b][0]]]
        rng.shuffle(pull); window=window+pull[:npull]
        wset=set(window)
        frozen=[(x,)+tuple(assign[x][1:]) for x in inbay if x not in wset]
        weights=[float(self.prefs[b][J]) for b in window]
        se=os.environ.get("VLNS_SINGLE_ENTRY","1")=="1"
        placed=self.cp_place(J,window,frozen,weights,seed,step=step,single_entry=se,tl=0.06)
        if placed is None: return None
        trial=copy.deepcopy(assign)
        for b,(o,x,y,en,ex) in placed.items(): trial[b]=(J,o,x,y,int(en),int(ex))
        dropped=[b for b in window if b in inbay and b not in placed]  # ejected from J
        for b in dropped:
            fb=self.fallback_bay(trial,b,J,seed)
            if fb is None: return None
            trial[b]=fb
        return trial

    def solve(self, deadline, init_assign, seed=12345, descent0=10.0):
        rng=random.Random(seed)
        # one-time strong descent to reach the good basin, then FAST window-repack SLS
        cur=self.descent(init_assign, min(descent0, (deadline-time.time())*0.4))
        cobj=self.obj_assign(cur)
        best=copy.deepcopy(cur); bobj=cobj
        bfeasobj=self.score(best)[0]
        it=0; acc=0; improved=0; nmove=0; stall=0
        T=max(1.0, bobj*0.01)
        while time.time()<deadline-1.5:
            it+=1
            sd=(seed*2654435761 + it) & 0x7fffffff
            # basin diversity: after a stall, a BIG ruin-recreate kick (jump basins);
            # otherwise the cheap window-repack local move.
            if stall>=25:
                k=rng.randint(6,16)
                trial=self.ruin_recreate(cur, k, rng, sd)
                stall=0
            else:
                trial=self.window_repack(cur, rng, sd)   # ONE cranepack call (+few fallbacks)
            if trial is None: continue
            nmove+=1
            tobj=self.obj_assign(trial)                  # FAST proxy for the SA walk
            d=tobj-cobj
            if d<-1e-6 or rng.random()<math.exp(-d/max(1e-9,T)):
                cur=trial; cobj=tobj; acc+=1
                if cobj<bobj-1e-6:
                    ro,rf=self.score(trial)              # verify with the grader
                    if rf and ro<bfeasobj-1e-6:
                        best=copy.deepcopy(trial); bobj=cobj; bfeasobj=ro; improved+=1
                    stall=0
                else: stall+=1
            else: stall+=1
            T*=0.997
            # re-anchor to best occasionally so kicks explore around the incumbent
            if stall>0 and stall%60==0:
                cur=copy.deepcopy(best); cobj=bobj
        return best, bfeasobj, True, it, acc, improved

# --------------- driver ---------------
if __name__=="__main__":
    NAME=sys.argv[1] if len(sys.argv)>1 else "prob_20"
    SEEDT=float(sys.argv[2]) if len(sys.argv)>2 else 12.0
    VLNST=float(sys.argv[3]) if len(sys.argv)>3 else 20.0
    MODE=os.environ.get("VLNS_MODE","feedback")   # one warm per run (parallel-worker sim)
    inst=json.load(open(find(NAME)))
    E=Engine(inst)
    t0=time.time()
    res=M._exact_reassign(inst,E.bu,time.time()+SEEDT,mip_cap=6.0,mode=MODE)
    if not(res and res[0]):
        print(f"{NAME}: no warm ({MODE})"); sys.exit(0)
    init={b:(a["bay_id"],a["orient_idx"],a["x"],a["y"],int(a["entry_time"]),int(a["exit_time"]))
          for b,a in {b:dict(v) for b,v in res[0].items()}.items()}
    o0,f0=E.score(init)
    tb=time.time()
    best,fo,ff,it,acc,imp=E.solve(time.time()+VLNST, init, seed=7)
    print(f"{NAME}[{MODE}]: warm={o0:.0f} -> VLNS={fo:.0f} feas={ff} iters={it} acc={acc} imp={imp} [{time.time()-t0:.1f}s]")
