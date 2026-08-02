// cranepack: dependency-free exact-style crane packer.
//   input : a congested clique of blocks (per-orient layer polygons at origin,
//           obb, entry, exit) + bay W,H + coarse grid step.
//   build : step-grid placement columns -> pairwise crane-conflict graph
//           (fastconf j>=k rule, VALIDATED) -> maximise # distinct blocks placed.
//   solve : iterated-greedy + force/repair local search on the conflict graph
//           (no Gurobi; grader has no license).  Returns the chosen placements.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <vector>
#include <cmath>
#include <algorithm>
#include <chrono>
#include <cstdlib>
namespace py = pybind11;
typedef std::vector<std::pair<double,double>> Poly;

// ---------- geometry (from the validated cranecheck.cpp) ----------
static inline double cross(double ox,double oy,double ax,double ay,double bx,double by){
    return (ax-ox)*(by-oy)-(ay-oy)*(bx-ox);
}
static inline int point_in_poly(double px,double py,const Poly& poly,double eps=1e-9){
    int n=poly.size(); bool inside=false;
    for(int i=0,j=n-1;i<n;j=i++){
        double xi=poly[i].first,yi=poly[i].second,xj=poly[j].first,yj=poly[j].second;
        double d=cross(xi,yi,xj,yj,px,py);
        double minx=std::min(xi,xj)-eps,maxx=std::max(xi,xj)+eps;
        double miny=std::min(yi,yj)-eps,maxy=std::max(yi,yj)+eps;
        if(std::fabs(d)<eps && px>=minx&&px<=maxx&&py>=miny&&py<=maxy) return 0;
        if(((yi>py)!=(yj>py)) && (px<(xj-xi)*(py-yi)/(yj-yi)+xi)) inside=!inside;
    }
    return inside?1:-1;
}
static inline bool seg_cross_proper(double p0x,double p0y,double p1x,double p1y,
                                    double p2x,double p2y,double p3x,double p3y){
    double d1=cross(p2x,p2y,p3x,p3y,p0x,p0y),d2=cross(p2x,p2y,p3x,p3y,p1x,p1y);
    double d3=cross(p0x,p0y,p1x,p1y,p2x,p2y),d4=cross(p0x,p0y,p1x,p1y,p3x,p3y);
    return (((d1>0&&d2<0)||(d1<0&&d2>0))&&((d3>0&&d4<0)||(d3<0&&d4>0)));
}
static bool poly_overlap(const Poly& A,const Poly& B){
    for(auto&p:A) if(point_in_poly(p.first,p.second,B)==1) return true;
    for(auto&p:B) if(point_in_poly(p.first,p.second,A)==1) return true;
    int na=A.size(),nb=B.size();
    for(int i=0;i<na;i++){
        double p0x=A[i].first,p0y=A[i].second,p1x=A[(i+1)%na].first,p1y=A[(i+1)%na].second;
        for(int j=0;j<nb;j++)
            if(seg_cross_proper(p0x,p0y,p1x,p1y,B[j].first,B[j].second,B[(j+1)%nb].first,B[(j+1)%nb].second)) return true;
    }
    return false;
}

// ---------- placement column ----------
struct Col {
    int block, orient, x, y, entry, exit;
    std::vector<Poly> layers;             // world coords
    double bx0,by0,bx1,by1;
};
static void bbox_of(Col& c){
    c.bx0=1e18;c.by0=1e18;c.bx1=-1e18;c.by1=-1e18;
    for(auto&L:c.layers) for(auto&p:L){
        c.bx0=std::min(c.bx0,p.first);c.by0=std::min(c.by0,p.second);
        c.bx1=std::max(c.bx1,p.first);c.by1=std::max(c.by1,p.second);
    }
}

// crane conflict, fastconf j>=k logic (descent OR ascent => same A_k vs B_{j>k} loop)
static bool crane_conflict(const Col& A, const Col& B){
    if(!(A.entry < B.exit && B.entry < A.exit)) return false;         // time co-presence
    if(A.bx1<=B.bx0||B.bx1<=A.bx0||A.by1<=B.by0||B.by1<=A.by0) return false; // AABB
    int Ka=A.layers.size(), Kb=B.layers.size();
    int mk=std::min(Ka,Kb);
    for(int k=0;k<mk;k++){                                            // resting j==k
        if(A.layers[k].size()<3||B.layers[k].size()<3) continue;
        if(poly_overlap(A.layers[k],B.layers[k])) return true;
    }
    bool AoverB = (A.entry>=B.entry) || (A.exit<=B.exit);             // A sweeps B upper layers
    bool BoverA = (B.entry>=A.entry) || (B.exit<=A.exit);
    if(AoverB){
        for(int k=0;k<Ka;k++){
            if(A.layers[k].size()<3) continue;
            for(int j=k+1;j<Kb;j++){
                if(B.layers[j].size()<3) continue;
                if(poly_overlap(A.layers[k],B.layers[j])) return true;
            }
        }
    }
    if(BoverA){
        for(int k=0;k<Kb;k++){
            if(B.layers[k].size()<3) continue;
            for(int j=k+1;j<Ka;j++){
                if(A.layers[j].size()<3) continue;
                if(poly_overlap(B.layers[k],A.layers[j])) return true;
            }
        }
    }
    return false;
}

// ---------- rng ----------
struct Xorshift { uint64_t s;
    Xorshift(uint64_t seed):s(seed?seed:0x9e3779b97f4a7c15ULL){}
    uint64_t next(){ s^=s<<13; s^=s>>7; s^=s<<17; return s; }
    int randint(int n){ return (int)(next()% (uint64_t)n); }
};

// ---------- main entry ----------
// blocks: list of (orient_layers, obb, entry_exit_list)
//   orient_layers   : list over orients of list of (Nx2 float64) layer arrays at origin
//   obb             : list over orients of (x0,y0,x1,y1)
//   entry_exit_list : list of (entry,exit) time-variants (>=1); columns are generated
//                     for EVERY variant so the packer can re-time a block (low-density
//                     temporal slack lever).  "one column per block" still holds.
// warm : list of (block_idx, orient, x, y) greedy placements (may be off-grid; seeded)
// returns (best_count, [(block, orient, x, y)...], n_cols, n_edges, build_ms, solve_ms)
// total_s : optional deadline on BUILD + SEARCH together, measured from entry.  time_budget_s
// bounds only the search, so a caller that must not overrun has to PREDICT the build and
// subtract it -- and the prediction is a rate times ncol^2, which was 1.6x optimistic on P6
// (predicted 119 s, measured 213 s).  The build measures itself for free; letting it subtract
// itself removes the prediction from the budget entirely.  A mispredicted tier then costs
// search time, which is quality, instead of costing the deadline, which is the whole answer.
// Negative (the default) keeps the old meaning exactly, so every existing caller is unchanged.
py::tuple pack(py::list blocks, double W, double H, int step,
               double time_budget_s, uint64_t seed, py::object warm, py::object frozen,
               py::object weights, double total_s){
    auto t0=std::chrono::high_resolution_clock::now();
    int nblk = (int)py::len(blocks);

    // per-block objective weight (maximise Sum of placed weights).  Default all 1.0 ->
    // identical to max-cardinality.  Objective-aware VLNS repair passes real weights.
    std::vector<double> wt(nblk, 1.0);
    if(!weights.is_none()){
        int wi=0; for(auto v : py::cast<py::list>(weights)){ if(wi<nblk) wt[wi]=py::cast<double>(v); wi++; }
    }

    // parse per-block per-orient origin polygons + obb + entry/exit variants
    std::vector<std::vector<std::vector<Poly>>> BL(nblk); // [b][o] -> layers
    std::vector<std::vector<std::array<double,4>>> OBB(nblk);
    std::vector<std::vector<std::pair<int,int>>> ENT(nblk); // entry/exit variants
    for(int b=0;b<nblk;b++){
        py::tuple bt = py::cast<py::tuple>(blocks[b]);
        py::list orients = py::cast<py::list>(bt[0]);
        py::list obbs    = py::cast<py::list>(bt[1]);
        for(auto ee : py::cast<py::list>(bt[2])){
            py::tuple t=py::cast<py::tuple>(ee);
            ENT[b].push_back({py::cast<int>(t[0]),py::cast<int>(t[1])});
        }
        int no=(int)py::len(orients);
        BL[b].resize(no); OBB[b].resize(no);
        for(int o=0;o<no;o++){
            py::list layers=py::cast<py::list>(orients[o]);
            for(auto L : layers){
                py::array_t<double> arr=py::cast<py::array_t<double>>(L);
                auto a=arr.unchecked<2>(); Poly P;
                for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
                BL[b][o].push_back(P);
            }
            py::tuple ob=py::cast<py::tuple>(obbs[o]);
            OBB[b][o]={py::cast<double>(ob[0]),py::cast<double>(ob[1]),
                       py::cast<double>(ob[2]),py::cast<double>(ob[3])};
        }
    }

    // frozen obstacle blocks (fixed placements in the bay, WORLD coords + entry/exit).
    // Any generated column that crane-conflicts with a frozen block is dropped.
    std::vector<Col> froz;
    if(!frozen.is_none()){
        for(auto item : py::cast<py::list>(frozen)){
            py::tuple t=py::cast<py::tuple>(item);
            py::list layers=py::cast<py::list>(t[0]);
            Col c; c.block=-1;c.orient=-1;c.x=0;c.y=0;
            c.entry=py::cast<int>(t[1]); c.exit=py::cast<int>(t[2]);
            for(auto L : layers){
                py::array_t<double> arr=py::cast<py::array_t<double>>(L);
                auto a=arr.unchecked<2>(); Poly P;
                for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
                c.layers.push_back(std::move(P));
            }
            bbox_of(c); froz.push_back(std::move(c));
        }
    }

    // warm placements
    std::vector<std::array<int,4>> warmp; // block,orient,x,y
    if(!warm.is_none()){
        for(auto item : py::cast<py::list>(warm)){
            py::tuple t=py::cast<py::tuple>(item);
            warmp.push_back({py::cast<int>(t[0]),py::cast<int>(t[1]),
                             py::cast<int>(t[2]),py::cast<int>(t[3])});
        }
    }

    // ---- generate columns (coarse grid + warm positions) ----
    std::vector<Col> cols;
    std::vector<std::vector<int>> colsOfBlock(nblk);
    auto make_col=[&](int b,int o,int x,int y,int en,int ex){
        Col c; c.block=b;c.orient=o;c.x=x;c.y=y;c.entry=en;c.exit=ex;
        for(auto& P : BL[b][o]){
            Poly Q; Q.reserve(P.size());
            for(auto&p:P) Q.emplace_back(p.first+x,p.second+y);
            c.layers.push_back(std::move(Q));
        }
        bbox_of(c);
        for(const Col& f : froz) if(crane_conflict(c,f)) return;   // drop: hits an obstacle
        colsOfBlock[b].push_back((int)cols.size());
        cols.push_back(std::move(c));
    };
    for(int b=0;b<nblk;b++){
        for(int o=0;o<(int)BL[b].size();o++){
            double x0=OBB[b][o][0],y0=OBB[b][o][1],x1=OBB[b][o][2],y1=OBB[b][o][3];
            int xlo=(int)std::ceil(-x0), xhi=(int)std::floor(W-x1);
            int ylo=(int)std::ceil(-y0), yhi=(int)std::floor(H-y1);
            if(xlo>xhi||ylo>yhi) continue;
            std::vector<int> xs, ys;
            for(int x=xlo;x<=xhi;x+=step) xs.push_back(x);
            for(int y=ylo;y<=yhi;y+=step) ys.push_back(y);
            for(auto& wp : warmp) if(wp[0]==b&&wp[1]==o){
                if(wp[2]>=xlo&&wp[2]<=xhi) xs.push_back(wp[2]);
                if(wp[3]>=ylo&&wp[3]<=yhi) ys.push_back(wp[3]);
            }
            std::sort(xs.begin(),xs.end()); xs.erase(std::unique(xs.begin(),xs.end()),xs.end());
            std::sort(ys.begin(),ys.end()); ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
            for(int x:xs) for(int y:ys) for(auto& ee : ENT[b]) make_col(b,o,x,y,ee.first,ee.second);
        }
    }
    int ncol=(int)cols.size();

    // ---- pairwise conflict graph (only across different blocks) ----
    // THE BUILD WATCHES ITS OWN CLOCK.  This loop is the reason every caller had to predict:
    // it is O(ncol^2) and used to have no clock check at all, so an oversized pack could not be
    // cut short, only declined in advance.  Prediction is a rate times ncol^2, and the rate is
    // not a constant -- measured 6.25e-08 to 6.6e-08 at P3's 30k columns and 9.4e-08 to 1.4e-07
    // at P6's 44k-62k, rising with size, which reads as cache behaviour.  One number is
    // therefore always optimistic about the LARGEST tier, which is exactly the tier that can
    // cost a run its deadline: on P6 it predicted 249 s for a build that took 544 s.
    //
    // A loop that measures itself needs no rate.  After k outer iterations the pairs visited
    // are k*ncol - k*k/2 of a total ncol*ncol/2, so elapsed time scales to a projected total
    // directly.  If that projection exceeds what is left, stop: the caller gets abort=1 and
    // keeps what it had, which costs the fraction already spent instead of the whole overrun.
    // Checked every 256 rows, so the clock read is amortised to nothing.
    std::vector<std::vector<int>> adj(ncol);
    long nedge=0;
    bool aborted=false;
    const double build_cap = (total_s > 0.0) ? total_s : -1.0;
    const double total_pairs = 0.5*(double)ncol*(double)ncol;
    for(int a=0;a<ncol;a++){
        if(build_cap > 0.0 && (a & 255) == 255){
            double el = std::chrono::duration<double>(
                            std::chrono::high_resolution_clock::now()-t0).count();
            double done = (double)a*(double)ncol - 0.5*(double)a*(double)a;
            if(done > 1.0){
                double projected = el * total_pairs / done;
                // leave room for the search: a build that would consume the entire cap has
                // already lost, and finishing it only turns a cheap decline into a costly one.
                if(projected > build_cap){ aborted=true; break; }
            }
        }
        const Col& ca=cols[a];
        for(int b=a+1;b<ncol;b++){
            const Col& cb=cols[b];
            if(ca.block==cb.block) continue;                 // same-block handled by blockUsed
            if(ca.bx1<=cb.bx0||cb.bx1<=ca.bx0||ca.by1<=cb.by0||cb.by1<=ca.by0) continue;
            if(!(ca.entry<cb.exit&&cb.entry<ca.exit)) continue;
            if(crane_conflict(ca,cb)){ adj[a].push_back(b); adj[b].push_back(a); nedge++; }
        }
    }
    for(auto& v:adj) std::sort(v.begin(),v.end());
    auto t1=std::chrono::high_resolution_clock::now();
    double build_ms=std::chrono::duration<double,std::milli>(t1-t0).count();

    // ---- MIS heuristic: maximise distinct blocks placed ----
    // state: sel[b] = chosen column for block b or -1 ; selected columns list.
    // compatibility of col c against current selection = no adj neighbour selected.
    // Fast neighbour-in-selection test via per-column "blocked" counter.
    Xorshift rng(seed);
    std::vector<int> sel(nblk,-1);       // working
    std::vector<int> blocked(ncol,0);    // #selected columns conflicting with this col
    std::vector<char> selflag(ncol,0);

    // FREE-COLUMN BITSET.  greedy_extend below picks, per block, the first column with
    // blocked==0 -- by scanning that block's whole column list from the start.  Counted on P3:
    // the search performs 12,791,335,136 of those reads in 35 s, against the 26,924,021 pair
    // tests the build does in 50 s.  The build was profiled today and hardened three ways; the
    // SEARCH had never been looked at, and it is doing 475x more work.
    //
    // One bit per column, grouped by block, set exactly when blocked[c]==0.  It is maintained
    // in add_col/rem_col on the 0<->1 transitions only, inside loops that already walk adj[c],
    // so the maintenance is free asymptotically.  Finding a free column becomes a
    // count-trailing-zeros over ~7 words instead of up to 404 array reads.
    //
    // Bit i of a block's range is colsOfBlock[b][i], so find-first-set returns the SAME column
    // the scan would have returned.  Behaviour is identical, not merely equivalent.
    // CRANEPACK_NOBITS=1 restores the scan for A/B.
    static const bool USEBITS=[](){const char*e=getenv("CRANEPACK_NOBITS");return !(e&&e[0]=='1');}();
    std::vector<int> bitBase(nblk,0), bitPos(ncol,0);
    int totw=0;
    for(int b=0;b<nblk;b++){
        bitBase[b]=totw;
        for(size_t i=0;i<colsOfBlock[b].size();i++) bitPos[colsOfBlock[b][i]]=(int)i;
        totw += ((int)colsOfBlock[b].size()+63)/64;
    }
    std::vector<uint64_t> freeb(std::max(1,totw),0ULL);
    auto bit_set=[&](int c){ int b=cols[c].block,i=bitPos[c];
                             freeb[bitBase[b]+(i>>6)] |= (1ULL<<(i&63)); };
    auto bit_clr=[&](int c){ int b=cols[c].block,i=bitPos[c];
                             freeb[bitBase[b]+(i>>6)] &= ~(1ULL<<(i&63)); };
    if(USEBITS) for(int c=0;c<ncol;c++) if(blocked[c]==0) bit_set(c);

    auto add_col=[&](int c){
        int b=cols[c].block; sel[b]=c; selflag[c]=1;
        if(USEBITS){ for(int nb2:adj[c]){ if(blocked[nb2]++==0) bit_clr(nb2); } }
        else       { for(int nb2:adj[c]) blocked[nb2]++; }
    };
    auto rem_col=[&](int c){
        int b=cols[c].block; sel[b]=-1; selflag[c]=0;
        if(USEBITS){ for(int nb2:adj[c]){ if(--blocked[nb2]==0) bit_set(nb2); } }
        else       { for(int nb2:adj[c]) blocked[nb2]--; }
    };
    auto clear_all=[&](){
        for(int b=0;b<nblk;b++) if(sel[b]>=0) rem_col(sel[b]);
    };
    auto count_sel=[&](){ int c2=0; for(int b=0;b<nblk;b++) if(sel[b]>=0) c2++; return c2; };
    auto wsel=[&](){ double s=0; for(int b=0;b<nblk;b++) if(sel[b]>=0) s+=wt[b]; return s; };

    // greedily extend current selection using a given block order; within a block
    // pick the first column with blocked==0.
    auto greedy_extend=[&](const std::vector<int>& border){
        for(int b:border){
            if(sel[b]>=0) continue;
            if(USEBITS){
                int nw=((int)colsOfBlock[b].size()+63)/64, base=bitBase[b], found=-1;
                for(int w=0;w<nw && found<0;w++){
                    uint64_t v=freeb[base+w];
                    if(v) found=(w<<6)+__builtin_ctzll(v);
                }
                if(found>=0 && found<(int)colsOfBlock[b].size()) add_col(colsOfBlock[b][found]);
            } else {
                for(int c:colsOfBlock[b]) if(blocked[c]==0){ add_col(c); break; }
            }
        }
    };

    std::vector<int> border(nblk); for(int b=0;b<nblk;b++) border[b]=b;
    // weight-priority order (exploit): high-weight blocks placed first
    std::vector<int> worder(nblk); for(int b=0;b<nblk;b++) worder[b]=b;
    std::sort(worder.begin(),worder.end(),[&](int a,int b){ return wt[a]>wt[b]; });

    // (2,1)-swap: remove one selected column s, add TWO freed columns from distinct
    // unplaced blocks that don't conflict with each other -> net +1 block.  Canonical
    // MIS improvement; escapes the 9-basin that force/repair alone cannot.  Returns
    // true if it improved (applied one swap).
    // weight-improving swaps around one selected column s (block bs, weight w_s):
    //  (1,1): replace s with a single freed column of a heavier block  (w_b' > w_s)
    //  (2,1): remove s, add TWO freed columns from distinct blocks with w1+w2 > w_s
    // With unit weights (1,1) never fires and (2,1) reduces to the +1-count MIS swap.
    auto try_swap=[&]()->bool{
        for(int b=0;b<nblk;b++){
            int s=sel[b]; if(s<0) continue;
            double ws=wt[b];
            std::vector<int> freed;
            for(int c:adj[s]) if(!selflag[c] && blocked[c]==1 && sel[cols[c].block]<0) freed.push_back(c);
            int nf=(int)freed.size();
            if(nf==0) continue;
            // (1,1): a single heavier freed block
            for(int i=0;i<nf;i++){
                int c1=freed[i]; if(wt[cols[c1].block] > ws + 1e-9){ rem_col(s); add_col(c1); return true; }
            }
            if(nf<2) continue;
            // (2,1): two freed from distinct blocks, non-conflicting, combined weight > w_s
            for(int i=0;i<nf;i++){
                int c1=freed[i], b1=cols[c1].block;
                for(int k=i+1;k<nf;k++){
                    int c2=freed[k]; if(cols[c2].block==b1) continue;
                    if(wt[b1]+wt[cols[c2].block] <= ws + 1e-9) continue;
                    if(std::binary_search(adj[c1].begin(),adj[c1].end(),c2)) continue;
                    rem_col(s); add_col(c1); add_col(c2);
                    return true;
                }
            }
        }
        return false;
    };
    // (k,1) GUIDED EJECTION.  Every move in try_swap removes exactly ONE selected column, and
    // the candidates it will even look at are restricted to blocked[c]==1 -- columns blocked by
    // that single column alone.  A column blocked by TWO selected columns is unreachable from
    // either of them, so wherever seating a block needs two or more evictions the entire
    // neighbourhood is empty, whatever the weights say.
    //
    // Measured on P3: the same 55 residents seated and ZERO outsiders admitted under three
    // different weightings (single-move deltas, directed-wish deltas, and exact linearised
    // coefficients), while the single-eviction neighbourhood had separately been found
    // exhausted.  Three weightings agreeing to the block is not a weighting problem.
    //
    // The force loop below does eject-all-conflicts, so this is not a new capability -- but it
    // picks the block and the column at RANDOM, which is a lottery over hundreds of columns
    // rather than a move.  This is the same thing guided: for each unplaced block, for each of
    // its columns, eject every selected column conflicting with it and accept only if the block
    // outweighs everything it displaced.  The weight test bounds the work, since accumulation
    // stops the moment it exceeds the gain, and it also guarantees termination: every accepted
    // move strictly increases the selected weight, which is bounded above.
    //
    // Refilling afterwards can only add weight, never remove it, so acceptance stays monotone.
    std::vector<int> ejbuf;
    const bool EJECT = [](){ const char* e=std::getenv("CRANEPACK_EJECT"); return e && e[0]=='1'; }();
    auto try_eject=[&]()->bool{
        for(int b=0;b<nblk;b++){
            if(sel[b]>=0) continue;
            double wb=wt[b];
            if(wb<=1e-9) continue;
            for(int c:colsOfBlock[b]){
                if(blocked[c]==0) continue;       // greedy_extend already seats these
                double cost=0.0; bool ok=true;
                ejbuf.clear();
                for(int d:adj[c]){
                    if(!selflag[d]) continue;
                    ejbuf.push_back(d);
                    cost+=wt[cols[d].block];
                    if(cost>=wb-1e-9){ ok=false; break; }
                }
                if(!ok||ejbuf.empty()) continue;
                for(int d:ejbuf) rem_col(d);
                add_col(c);
                greedy_extend(worder);            // the eviction may have freed room for others
                return true;
            }
        }
        return false;
    };
    auto local_opt=[&](){ for(;;){ if(try_swap()) continue;
                                   if(EJECT && try_eject()) continue;
                                   break; } };

    // best (tracked by total WEIGHT; `best` reports the block count of that selection)
    std::vector<int> best_sel(nblk,-1); int best=0; double bestw=-1e18;
    auto save_if_better=[&](){ double cw=wsel(); if(cw>bestw+1e-9){ bestw=cw; best_sel=sel; best=count_sel(); } return cw; };

    // seed 1: warm placement (map warm to nearest generated column of same b,o,x,y)
    if(!warmp.empty()){
        clear_all();
        for(auto&wp:warmp){
            int b=wp[0]; int want=-1;
            for(int c:colsOfBlock[b]) if(cols[c].orient==wp[1]&&cols[c].x==wp[2]&&cols[c].y==wp[3]){want=c;break;}
            if(want>=0 && sel[b]<0 && blocked[want]==0) add_col(want);
        }
        greedy_extend(border);
        save_if_better();
    }

    // seed 2..: randomized greedy constructions
    // main loop: iterated force/repair local search on the incumbent.
    auto now_s=[&](){ auto t=std::chrono::high_resolution_clock::now();
                      return std::chrono::duration<double>(t-t1).count(); };
    // now_s() runs from t1, i.e. AFTER the build, so a total deadline is just the total minus
    // what the build already spent.  Clamped at zero: an oversized tier returns the warm start
    // rather than borrowing time it does not have.
    const double search_budget = aborted ? 0.0
        : ((total_s > 0.0) ? std::max(0.0, total_s - build_ms / 1000.0)
                           : time_budget_s);
    int since_improve=0;
    // ensure we hold a working selection = current best (or a fresh greedy)
    auto load_best=[&](){ clear_all();
        for(int b=0;b<nblk;b++) if(best_sel[b]>=0){ int c=best_sel[b]; if(blocked[c]==0) add_col(c);} };

    // exploit seed: weight-priority greedy (place heaviest blocks first)
    clear_all(); greedy_extend(worder); local_opt(); save_if_better();
    // Full-cardinality is provably optimal: no selection can place more than nblk
    // blocks, and with non-negative weights placing every block maximises weight too.
    // So once best==nblk we can stop immediately -- this saves the wasted tail of every
    // SUCCESSFUL pack (the common case in the low-density relocator, where success ==
    // "all of F+b fit").  Correctness-preserving; only skips search that cannot improve.
    // initial random restarts (each hardened with the swap local opt) to get incumbent
    for(int it=0; it<200 && now_s()<search_budget && best<nblk; it++){
        clear_all();
        for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
        greedy_extend(border);
        local_opt();
        save_if_better();
    }
    load_best();

    // iterated local search: force a random excluded block in (kick conflicts), repair.
    while(now_s()<search_budget && best<nblk){
        // snapshot current working weight
        double before=wsel();
        // pick a random excluded block that has at least one column
        int tries=0, pick=-1;
        while(tries++<2*nblk){
            int b=rng.randint(nblk);
            if(sel[b]<0 && !colsOfBlock[b].empty()){ pick=b; break; }
        }
        if(pick<0){
            // fully placed everything placeable; perturb by random restart
            clear_all();
            for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
            greedy_extend(border);
            if(wsel()>=before-1e-9) save_if_better(); else load_best();
            continue;
        }
        // choose a random column of that block, kick out selected conflicts, add it
        int c = colsOfBlock[pick][ rng.randint((int)colsOfBlock[pick].size()) ];
        // remove selected columns adjacent to c
        for(int nb2:adj[c]) if(selflag[nb2]) rem_col(nb2);
        add_col(c);
        // repair greedily with random order, then harden with (2,1)-swap local opt
        for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
        greedy_extend(border);
        local_opt();
        double after=wsel();
        if(after>=before-1e-9){ save_if_better(); }  // accept equal/better (plateau walk)
        else { load_best(); since_improve++; }
        if(after>before+1e-9) since_improve=0;
        // occasional full restart to diversify
        if(since_improve>500){
            clear_all();
            for(int i=nblk-1;i>0;i--){ int j=rng.randint(i+1); std::swap(border[i],border[j]); }
            greedy_extend(border);
            local_opt();
            save_if_better(); load_best(); since_improve=0;
        }
    }
    auto t2=std::chrono::high_resolution_clock::now();
    double solve_ms=std::chrono::duration<double,std::milli>(t2-t1).count();

    py::list placements;
    for(int b=0;b<nblk;b++) if(best_sel[b]>=0){
        const Col& c=cols[best_sel[b]];
        placements.append(py::make_tuple(c.block,c.orient,c.x,c.y,c.entry,c.exit));
    }

    // export graph for an exact solver (Gurobi): column descriptors + edges + warm-set.
    py::array_t<int> coldesc({(py::ssize_t)ncol,(py::ssize_t)6});
    { auto r=coldesc.mutable_unchecked<2>();
      for(int c=0;c<ncol;c++){ r(c,0)=cols[c].block;r(c,1)=cols[c].orient;r(c,2)=cols[c].x;
                               r(c,3)=cols[c].y;r(c,4)=cols[c].entry;r(c,5)=cols[c].exit; } }
    py::array_t<int> edges({(py::ssize_t)nedge,(py::ssize_t)2});
    { auto r=edges.mutable_unchecked<2>(); long e=0;
      for(int a=0;a<ncol;a++) for(int nb2:adj[a]) if(nb2>a){ r(e,0)=a;r(e,1)=nb2;e++; } }
    py::list warmcols;  // column indices chosen by the heuristic (per-block)
    for(int b=0;b<nblk;b++) if(best_sel[b]>=0) warmcols.append(best_sel[b]);

    return py::make_tuple(best, placements, ncol, (long)nedge, build_ms, solve_ms,
                          coldesc, edges, warmcols, aborted ? 1 : 0);
}

// ================= C++ VLNS refiner (whole SLS loop in C++) =================
// Precomputes block geometry once, then runs the window-repack stochastic local search
// (SA on the Z2+Z3 assignment objective) entirely in C++ -- no per-iteration Python
// overhead -> several x more iterations in the same wall time.  Returns the best
// assignment by the internal objective; Python re-verifies it with the grader (falls
// back to the warm if the rare geometry mismatch makes it infeasible -> never-worse).
struct BGeom {
    std::vector<std::vector<Poly>> ol;      // [orient][layer] at origin
    std::vector<std::array<double,4>> obb;  // [orient] (x0,y0,x1,y1)
    int release, proc, due;
    std::vector<double> prefs;              // per bay
    double maxpref, workload;
};

py::tuple refine(py::list blocks, py::list baydims, py::list bayunit,
                 double w2, double w3, py::list init, double budget_s, uint64_t seed,
                 int WIN, int NPULL, int STEP){
    auto T0 = std::chrono::high_resolution_clock::now();
    int nblk = (int)py::len(blocks);
    int m = (int)py::len(baydims);
    std::vector<BGeom> G(nblk);
    for(int b=0;b<nblk;b++){
        py::tuple bt = py::cast<py::tuple>(blocks[b]);
        py::list orients = py::cast<py::list>(bt[0]);
        py::list obbs    = py::cast<py::list>(bt[1]);
        G[b].release=py::cast<int>(bt[2]); G[b].proc=py::cast<int>(bt[3]); G[b].due=py::cast<int>(bt[4]);
        for(auto p : py::cast<py::list>(bt[5])) G[b].prefs.push_back(py::cast<double>(p));
        G[b].workload=py::cast<double>(bt[6]);
        G[b].maxpref=*std::max_element(G[b].prefs.begin(),G[b].prefs.end());
        int no=(int)py::len(orients);
        G[b].ol.resize(no); G[b].obb.resize(no);
        for(int o=0;o<no;o++){
            for(auto L : py::cast<py::list>(orients[o])){
                py::array_t<double> arr=py::cast<py::array_t<double>>(L);
                auto a=arr.unchecked<2>(); Poly P;
                for(py::ssize_t i=0;i<a.shape(0);i++) P.emplace_back(a(i,0),a(i,1));
                G[b].ol[o].push_back(std::move(P));
            }
            py::tuple ob=py::cast<py::tuple>(obbs[o]);
            G[b].obb[o]={py::cast<double>(ob[0]),py::cast<double>(ob[1]),py::cast<double>(ob[2]),py::cast<double>(ob[3])};
        }
    }
    std::vector<std::pair<double,double>> BD(m);
    std::vector<double> BU(m);
    for(int j=0;j<m;j++){ py::tuple t=py::cast<py::tuple>(baydims[j]); BD[j]={py::cast<double>(t[0]),py::cast<double>(t[1])}; BU[j]=py::cast<double>(bayunit[j]); }
    // assignment: [bay,orient,x,y,entry,exit]
    std::vector<std::array<int,6>> A(nblk);
    for(int b=0;b<nblk;b++){ py::tuple t=py::cast<py::tuple>(init[b]);
        for(int k=0;k<6;k++) A[b][k]=py::cast<int>(t[k]); }

    // world Col for a placement (single layer set)
    auto world_col=[&](int b,int o,int x,int y,int en,int ex)->Col{
        Col c; c.block=b;c.orient=o;c.x=x;c.y=y;c.entry=en;c.exit=ex;
        for(auto& P : G[b].ol[o]){ Poly Q; Q.reserve(P.size());
            for(auto&p:P) Q.emplace_back(p.first+x,p.second+y); c.layers.push_back(std::move(Q)); }
        bbox_of(c); return c;
    };
    auto obj_assign=[&](const std::vector<std::array<int,6>>& AA)->double{
        std::vector<double> load(m,0.0); double z3=0;
        for(int b=0;b<nblk;b++){ int j=AA[b][0]; load[j]+=G[b].workload; z3+=G[b].maxpref-G[b].prefs[j]; }
        double mx=-1e18,mn=1e18;
        for(int j=0;j<m;j++){ double v=BU[j]*load[j]; mx=std::max(mx,v); mn=std::min(mn,v); }
        return w2*std::floor(mx-mn)+w3*z3;
    };
    Xorshift rng(seed);

    // pack a window: place a max-preference-weighted subset of `cand` (global block ids)
    // into bay J, avoiding `frozen` obstacle cols.  Returns chosen placement per cand
    // (o,x,y,en,ex); cand not in the map were dropped.  single_entry=release.
    auto ent_cands=[&](int b, std::vector<std::pair<int,int>>& out){
        int lo=G[b].release, hi=G[b].due-G[b].proc;
        auto add=[&](int t){ if(t>=0 && t+G[b].proc<=G[b].due) out.push_back({t,t+G[b].proc}); };
        if(hi<=lo){ add(lo); return; }
        std::set<int> ts; for(int k=0;k<3;k++) ts.insert(lo+((hi-lo)*k)/2);
        for(int t:ts) add(t);
    };
    auto pack_window=[&](int J,const std::vector<int>& cand,const std::vector<Col>& frozen,
                         std::map<int,std::array<int,5>>& out, bool multi_entry=false, int step=-1)->void{
        if(step<0) step=STEP;
        double W=BD[J].first, H=BD[J].second;
        std::vector<Col> cols; std::vector<int> colblk; // block-local idx
        std::vector<double> wt(cand.size());
        std::map<int,int> g2l; for(size_t i=0;i<cand.size();i++){ g2l[cand[i]]=(int)i; wt[i]=G[cand[i]].prefs[J]; }
        for(size_t li=0; li<cand.size(); li++){
            int b=cand[li];
            std::vector<std::pair<int,int>> ees;
            if(multi_entry) ent_cands(b,ees); else { int en=G[b].release; if(en+G[b].proc<=G[b].due) ees.push_back({en,en+G[b].proc}); }
            if(ees.empty()) continue;
            for(int o=0;o<(int)G[b].ol.size();o++){
                double x0=G[b].obb[o][0],y0=G[b].obb[o][1],x1=G[b].obb[o][2],y1=G[b].obb[o][3];
                int xlo=(int)std::ceil(-x0),xhi=(int)std::floor(W-x1),ylo=(int)std::ceil(-y0),yhi=(int)std::floor(H-y1);
                if(xlo>xhi||ylo>yhi) continue;
                for(int x=xlo;x<=xhi;x+=step) for(int y=ylo;y<=yhi;y+=step) for(auto&ee:ees){
                    Col c=world_col(b,o,x,y,ee.first,ee.second);
                    bool bad=false; for(const Col& f:frozen){ if(crane_conflict(c,f)){bad=true;break;} }
                    if(bad) continue;
                    colblk.push_back((int)li); cols.push_back(std::move(c));
                }
            }
        }
        int nc=(int)cols.size(); if(nc==0) return;
        std::vector<std::vector<int>> adj(nc);
        for(int a=0;a<nc;a++) for(int b2=a+1;b2<nc;b2++){
            if(colblk[a]==colblk[b2]) continue;
            const Col&ca=cols[a],&cb=cols[b2];
            if(ca.bx1<=cb.bx0||cb.bx1<=ca.bx0||ca.by1<=cb.by0||cb.by1<=ca.by0) continue;
            if(!(ca.entry<cb.exit&&cb.entry<ca.exit)) continue;
            if(crane_conflict(ca,cb)){ adj[a].push_back(b2); adj[b2].push_back(a); }
        }
        for(auto&v:adj) std::sort(v.begin(),v.end());
        int L=(int)cand.size();
        std::vector<std::vector<int>> colsOf(L);
        for(int c=0;c<nc;c++) colsOf[colblk[c]].push_back(c);
        // max-weight MIS: iterated greedy (weight-desc) + (1,1)/(2,1) swaps + restarts
        std::vector<int> sel(L,-1); std::vector<int> blocked(nc,0); std::vector<char> sf(nc,0);
        auto addc=[&](int c){ sel[colblk[c]]=c; sf[c]=1; for(int nb:adj[c]) blocked[nb]++; };
        auto remc=[&](int c){ sel[colblk[c]]=-1; sf[c]=0; for(int nb:adj[c]) blocked[nb]--; };
        auto clr=[&](){ for(int l=0;l<L;l++) if(sel[l]>=0) remc(sel[l]); };
        auto wsel=[&](){ double s=0; for(int l=0;l<L;l++) if(sel[l]>=0) s+=wt[l]; return s; };
        std::vector<int> ord(L); for(int l=0;l<L;l++) ord[l]=l;
        std::sort(ord.begin(),ord.end(),[&](int a,int b){return wt[a]>wt[b];});
        auto greedy=[&](const std::vector<int>& o2){ for(int l:o2){ if(sel[l]>=0) continue; for(int c:colsOf[l]) if(blocked[c]==0){addc(c);break;} } };
        auto swap1=[&]()->bool{ for(int l=0;l<L;l++){ int s=sel[l]; if(s<0)continue; double ws=wt[l];
            std::vector<int> fr; for(int c:adj[s]) if(!sf[c]&&blocked[c]==1&&sel[colblk[c]]<0) fr.push_back(c);
            for(int c1:fr) if(wt[colblk[c1]]>ws+1e-9){ remc(s); addc(c1); return true; }
            for(size_t i=0;i<fr.size();i++) for(size_t k=i+1;k<fr.size();k++){ int c1=fr[i],c2=fr[k];
                if(colblk[c1]==colblk[c2]) continue; if(wt[colblk[c1]]+wt[colblk[c2]]<=ws+1e-9) continue;
                if(std::binary_search(adj[c1].begin(),adj[c1].end(),c2)) continue; remc(s); addc(c1); addc(c2); return true; } }
            return false; };
        auto lopt=[&](){ while(swap1()){} };
        std::vector<int> best_sel(L,-1); double bw=-1e18;
        auto save=[&](){ double cw=wsel(); if(cw>bw+1e-9){bw=cw; best_sel=sel;} };
        clr(); greedy(ord); lopt(); save();
        for(int it=0; it<60; it++){ clr();
            for(int i=L-1;i>0;i--){int j=(int)(rng.next()%(i+1)); std::swap(ord[i],ord[j]);}
            greedy(ord); lopt(); save(); }
        // force/repair (pack()'s optimum-reaching loop): kick an excluded block in,
        // remove its conflicts, repair -> escapes MIS local optima the swaps can't.
        auto load_best=[&](){ clr(); for(int l=0;l<L;l++) if(best_sel[l]>=0){int c=best_sel[l]; if(blocked[c]==0) addc(c);} };
        load_best(); int since=0;
        for(int it=0; it<120; it++){
            double before=wsel(); int pick=-1,tr=0;
            while(tr++<2*L){ int l=(int)(rng.next()%L); if(sel[l]<0&&!colsOf[l].empty()){pick=l;break;} }
            if(pick<0){ clr(); for(int i=L-1;i>0;i--){int j=(int)(rng.next()%(i+1));std::swap(ord[i],ord[j]);} greedy(ord); lopt();
                        if(wsel()>=before-1e-9) save(); else load_best(); continue; }
            int c=colsOf[pick][rng.next()%colsOf[pick].size()];
            for(int nb:adj[c]) if(sf[nb]) remc(nb);
            addc(c);
            for(int i=L-1;i>0;i--){int j=(int)(rng.next()%(i+1));std::swap(ord[i],ord[j]);} greedy(ord); lopt();
            double after=wsel();
            if(after>=before-1e-9) save(); else { load_best(); since++; }
            if(after>before+1e-9) since=0;
            if(since>50){ clr(); for(int i=L-1;i>0;i--){int j=(int)(rng.next()%(i+1));std::swap(ord[i],ord[j]);} greedy(ord); lopt(); save(); load_best(); since=0; }
        }
        for(int l=0;l<L;l++) if(best_sel[l]>=0){ const Col&c=cols[best_sel[l]];
            out[cand[l]]={c.orient,c.x,c.y,c.entry,c.exit}; }
    };

    // fallback: place bumped block b into best OTHER crane-feasible bay (freeze that bay)
    auto fallback=[&](const std::vector<std::array<int,6>>& AA,int b,int avoid,std::array<int,6>& res)->bool{
        std::vector<int> order; for(int j=0;j<m;j++) if(j!=avoid) order.push_back(j);
        std::sort(order.begin(),order.end(),[&](int p,int q){return G[b].prefs[p]>G[b].prefs[q];});
        for(int J:order){ std::vector<Col> froz;
            for(int x=0;x<nblk;x++) if(x!=b&&AA[x][0]==J) froz.push_back(world_col(x,AA[x][1],AA[x][2],AA[x][3],AA[x][4],AA[x][5]));
            std::vector<int> cand{b}; std::map<int,std::array<int,5>> out; pack_window(J,cand,froz,out);
            auto it=out.find(b); if(it!=out.end()){ res={J,it->second[0],it->second[1],it->second[2],it->second[3],it->second[4]}; return true; } }
        return false;
    };

    // one window-repack move on AA (in place); returns true if a valid trial was produced.
    auto window_repack=[&](std::vector<std::array<int,6>>& AA)->bool{
        std::vector<int> cbays; for(int j=0;j<m;j++){ int cnt=0; for(int b=0;b<nblk;b++) if(AA[b][0]==j)cnt++; if(cnt>=2)cbays.push_back(j); }
        if(cbays.empty()) return false;
        int J=cbays[rng.next()%cbays.size()];
        std::vector<int> inbay; for(int b=0;b<nblk;b++) if(AA[b][0]==J) inbay.push_back(b);
        int sb=inbay[rng.next()%inbay.size()]; int st=AA[sb][4];
        std::sort(inbay.begin(),inbay.end(),[&](int a,int b){return std::abs(AA[a][4]-st)<std::abs(AA[b][4]-st);});
        std::vector<int> window(inbay.begin(), inbay.begin()+std::min((int)inbay.size(),WIN));
        std::vector<int> pull; for(int b=0;b<nblk;b++) if(AA[b][0]!=J && G[b].prefs[J]>G[b].prefs[AA[b][0]]) pull.push_back(b);
        for(int i=(int)pull.size()-1;i>0;i--){int j=(int)(rng.next()%(i+1)); std::swap(pull[i],pull[j]);}
        for(int i=0;i<std::min((int)pull.size(),NPULL);i++) window.push_back(pull[i]);
        std::set<int> wset(window.begin(),window.end());
        std::vector<Col> frozen; for(int b:inbay) if(!wset.count(b)) frozen.push_back(world_col(b,AA[b][1],AA[b][2],AA[b][3],AA[b][4],AA[b][5]));
        std::map<int,std::array<int,5>> placed; pack_window(J,window,frozen,placed,true); // multi-entry
        if(placed.empty()) return false;
        // apply to AA
        for(auto& kv:placed){ int b=kv.first; AA[b]={J,kv.second[0],kv.second[1],kv.second[2],kv.second[3],kv.second[4]}; }
        // bumped: in inbay∩window but not placed -> fallback
        for(int b:window){ bool wasIn=wset.count(b)&&std::find(inbay.begin(),inbay.end(),b)!=inbay.end();
            if(wasIn && !placed.count(b)){ std::array<int,6> res; if(!fallback(AA,b,J,res)) return false; AA[b]=res; } }
        return true;
    };

    auto elapsed=[&](){ return std::chrono::duration<double>(std::chrono::high_resolution_clock::now()-T0).count(); };

    // descent move: pull spilled block b into preferred bay J by freeing FREE time-
    // neighbours and requiring ALL of {F, b} to crane-fit (aggressive insertion the
    // gentle window-repack cannot make).  Applies to AA in place; true if it fit all.
    auto try_insert=[&](std::vector<std::array<int,6>>& AA,int b,int J,int FREE)->bool{
        std::vector<int> inbay; for(int x=0;x<nblk;x++) if(x!=b&&AA[x][0]==J) inbay.push_back(x);
        int rb=G[b].release, db=G[b].due;
        std::vector<int> Fall; for(int x:inbay){ int ex=AA[x][5],en=AA[x][4]; if(!(ex<=rb||db<=en)) Fall.push_back(x); }
        std::sort(Fall.begin(),Fall.end(),[&](int p,int q){return std::abs(AA[p][4]-rb)<std::abs(AA[q][4]-rb);});
        std::vector<int> F(Fall.begin(), Fall.begin()+std::min((int)Fall.size(),FREE));
        std::set<int> Fs(F.begin(),F.end());
        std::vector<Col> frozen; for(int x:inbay) if(!Fs.count(x)) frozen.push_back(world_col(x,AA[x][1],AA[x][2],AA[x][3],AA[x][4],AA[x][5]));
        std::vector<int> cand=F; cand.push_back(b);
        std::map<int,std::array<int,5>> placed; pack_window(J,cand,frozen,placed,true,6); // multi-entry, fine grid
        if((int)placed.size()!=(int)cand.size()) return false;   // could not fit all
        for(auto& kv:placed){ int bb=kv.first; AA[bb]={J,kv.second[0],kv.second[1],kv.second[2],kv.second[3],kv.second[4]}; }
        return true;
    };

    // ---- phase 1: descent (systematic spilled-block relocation) ----
    {
        double curo=obj_assign(A); double dl=budget_s*0.45;
        for(int pass=0; pass<6 && elapsed()<dl; pass++){
            std::vector<int> cands; for(int b=0;b<nblk;b++) if(G[b].prefs[A[b][0]]<G[b].maxpref) cands.push_back(b);
            std::sort(cands.begin(),cands.end(),[&](int p,int q){return (G[p].maxpref-G[p].prefs[A[p][0]])>(G[q].maxpref-G[q].prefs[A[q][0]]);});
            int moved=0;
            for(int b:cands){ if(elapsed()>dl) break; int j=A[b][0];
                std::vector<int> tg; for(int jt=0;jt<m;jt++) if(G[b].prefs[jt]>G[b].prefs[j]) tg.push_back(jt);
                std::sort(tg.begin(),tg.end(),[&](int p,int q){return G[b].prefs[p]>G[b].prefs[q];});
                for(int jt:tg){ std::vector<std::array<int,6>> snap=A;
                    if(try_insert(A,b,jt,10)){ double no=obj_assign(A); if(no<curo-1e-6){curo=no;moved++;break;} else A=snap; }
                    else A=snap; } }
            if(moved==0) break;
        }
    }

    // ruin-recreate kick: re-home k blocks (spilled-biased) to their best feasible bay
    // -> jump basins when window-repack stalls.
    auto ruin_recreate=[&](std::vector<std::array<int,6>>& AA,int k){
        std::vector<int> pool; for(int b=0;b<nblk;b++) if(G[b].prefs[AA[b][0]]<G[b].maxpref) pool.push_back(b);
        if(pool.empty()) for(int b=0;b<nblk;b++) pool.push_back(b);
        for(int i=(int)pool.size()-1;i>0;i--){int j=(int)(rng.next()%(i+1)); std::swap(pool[i],pool[j]);}
        int kk=std::min(k,(int)pool.size());
        for(int i=0;i<kk;i++){ int b=pool[i]; std::array<int,6> res; if(fallback(AA,b,-1,res)) AA[b]=res; }
    };

    std::vector<std::array<int,6>> best=A, cur=A;
    double bestobj=obj_assign(A), curobj=bestobj;
    double Temp=std::max(1.0,bestobj*0.01); int stall=0; long iters=0;
    while(elapsed()<budget_s){
        iters++;
        std::vector<std::array<int,6>> trial=cur; bool ok;
        if(stall>=25){ ruin_recreate(trial, 6+(int)(rng.next()%11)); ok=true; stall=0; }
        else ok=window_repack(trial);
        if(!ok) continue;
        double tobj=obj_assign(trial); double d=tobj-curobj;
        if(d<-1e-6 || (double)(rng.next()%1000000)/1000000.0 < std::exp(-d/std::max(1e-9,Temp))){
            cur.swap(trial); curobj=tobj;
            if(curobj<bestobj-1e-6){ best=cur; bestobj=curobj; stall=0; } else stall++;
        } else stall++;
        Temp*=0.997;
        if(stall>0 && stall%60==0){ cur=best; curobj=bestobj; }
    }
    py::list outA;
    for(int b=0;b<nblk;b++){ auto&a=best[b]; outA.append(py::make_tuple(a[0],a[1],a[2],a[3],a[4],a[5])); }
    return py::make_tuple(bestobj, outA, iters);
}

PYBIND11_MODULE(cranepack,m){
    m.def("refine",&refine,
          py::arg("blocks"),py::arg("baydims"),py::arg("bayunit"),
          py::arg("w2"),py::arg("w3"),py::arg("init"),py::arg("budget_s"),
          py::arg("seed")=7,py::arg("WIN")=6,py::arg("NPULL")=2,py::arg("STEP")=8);
    m.def("pack",&pack,
          py::arg("blocks"),py::arg("W"),py::arg("H"),py::arg("step"),
          py::arg("time_budget_s"),py::arg("seed")=12345,py::arg("warm")=py::none(),
          py::arg("frozen")=py::none(),py::arg("weights")=py::none(),
          py::arg("total_s")=-1.0);
}
