// ogc_fast: RECONSTRUCTED engine (crane-descent packing + placement search).
// Geometry + crane-descent feasibility are lifted verbatim from the verified
// ogc_state source (classify: segment-cross + point-in-poly, c==1 == positive-area
// overlap matching shapely area>0; c==0 boundary-touch == feasible).  On top of that
// this adds find_best_placement (tardiness/pref/bottom-left scored) and a conservative
// integer-cell RASTER bitmask that fast-rejects clearly-disjoint layer pairs before the
// exact classify (never under-marks -> identical feasibility, ~3x fewer classify calls).
// API surface matches the shipped ogc_fast.so that myalgorithm.py calls:
//   init(nbays,W,H,unit) reserve_blocks register_block(+meta) add remove clear_all
//   placement_feasible(bay,bid,orient,x,y,en,ex) find_best_placement(bid,bays,ets)
//   set_nfp_provider (stored; candidate gen here is NFP-free grid+corner scan)
// env: RASTER (default on), GRIDDIV (default 4).
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>
#include <tuple>
#include <algorithm>
#include <functional>
#include <chrono>
#include <array>
#include <climits>
#include <map>
namespace py = pybind11;
static double GRID_DIV = [](){ const char* e=std::getenv("GRIDDIV"); return e? atof(e):4.0; }();

static const double EPS = 1e-9;
// TOUCH: how close to contact a placement may sit before the engine calls it a collision.
//
// The grader rejects any overlap with `inter.area > 0` and allows no tolerance at all.  The
// predicates below used to carry an EPS=1e-9 deadzone in the other direction: proper_cross
// ignored sign changes smaller than EPS, and pip treated a point on the boundary as
// OUTSIDE and returned early, skipping the ray cast entirely.
//
// On randomly sampled placements that costs nothing -- 200k pairs on prob_29, every one
// agreeing with shapely, 0 missed overlaps and 0 false ones.  The beam is not random,
// though: it scores candidates by CONTACT, so it hunts for exactly the grazing
// configurations the deadzone mishandles.  prob_29 block 90 @(40,13) o1 against block 143
// @(43,16) o5 measures 9.13e-16 of intersection under shapely on all four layer pairs and
// the old predicate called every one of them clear.  That is the whole reason prob_29 and
// prob_35 came back grader-infeasible -- not budget, not the bitmap prefilter.
//
// So the deadzone is removed rather than widened.  At TOUCH=0 proper_cross accepts any true
// sign change however small, and a point resting on the boundary counts as inside; the test
// is sound with the least conservatism available.  Widening it only throws away legal tight
// placements: on the same 200k pairs the count of contacts wrongly called collisions goes
// 1138 -> 1542 (1e-9) -> 1568 (1e-4), and prob_29's objective goes 657828 -> 1104088 at
// 1e-4.  env OGC_TOUCH overrides for that sweep.
static const double TOUCH = [](){ const char* e=std::getenv("OGC_TOUCH"); return e? atof(e):0.0; }();
static inline double orient_(double ax,double ay,double bx,double by,double px,double py){
    return (bx-ax)*(py-ay)-(by-ay)*(px-ax);
}
static inline bool on_seg(double ax,double ay,double bx,double by,double px,double py){
    if(px<std::min(ax,bx)-EPS||px>std::max(ax,bx)+EPS) return false;
    if(py<std::min(ay,by)-EPS||py>std::max(ay,by)+EPS) return false;
    return true;
}
static inline bool proper_cross(double ax,double ay,double bx,double by,double cx,double cy,double dx,double dy){
    double d1=orient_(cx,cy,dx,dy,ax,ay),d2=orient_(cx,cy,dx,dy,bx,by);
    double d3=orient_(ax,ay,bx,by,cx,cy),d4=orient_(ax,ay,bx,by,dx,dy);
    // -TOUCH rather than +EPS: no deadzone, so a grazing sign change still counts as a
    // crossing instead of being rounded away into "clear".
    const double m = -TOUCH;
    return (((d1>m&&d2<-m)||(d1<-m&&d2>m))&&((d3>m&&d4<-m)||(d3<-m&&d4>m)));
}
static bool pip(double px,double py,const double* poly,int n,double ox,double oy){
    for(int i=0;i<n;i++){
        double ax=poly[2*i]+ox,ay=poly[2*i+1]+oy; int ni=(i+1)%n;
        double bx=poly[2*ni]+ox,by=poly[2*ni+1]+oy;
        double o=orient_(ax,ay,bx,by,px,py);
        // a point resting ON the boundary counts as INSIDE now.  It used to return false
        // here, which not only excluded the boundary but abandoned the ray cast below, so
        // a vertex grazing one edge hid the fact that it was interior to the polygon.
        if(std::fabs(o)<=TOUCH&&on_seg(ax,ay,bx,by,px,py)) return true;
    }
    bool inside=false;int j=n-1;
    for(int i=0;i<n;i++){
        double yi=poly[2*i+1]+oy,yj=poly[2*j+1]+oy,xi=poly[2*i]+ox,xj=poly[2*j]+ox;
        if((yi>py)!=(yj>py)){double xint=(xj-xi)*(py-yi)/(yj-yi)+xi; if(px<xint)inside=!inside;}
        j=i;
    }
    return inside;
}
// 0=disjoint/touch, 1=positive-area overlap, 2=bbox-separate
static int classify(const double* A,int na,double aox,double aoy,
                    const double* B,int nb,double box,double boy){
    if(na<3||nb<3) return 2;
    double axmin=A[0]+aox,axmax=axmin,aymin=A[1]+aoy,aymax=aymin;
    for(int i=1;i<na;i++){double x=A[2*i]+aox,y=A[2*i+1]+aoy;
        if(x<axmin)axmin=x;if(x>axmax)axmax=x;if(y<aymin)aymin=y;if(y>aymax)aymax=y;}
    double bxmin=B[0]+box,bxmax=bxmin,bymin=B[1]+boy,bymax=bymin;
    for(int i=1;i<nb;i++){double x=B[2*i]+box,y=B[2*i+1]+boy;
        if(x<bxmin)bxmin=x;if(x>bxmax)bxmax=x;if(y<bymin)bymin=y;if(y>bymax)bymax=y;}
    if(!(axmin<bxmax&&bxmin<axmax&&aymin<bymax&&bymin<aymax)) return 2;
    for(int i=0;i<na;i++){
        double ax=A[2*i]+aox,ay=A[2*i+1]+aoy; int ni=(i+1)%na;
        double bx=A[2*ni]+aox,by=A[2*ni+1]+aoy;
        for(int k=0;k<nb;k++){
            double cx=B[2*k]+box,cy=B[2*k+1]+boy; int nk=(k+1)%nb;
            double dx=B[2*nk]+box,dy=B[2*nk+1]+boy;
            if(proper_cross(ax,ay,bx,by,cx,cy,dx,dy)) return 1;
        }
    }
    for(int i=0;i<na;i++) if(pip(A[2*i]+aox,A[2*i+1]+aoy,B,nb,box,boy)) return 1;
    for(int k=0;k<nb;k++) if(pip(B[2*k]+box,B[2*k+1]+boy,A,na,aox,aoy)) return 1;
    // containment/identity degenerate: vertices lie on the boundary and no edge
    // properly crosses, yet interiors coincide.  Centroids are interior for convex
    // layers; pure edge-touching keeps both centroids outside -> stays 0.
    {   double cax=0,cay=0; for(int i=0;i<na;i++){cax+=A[2*i]+aox;cay+=A[2*i+1]+aoy;} cax/=na;cay/=na;
        if(pip(cax,cay,B,nb,box,boy)) return 1;
        double cbx=0,cby=0; for(int i=0;i<nb;i++){cbx+=B[2*i]+box;cby+=B[2*i+1]+boy;} cbx/=nb;cby/=nb;
        if(pip(cbx,cby,A,na,aox,aoy)) return 1;
    }
    return 0;
}

static bool RASTER = [](){ const char* e=std::getenv("RASTER"); return e ? (e[0]=='1') : true; }();

// segment (x1,y1)-(x2,y2) intersects the closed unit cell [cx,cx+1]x[cy,cy+1]?
static bool seg_hits_cell(double x1,double y1,double x2,double y2,double cx,double cy){
    double lo=cx,hi=cx+1.0,bo=cy,to=cy+1.0;
    if(x1>=lo&&x1<=hi&&y1>=bo&&y1<=to) return true;
    if(x2>=lo&&x2<=hi&&y2>=bo&&y2<=to) return true;
    double dx=x2-x1, dy=y2-y1; double t0=0.0,t1=1.0;
    double p[4]={-dx,dx,-dy,dy}, q[4]={x1-lo,hi-x1,y1-bo,to-y1};
    for(int i=0;i<4;i++){
        if(std::fabs(p[i])<1e-12){ if(q[i]<0) return false; }
        else{ double r=q[i]/p[i];
            if(p[i]<0){ if(r>t1) return false; if(r>t0) t0=r; }
            else{ if(r<t0) return false; if(r<t1) t1=r; } }
    }
    return t0<=t1;
}

struct LayerData {
    std::vector<double> pts; int npts;
    // conservative cell raster (never under-marks): bit(r,c) set if the polygon
    // touches unit cell (cx0+c, cy0+r).  Fast disjoint-proof pre-filter.
    // bits_in: TIGHT interior raster (cell CENTER strictly inside the polygon only, no
    // edge-touch).  Two interior rasters overlap ~iff the polygons share positive area,
    // so it matches the grader's area>0 rule -- used by the approx rollout so that touching
    // (zero-gap) placements are NOT falsely forbidden.
    int cx0=0,cy0=0,cw=0,ch=0,wpr=0; std::vector<uint64_t> bits, bits_in;
    void rasterize(){
        if(npts<3){ cw=ch=0; return; }
        double mnx=pts[0],mny=pts[1],mxx=pts[0],mxy=pts[1];
        for(int i=1;i<npts;i++){double x=pts[2*i],y=pts[2*i+1];
            if(x<mnx)mnx=x;if(x>mxx)mxx=x;if(y<mny)mny=y;if(y>mxy)mxy=y;}
        cx0=(int)std::floor(mnx); cy0=(int)std::floor(mny);
        cw=(int)std::ceil(mxx)-cx0; ch=(int)std::ceil(mxy)-cy0;
        if(cw<=0)cw=1; if(ch<=0)ch=1; wpr=(cw+63)>>6;
        bits.assign((size_t)ch*wpr,0ULL);
        bits_in.assign((size_t)ch*wpr,0ULL);
        for(int r=0;r<ch;r++){int wy=cy0+r;
            for(int c=0;c<cw;c++){int wx=cx0+c; bool hit=false;
                double ccx=wx+0.5, ccy=wy+0.5;
                bool inside=false;
                { int j=npts-1;
                  for(int i=0;i<npts;i++){double yi=pts[2*i+1],yj=pts[2*j+1],xi=pts[2*i],xj=pts[2*j];
                    if((yi>ccy)!=(yj>ccy)){double xint=(xj-xi)*(ccy-yi)/(yj-yi)+xi; if(ccx<xint)inside=!inside;} j=i;}
                  if(inside) hit=true; }
                if(inside) bits_in[(size_t)r*wpr+(c>>6)] |= (1ULL<<(c&63));
                if(!hit){ for(int i=0;i<npts&&!hit;i++){int ni=(i+1)%npts;
                    if(seg_hits_cell(pts[2*i],pts[2*i+1],pts[2*ni],pts[2*ni+1],wx,wy)) hit=true; } }
                if(hit) bits[(size_t)r*wpr+(c>>6)] |= (1ULL<<(c&63));
            }
        }
    }
};
// two rasterized layers overlap at integer placements (aox,aoy),(box,boy)?
static bool bmp_overlap(const LayerData& A,int aox,int aoy,const LayerData& B,int box,int boy){
    if(A.cw==0||B.cw==0) return true; // no raster -> don't reject
    int Ax0=aox+A.cx0, Ay0=aoy+A.cy0, Bx0=box+B.cx0, By0=boy+B.cy0;
    int rlo=std::max(Ay0,By0), rhi=std::min(Ay0+A.ch,By0+B.ch); if(rlo>=rhi) return false;
    int clo=std::max(Ax0,Bx0), chi=std::min(Ax0+A.cw,Bx0+B.cw); if(clo>=chi) return false;
    int d = Ax0 - Bx0; // B local col for A local col ca is (ca+d)
    for(int wr=rlo;wr<rhi;wr++){
        const uint64_t* Ar=&A.bits[(size_t)(wr-Ay0)*A.wpr];
        for(int w=0;w<A.wpr;w++){
            uint64_t aw=Ar[w]; if(!aw) continue;
            long sB=(long)(w*64)+d;
            long wi=sB>>6; int off=(int)(sB&63); if(sB<0){wi=-((-sB+63)>>6); off=(int)((sB%64+64)%64);}
            uint64_t bw=0;
            if(wi>=0 && wi<B.wpr) bw |= (B.bits[(size_t)(wr-By0)*B.wpr+wi] >> off);
            if(off && (wi+1)>=0 && (wi+1)<B.wpr) bw |= (B.bits[(size_t)(wr-By0)*B.wpr+wi+1] << (64-off));
            if(aw & bw) return true;
        }
    }
    return false;
}

struct OrientData { std::vector<LayerData> layers; double x0,y0,x1,y1; };
struct BlockShape {
    std::vector<OrientData> orients;
    double workload=0,due=0,pt=0,rt=0;
    std::vector<double> prefs;
};
struct Placed { int en,ex,bid,orient; double ox,oy,bx0,by0,bx1,by1; int bay; };

static bool SWEEP = [](){ const char* e=std::getenv("SWEEP"); return e ? (e[0]=='1') : false; }();

// OR rasterized layer L (world integer position wox,woy) into a bay-grid bitmap
// F (bayH rows, wpr uint64 words per row, world col 0 == bit 0).
static void or_layer_into_map(std::vector<uint64_t>& F,int wpr,int bayH,
                              const LayerData& L,int wox,int woy,bool interior=false){
    if(L.cw==0) return;
    const std::vector<uint64_t>& Lb = interior ? L.bits_in : L.bits;
    long colbase=(long)wox+L.cx0;
    for(int r=0;r<L.ch;r++){
        int Y=woy+L.cy0+r; if(Y<0||Y>=bayH) continue;
        const uint64_t* Lr=&Lb[(size_t)r*L.wpr]; uint64_t* Fr=&F[(size_t)Y*wpr];
        for(int lw=0;lw<L.wpr;lw++){
            uint64_t v=Lr[lw]; if(!v) continue;
            long bit0=colbase+(long)lw*64;
            long wi=bit0>>6; int off=(int)((bit0%64+64)%64); if(bit0<0&&off) wi=-(((-bit0)+63)>>6);
            if(off==0){ if(wi>=0&&wi<wpr) Fr[wi]|=v; }
            else{ if(wi>=0&&wi<wpr) Fr[wi]|=(v<<off);
                  if((wi+1)>=0&&(wi+1)<wpr) Fr[wi+1]|=(v>>(64-off)); }
        }
    }
}
// does rasterized layer L (world wox,woy) overlap bay-grid bitmap F?
static bool layer_hits_map(const std::vector<uint64_t>& F,int wpr,int bayH,
                           const LayerData& L,int wox,int woy,bool interior=false){
    if(L.cw==0) return true;
    const std::vector<uint64_t>& Lb = interior ? L.bits_in : L.bits;
    long colbase=(long)wox+L.cx0;
    for(int r=0;r<L.ch;r++){
        int Y=woy+L.cy0+r; if(Y<0||Y>=bayH) continue;
        const uint64_t* Lr=&Lb[(size_t)r*L.wpr]; const uint64_t* Fr=&F[(size_t)Y*wpr];
        for(int lw=0;lw<L.wpr;lw++){
            uint64_t v=Lr[lw]; if(!v) continue;
            long bit0=colbase+(long)lw*64;
            long wi=bit0>>6; int off=(int)((bit0%64+64)%64); if(bit0<0&&off) wi=-(((-bit0)+63)>>6);
            uint64_t fw=0;
            if(wi>=0&&wi<wpr) fw|=(Fr[wi]>>off);
            if(off&&(wi+1)>=0&&(wi+1)<wpr) fw|=(Fr[wi+1]<<(64-off));
            if(v&fw) return true;
        }
    }
    return false;
}

struct Engine {
    std::vector<BlockShape> shapes;
    std::vector<std::vector<Placed>> timeline;
    int n_bays=0;
    std::vector<double> bw,bh,unit;
    std::function<py::object(int,int,int,int)> nfp_provider;

    void init(int nb, std::vector<double> w, std::vector<double> h, std::vector<double> u){
        n_bays=nb; bw=w; bh=h; unit=u; timeline.assign(nb,{});
    }
    void reserve_blocks(int n){ if((int)shapes.size()<n) shapes.resize(n); }
    void set_nfp_provider(std::function<py::object(int,int,int,int)> f){ nfp_provider=f; }

    void register_block(int bid, py::list orients_layers,
                        double workload,double due,double pt,double rt,std::vector<double> prefs){
        if((int)shapes.size()<=bid) shapes.resize(bid+1);
        BlockShape bs; bs.workload=workload; bs.due=due; bs.pt=pt; bs.rt=rt; bs.prefs=prefs;
        for(auto o : orients_layers){
            OrientData od; double x0=1e18,y0=1e18,x1=-1e18,y1=-1e18;
            for(auto layer : o.cast<py::list>()){
                auto arr=layer.cast<py::array_t<double,py::array::c_style|py::array::forcecast>>();
                LayerData ld; ld.npts=(int)arr.shape(0);
                const double* p=arr.data(); ld.pts.assign(p,p+2*ld.npts);
                for(int i=0;i<ld.npts;i++){double x=ld.pts[2*i],y=ld.pts[2*i+1];
                    if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}
                ld.rasterize();
                od.layers.push_back(std::move(ld));
            }
            od.x0=x0;od.y0=y0;od.x1=x1;od.y1=y1;
            bs.orients.push_back(std::move(od));
        }
        shapes[bid]=std::move(bs);
    }
    std::vector<double> compute_bbox(int bid,int orient,double ox,double oy){
        const OrientData& od=shapes[bid].orients[orient];
        return {od.x0+ox,od.y0+oy,od.x1+ox,od.y1+oy};
    }
    void add(int bay,int bid,int orient,double ox,double oy,int en,int ex){
        const OrientData& od=shapes[bid].orients[orient];
        timeline[bay].push_back({en,ex,bid,orient,ox,oy,od.x0+ox,od.y0+oy,od.x1+ox,od.y1+oy,bay});
    }
    void remove(int bid){
        for(int b=0;b<n_bays;b++){auto&tl=timeline[b];
            for(size_t i=0;i<tl.size();i++) if(tl[i].bid==bid){tl.erase(tl.begin()+i); return;}}
    }
    void clear_all(){ for(int b=0;b<n_bays;b++) timeline[b].clear(); }

    static inline bool bb_ov(double a0,double a1,double a2,double a3,double b0,double b1,double b2,double b3){
        return !(a2<=b0||b2<=a0||a3<=b1||b3<=a1);
    }
    // NEW block (descending body) layer k vs existing te layer j, j>=k.  c==1 => blocked.
    inline bool desc_hit(int bid,int orient,double ox,double oy,const Placed& te){
        const OrientData& nod=shapes[bid].orients[orient];
        const OrientData& eod=shapes[te.bid].orients[te.orient];
        int nn=(int)nod.layers.size(), ne=(int)eod.layers.size();
        int iox=(int)std::floor(ox+0.5), ioy=(int)std::floor(oy+0.5);
        int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
        for(int k=0;k<nn;k++){const LayerData&AL=nod.layers[k]; if(AL.npts<3)continue;
            for(int j=k;j<ne;j++){const LayerData&BL=eod.layers[j]; if(BL.npts<3)continue;
                if(RASTER && !bmp_overlap(AL,iox,ioy,BL,tox,toy)) continue;
                if(classify(AL.pts.data(),AL.npts,ox,oy,BL.pts.data(),BL.npts,te.ox,te.oy)==1) return true;}}
        return false;
    }
    // existing te (descending body) layer k vs NEW block layer j, j>=k.
    inline bool desc_hit_rev(const Placed& te,int bid,int orient,double ox,double oy){
        const OrientData& nod=shapes[bid].orients[orient];
        const OrientData& eod=shapes[te.bid].orients[te.orient];
        int nn=(int)nod.layers.size(), ne=(int)eod.layers.size();
        int iox=(int)std::floor(ox+0.5), ioy=(int)std::floor(oy+0.5);
        int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
        for(int k=0;k<ne;k++){const LayerData&AL=eod.layers[k]; if(AL.npts<3)continue;
            for(int j=k;j<nn;j++){const LayerData&BL=nod.layers[j]; if(BL.npts<3)continue;
                if(RASTER && !bmp_overlap(AL,tox,toy,BL,iox,ioy)) continue;
                if(classify(AL.pts.data(),AL.npts,te.ox,te.oy,BL.pts.data(),BL.npts,ox,oy)==1) return true;}}
        return false;
    }
    bool placement_feasible(int bay,int bid,int orient,double x,double y,int en,int ex){
        const OrientData& od=shapes[bid].orients[orient];
        double nx0=od.x0+x,ny0=od.y0+y,nx1=od.x1+x,ny1=od.y1+y;
        // bay containment, exact: the grader rejects any footprint outside the bay with
        // `outside.area > 0`, so a 1e-6 slack here is slack in the direction that gets a
        // solution thrown out.  Equality still passes, so flush-against-the-wall stays legal.
        if(nx0<0.0||ny0<0.0||nx1>bw[bay]||ny1>bh[bay]) return false;
        for(const Placed& te : timeline[bay]){
            if(!(en < te.ex && te.en < ex)) continue;
            if(!bb_ov(nx0,ny0,nx1,ny1,te.bx0,te.by0,te.bx1,te.by1)) continue;
            if(te.en <= en && en < te.ex){ if(desc_hit(bid,orient,x,y,te)) return false; }
            if(te.en < ex && ex <= te.ex){ if(desc_hit(bid,orient,x,y,te)) return false; }
            if(en <= te.en && te.en < ex){ if(desc_hit_rev(te,bid,orient,x,y)) return false; }
            if(en < te.ex && te.ex <= ex){ if(desc_hit_rev(te,bid,orient,x,y)) return false; }
        }
        return true;
    }

    void candidates(int bid,int orient,int bay,double step,std::vector<std::pair<double,double>>& out){
        const OrientData& od=shapes[bid].orients[orient];
        double w=od.x1-od.x0, h=od.y1-od.y0;
        double maxx=bw[bay]-w, maxy=bh[bay]-h;
        if(maxx<-1e-6||maxy<-1e-6) return;
        out.push_back({-od.x0,-od.y0});
        for(const Placed& te: timeline[bay]){
            double axs[2]={te.bx1-od.x0, te.bx0-od.x0};
            double ays[2]={te.by1-od.y0, te.by0-od.y0};
            for(double ax: axs) for(double ay: ays){
                if(ax>=-od.x0-1e-6&&ax<=maxx-od.x0+1e-6&&ay>=-od.y0-1e-6&&ay<=maxy-od.y0+1e-6)
                    out.push_back({ax,ay});
            }
        }
        for(double gx=0; gx<=maxx+1e-6; gx+=step)
            for(double gy=0; gy<=maxy+1e-6; gy+=step)
                out.push_back({gx-od.x0,gy-od.y0});
    }

    std::tuple<bool,int,int,double,double,int,int>
    find_best_placement(int bid, std::vector<int> bay_list, std::vector<int> entry_times){
        const BlockShape& bs=shapes[bid];
        int P=(int)bs.pt; double due=bs.due;
        double bestscore=1e30; bool found=false;
        int bbay=-1,bori=-1,ben=-1,bex=-1; double bx=0,by=0;
        int norient=(int)bs.orients.size();
        for(int en : entry_times){
            int ex=en+P;
            double tard = (ex>due)? (ex-due) : 0.0;
            for(int bay : bay_list){
                double prefpen = 0.0;
                if(bay < (int)bs.prefs.size()){
                    double mx=bs.prefs[0]; for(double v:bs.prefs) if(v>mx)mx=v;
                    prefpen = mx - bs.prefs[bay];
                }
                double bstep = std::max(1.0, std::min(bw[bay],bh[bay])/GRID_DIV);
                // SWEEP: build per-new-layer forbidden bay-grid bitmaps once per (bay,en);
                // a candidate whose layers are all disjoint from F[k] is DEFINITELY feasible
                // (conservative maps) -> skip the exact per-present-block loop.
                int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
                int bayH=(int)std::ceil(bh[bay]); int bayW=(int)std::ceil(bw[bay]);
                int wpr=(bayW+64)>>6;   // +1 col slack
                std::vector<std::vector<uint64_t>> F;
                bool use_sweep = SWEEP && RASTER && maxL>0 && bayH>0 && bayH<20000;
                if(use_sweep){
                    F.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                    for(const Placed& te: timeline[bay]){
                        if(!(en < te.ex && te.en < ex)) continue;
                        bool newdesc=(te.en<=en&&en<te.ex)||(te.en<ex&&ex<=te.ex);
                        bool tedesc =(en<=te.en&&te.en<ex)||(en<te.ex&&te.ex<=ex);
                        if(!newdesc&&!tedesc) continue;
                        const OrientData& eod=shapes[te.bid].orients[te.orient];
                        int ne=(int)eod.layers.size();
                        int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
                        for(int j=0;j<ne;j++){ const LayerData& L=eod.layers[j]; if(L.npts<3)continue;
                            // newdesc: te layer j forbids new layers k<=j  -> F[0..min(j,maxL-1)]
                            if(newdesc){ int hi=std::min(j,maxL-1); for(int k=0;k<=hi;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                            // tedesc: te layer j forbids new layers k>=j    -> F[j..maxL-1]
                            if(tedesc){ for(int k=std::max(j,0);k<maxL;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                        }
                    }
                }
                for(int oi=0; oi<norient; oi++){
                    const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
                    std::vector<std::pair<double,double>> cand;
                    candidates(bid,oi,bay,bstep,cand);
                    for(auto& c: cand){
                        double x=std::round(c.first), y=std::round(c.second);
                        double score = tard*1e12 + prefpen*1e8 + y*1e3 + x;
                        if(score>=bestscore) continue;   // can't beat current best -> skip work
                        // bounds
                        if(od.x0+x<0.0||od.y0+y<0.0||od.x1+x>bw[bay]||od.y1+y>bh[bay]) continue;   // exact: see placement_feasible
                        bool ok;
                        if(use_sweep){
                            int ix=(int)x, iy=(int)y; bool clear=true;
                            for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                                if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                            ok = clear ? true : placement_feasible(bay,bid,oi,x,y,en,ex);
                        } else {
                            ok = placement_feasible(bay,bid,oi,x,y,en,ex);
                        }
                        if(ok){bestscore=score;found=true;
                            bbay=bay;bori=oi;bx=x;by=y;ben=en;bex=ex;}
                    }
                }
            }
            if(found) break; // earliest feasible entry time wins the tardiness tier
        }
        return {found,bbay,bori,bx,by,ben,bex};
    }

    // Leftbottom best feasible cell for block `bid` at time [cur,cur+pt): min (h,wx,wy,bay).
    // found=false if none. Used by greedy_rollout (hot loop, all-C++).  Uses a per-(bay)
    // forbidden-layer bitmap (built once per call): a candidate whose layers are all
    // disjoint from the maps is DEFINITELY feasible (skip the exact per-present check);
    // only map-hitting candidates fall back to placement_feasible -> big speedup in the
    // rollout inner loop while staying EXACT.
    inline bool lb_best(int bid,int cur,int step,int& obay,int& oori,int& oix,int& oiy,bool approx=false,double prefw=0.0){
        const BlockShape& bs=shapes[bid]; int P=(int)bs.pt; int ex=cur+P;
        int norient=(int)bs.orients.size();
        int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
        double mxpref=0.0; if(prefw!=0.0 && !bs.prefs.empty()){ mxpref=bs.prefs[0]; for(double v:bs.prefs) if(v>mxpref)mxpref=v; }
        bool found=false; double bestsc=1e300;
        for(int bay=0;bay<n_bays;bay++){
            // Z3-aware bay offset: when prefw>0, bias placement toward the block's
            // preferred bays (min bay-preference penalty) so the rollout balances Z1
            // (tight packing) against Z3 (bay preference).  prefw==0 -> pure leftbottom.
            double bayoff = (double)bay;
            if(prefw!=0.0 && bay<(int)bs.prefs.size()) bayoff += prefw*(mxpref-bs.prefs[bay]);
            int bayH=(int)std::ceil(bh[bay]); int bayW=(int)std::ceil(bw[bay]);
            int wpr=(bayW+64)>>6;
            bool use_sweep = RASTER && maxL>0 && bayH>0 && bayH<20000;
            // F = conservative TOUCH forbidden-map (disjoint => provably feasible).
            // Fin = tight INTERIOR forbidden-map (overlap => provably infeasible, area>0).
            // Between them lies the boundary band where an exact placement_feasible is needed.
            std::vector<std::vector<uint64_t>> F, Fin;
            if(use_sweep){
                F.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                Fin.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                for(const Placed& te: timeline[bay]){
                    if(!(cur < te.ex && te.en < ex)) continue;
                    bool newdesc=(te.en<=cur&&cur<te.ex)||(te.en<ex&&ex<=te.ex);
                    bool tedesc =(cur<=te.en&&te.en<ex)||(cur<te.ex&&te.ex<=ex);
                    if(!newdesc&&!tedesc) continue;
                    const OrientData& eod=shapes[te.bid].orients[te.orient];
                    int ne=(int)eod.layers.size();
                    int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
                    for(int j=0;j<ne;j++){ const LayerData& L=eod.layers[j]; if(L.npts<3)continue;
                        if(newdesc){ int hi=std::min(j,maxL-1); for(int k=0;k<=hi;k++){ or_layer_into_map(F[k],wpr,bayH,L,tox,toy,false); or_layer_into_map(Fin[k],wpr,bayH,L,tox,toy,true); } }
                        if(tedesc){ for(int k=std::max(j,0);k<maxL;k++){ or_layer_into_map(F[k],wpr,bayH,L,tox,toy,false); or_layer_into_map(Fin[k],wpr,bayH,L,tox,toy,true); } }
                    }
                }
            }
            for(int oi=0;oi<norient;oi++){
                const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
                double w=od.x1-od.x0, h=od.y1-od.y0;
                if(w>bw[bay]+1e-9||h>bh[bay]+1e-9) continue;
                // taller orients can never beat a found (h,wx,wy) with wx=wy=0
                double orient_floor=((h*1e6+0.0)*1e4+0.0)*4.0+bayoff;
                if(found && orient_floor>=bestsc) continue;
                int lo_x=(int)std::ceil(-od.x0), hi_x=(int)std::floor(bw[bay]-od.x1);
                int lo_y=(int)std::ceil(-od.y0), hi_y=(int)std::floor(bh[bay]-od.y1);
                for(int ix=lo_x; ix<=hi_x; ix+=step){
                    double wx=ix+od.x0;
                    if(found && ((h*1e6+wx)*1e4+0.0)*4.0+bayoff>=bestsc) break;  // wx only grows
                    for(int iy=lo_y; iy<=hi_y; iy+=step){
                        double wy=iy+od.y0;
                        double sc=((h*1e6+wx)*1e4+wy)*4.0+bayoff;
                        if(found && sc>=bestsc) break;   // wy only grows within this ix
                        bool ok;
                        if(use_sweep){
                            bool clear=true;                    // disjoint from TOUCH map?
                            for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                                if(layer_hits_map(F[k],wpr,bayH,L,ix,iy,false)) clear=false; }
                            if(clear) ok=true;                  // provably feasible
                            else if(approx) ok=false;           // approx: touch-hit => reject (lossy)
                            else {
                                bool ihit=false;                // overlaps INTERIOR map?
                                for(int k=0;k<nl&&!ihit;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                                    if(layer_hits_map(Fin[k],wpr,bayH,L,ix,iy,true)) ihit=true; }
                                // interior overlap => genuine area>0 overlap => provably infeasible;
                                // otherwise it's the boundary band -> one exact check.
                                ok = ihit ? false : placement_feasible(bay,bid,oi,(double)ix,(double)iy,cur,ex);
                            }
                        } else ok = placement_feasible(bay,bid,oi,(double)ix,(double)iy,cur,ex);
                        if(ok){ bestsc=sc; found=true; obay=bay; oori=oi; oix=ix; oiy=iy; break; }
                    }
                }
            }
        }
        return found;
    }

    // Python-facing leftbottom best cell: (found,bay,ori,ix,iy) for block bid at [cur,cur+pt).
    std::tuple<bool,int,int,int,int> best_cell_lb(int bid,int cur,int step){
        int obay=-1,oori=-1,oix=0,oiy=0;
        bool f=lb_best(bid,cur,step,obay,oori,oix,oiy,false,bcl_prefw);
        return {f,obay,oori,oix,oiy};
    }
    double bcl_prefw=0.0;   // preference weight used by best_cell_lb (set via set_bcl_prefw)
    void set_bcl_prefw(double w){ bcl_prefw=w; }

    // FRIEND-STYLE contact-maximising position picker (Phase2 sc + Phase3 d_rank) against the
    // CURRENT (main) timeline, block bid entering at cur.  Phase2 per (bay,orient): among
    // feasible cells pick argmin  sc = -contact + (iy+top)*pos_lam + ix*pos_lam*0.01 + prefw*pen
    // (contact-first, low-skyline, left, biased to preferred bays).  Phase3 cross-bay: rank by
    // d_rank = w1*tardy + w3*pen - mu*contact.  Returns up to `topk` rows (bay,ori,ix,iy,contact)
    // sorted by d_rank -- the fast core of the friend's beam candidate stage.
    // OUR position scorer (env OGC_OURSCORE=1), distinct from the reference's raw -contact:
    //  (1) contact-DENSITY = contact / block-bbox-half-perimeter -> rewards how WELL-NESTED a
    //      block is for ITS OWN size, removing the reference's bias toward big blocks with long
    //      edges (a small block snug in a nook scores like a big block along a wall);
    //  (2) a stronger low-skyline weight -- the crane descends from the TOP, so keeping packs
    //      low preserves vertical descent clearance for later blocks (our crane-lever insight).
    // Magic-static: read once, thread-safe (used inside the OpenMP beam).
    static bool use_ourscore(){ static const int v=[](){const char*e=getenv("OGC_OURSCORE");return(e&&e[0]=='1')?1:0;}(); return v; }
    py::array_t<int> best_cell_contact(int bid,int cur,int step,double pos_lam,double prefw,
                                       double mu,double w1,double w3,int topk,
                                       double fut_beta=0.0,double mean_proc=1.0,
                                       double w2=0.0,std::vector<double> loads={}){
        const BlockShape& bs=shapes[bid]; int P=(int)bs.pt; int ex=cur+P; double dd=shapes[bid].due;
        double s_max=0; if(!bs.prefs.empty()){ s_max=bs.prefs[0]; for(double v:bs.prefs) if(v>s_max)s_max=v; }
        double tardy = ex>dd? (double)(ex-dd):0.0;
        int norient=(int)bs.orients.size();
        struct Cand{ double drank; int bay,oi,ix,iy,ct; };
        std::vector<Cand> cands;
        int maxLb=0; for(int oi=0;oi<norient;oi++) maxLb=std::max(maxLb,(int)bs.orients[oi].layers.size());
        for(int bay=0;bay<n_bays;bay++){
            double bw_j=bw[bay],bh_j=bh[bay];
            int bayH=(int)std::ceil(bh_j),bayW=(int)std::ceil(bw_j); int wpr=(bayW+64)>>6;
            std::vector<char> occ; buildOcc(timeline[bay],cur,ex,bayW,bayH,occ);
            std::vector<std::vector<uint64_t>> F;
            bool use_sweep=RASTER&&maxLb>0&&bayH>0&&bayH<20000;
            const bool HARDREJ=HARDREJ_on();
            if(use_sweep){ F.assign(maxLb,std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                for(const Placed& te: timeline[bay]){ if(!(cur<te.ex&&te.en<ex))continue;
                    bool nd=(te.en<=cur&&cur<te.ex)||(te.en<ex&&ex<=te.ex);
                    bool td=(cur<=te.en&&te.en<ex)||(cur<te.ex&&te.ex<=ex); if(!nd&&!td)continue;
                    const OrientData& eod=shapes[te.bid].orients[te.orient]; int ne=(int)eod.layers.size();
                    int tox=(int)std::floor(te.ox+0.5),toy=(int)std::floor(te.oy+0.5);
                    for(int j=0;j<ne;j++){const LayerData&L=eod.layers[j];if(L.npts<3)continue;
                        if(nd){int hi=std::min(j,maxLb-1);for(int k=0;k<=hi;k++)or_layer_into_map(F[k],wpr,bayH,L,tox,toy);}
                        if(td){for(int k=std::max(j,0);k<maxLb;k++)or_layer_into_map(F[k],wpr,bayH,L,tox,toy);}}}}
            double pen = (bay<(int)bs.prefs.size())? (s_max-bs.prefs[bay]) : s_max;
            double bestsc=1e300; int boi=-1,bix=0,biy=0,bct=0;
            for(int oi=0;oi<norient;oi++){ const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
                double w=od.x1-od.x0,h=od.y1-od.y0; if(w>bw_j+1e-9||h>bh_j+1e-9)continue;
                const FP& fp=footprint(bid,oi);
                int lox=(int)std::ceil(-od.x0),hix=(int)std::floor(bw_j-od.x1);
                int loy=(int)std::ceil(-od.y0),hiy=(int)std::floor(bh_j-od.y1);
                for(int ix=lox;ix<=hix;ix+=step)for(int iy=loy;iy<=hiy;iy+=step){
                    bool ok; if(use_sweep){bool clear=true;
                        for(int k=0;k<nl&&clear;k++){const LayerData&L=od.layers[k];if(L.npts<3)continue;
                            if(layer_hits_map(F[k],wpr,bayH,L,ix,iy))clear=false;}
                        ok=clear?true:placement_feasible(bay,bid,oi,(double)ix,(double)iy,cur,ex);
                    } else ok=placement_feasible(bay,bid,oi,(double)ix,(double)iy,cur,ex);
                    if(!ok)continue;
                    int ct=contact_at(fp,ix,iy,occ,bayW,bayH);
                    double sc;
                    if(use_ourscore()){
                        double bbp=std::max(1.0,(od.x1-od.x0)+(od.y1-od.y0));
                        double cdens=(double)ct/bbp;
                        sc = -cdens*12.0 + ((double)iy+od.y1)*pos_lam*1.4 + (double)ix*pos_lam*0.02 + prefw*pen;
                    } else {
                        sc = -(double)ct + ((double)iy+od.y1)*pos_lam + (double)ix*pos_lam*0.01 + prefw*pen;
                    }
                    if(fut_beta>0.0){
                        // FUTURE-VALUE (reference fut_beta): push blocks toward walls so the bay
                        // CENTRE stays open for later crane descents -- the lever that keeps Z1
                        // low on congested instances (contact alone fragments the descent paths).
                        double dl=(double)ix+od.x0, dr=bw_j-((double)ix+od.x1);
                        double db=(double)iy+od.y0, dt=bh_j-((double)iy+od.y1);
                        double dwall=std::min(std::min(dl,dr),std::min(db,dt));
                        sc += fut_beta*((double)P/std::max(1e-9,mean_proc))*dwall;
                    }
                    if(sc<bestsc){bestsc=sc;boi=oi;bix=ix;biy=iy;bct=ct;}
                }
            }
            if(boi<0)continue;
            double drank = w1*tardy + w3*pen - mu*(double)bct
                         + w2*dobj2_of(loads, bay, bs.workload);
            cands.push_back({drank,bay,boi,bix,biy,bct});
        }
        std::sort(cands.begin(),cands.end(),[](const Cand&a,const Cand&b){return a.drank<b.drank;});
        int m=std::min((int)cands.size(),std::max(1,topk));
        py::array_t<int> arr({m,5}); int* pp=arr.mutable_data();
        for(int i=0;i<m;i++){ pp[i*5]=cands[i].bay;pp[i*5+1]=cands[i].oi;pp[i*5+2]=cands[i].ix;pp[i*5+3]=cands[i].iy;pp[i*5+4]=cands[i].ct; }
        return arr;
    }
    // Contact-max greedy completion from the CURRENT timeline (keeps existing placements),
    // placing the unplaced blocks in `order`.  Returns (w1*Z1 + w3*Z3 of NEW blocks, full flat).
    // Used to RANK contact-beam nodes by a faithful contact rollout (analog of greedy_rollout_from).
    std::pair<double,std::vector<int>>
    greedy_contact_from(std::vector<int> state_flat, std::vector<int> order, int step, double pos_lam,
                        double prefw, double mu, double w1, double w3,
                        double fut_beta=0.0, double mean_proc=1.0){
        int nb=(int)shapes.size();
        for(auto&t:timeline) t.clear();
        std::vector<char> placed(nb,0);
        for(size_t i=0;i+6<state_flat.size();i+=7){ int b=state_flat[i];
            add(state_flat[i+1],b,state_flat[i+2],(double)state_flat[i+3],(double)state_flat[i+4],state_flat[i+5],state_flat[i+6]);
            placed[b]=1; }
        std::vector<int> pending; for(int b: order) if(!placed[b]) pending.push_back(b);
        double z1=0,z3=0; std::vector<int> out; int cur=INT_MAX;
        for(int b: pending) cur=std::min(cur,(int)shapes[b].rt);
        if(pending.empty()) cur=0;
        long guard=0;
        while(!pending.empty()){
            if(++guard>2000000) break;
            std::vector<int> ready; for(int b:pending) if((int)shapes[b].rt<=cur) ready.push_back(b);
            bool any=false;
            for(int b: ready){
                py::array_t<int> r=best_cell_contact(b,cur,step,pos_lam,prefw,mu,w1,w3,1,fut_beta,mean_proc);
                if(r.shape(0)<1) continue;
                const int* d=r.data(); int bay=d[0],oi=d[1],ix=d[2],iy=d[3];
                int ex=cur+(int)shapes[b].pt; add(bay,b,oi,(double)ix,(double)iy,cur,ex); placed[b]=1;
                double dd=shapes[b].due; z1 += ex>dd?(double)(ex-dd):0.0;
                const auto&pr=shapes[b].prefs; double mx=pr.empty()?0:pr[0]; for(double v:pr)if(v>mx)mx=v;
                z3 += (bay<(int)pr.size())? (mx-pr[bay]) : mx;
                any=true;
            }
            if(any){ std::vector<int> np; for(int b:pending) if(!placed[b]) np.push_back(b); pending.swap(np); }
            if(pending.empty()) break;
            long nextt=(long)2e18;
            for(int b:pending){ long r=(long)shapes[b].rt; if(r>cur&&r<nextt)nextt=r; }
            for(auto& bay:timeline) for(auto& p:bay){ if(p.ex>cur&&p.ex<nextt)nextt=p.ex; }
            if(nextt>=(long)1e18){ cur=cur+1; } else cur=(int)nextt;
        }
        std::vector<char> has(nb,0); std::vector<std::array<int,7>> rec(nb);
        for(auto& bay:timeline) for(auto& p:bay){ has[p.bid]=1; rec[p.bid]={p.bid,p.bay,p.orient,(int)std::floor(p.ox+0.5),(int)std::floor(p.oy+0.5),p.en,p.ex}; }
        for(int b=0;b<nb;b++) if(has[b]){ auto&rr=rec[b]; for(int k=0;k<7;k++) out.push_back(rr[k]); }
        return {w1*z1+w3*z3, out};
    }
    // Greedy event-driven construction using best_cell_contact (friend's contact-max Phase2/3).
    // Places blocks in dispatch `order`; each ready block goes to its cross-bay best contact cell.
    // Returns flat [b,bay,ori,ix,iy,en,ex]* (all placed) for measurement / seeding.
    std::vector<int> greedy_contact(std::vector<int> order, int step, double pos_lam, double prefw,
                                    double mu, double w1, double w3){
        int nb=(int)shapes.size();
        for(auto&t:timeline) t.clear();
        std::vector<char> placed(nb,0); std::vector<int> pending=order;
        std::vector<int> out; int cur=INT_MAX;
        for(int b: order) cur=std::min(cur,(int)shapes[b].rt);
        long guard=0;
        while(!pending.empty()){
            if(++guard>2000000) break;
            std::vector<int> ready;
            for(int b: pending) if((int)shapes[b].rt<=cur) ready.push_back(b);
            bool any=false;
            for(int b: ready){
                py::array_t<int> r=best_cell_contact(b,cur,step,pos_lam,prefw,mu,w1,w3,1);
                if(r.shape(0)<1) continue;
                const int* d=r.data(); int bay=d[0],oi=d[1],ix=d[2],iy=d[3];
                int ex=cur+(int)shapes[b].pt;
                add(bay,b,oi,(double)ix,(double)iy,cur,ex); placed[b]=1;
                out.push_back(b);out.push_back(bay);out.push_back(oi);out.push_back(ix);out.push_back(iy);out.push_back(cur);out.push_back(ex);
                any=true;
            }
            if(any){ std::vector<int> np; for(int b:pending) if(!placed[b]) np.push_back(b); pending.swap(np); }
            if(pending.empty()) break;
            long nextt=(long)2e18;
            for(int b:pending){ long r=(long)shapes[b].rt; if(r>cur&&r<nextt)nextt=r; }
            for(auto& bay:timeline) for(auto& p:bay){ if(p.ex>cur&&p.ex<nextt)nextt=p.ex; }
            if(nextt>=(long)1e18){ cur=cur+1; } else cur=(int)nextt;
        }
        return out;
    }
    // THREAD-LOCAL-timeline variant of best_cell_contact (for the parallel contact_beam): same
    // Phase2 contact-max position (with fut_beta wall-push) + Phase3 cross-bay d_rank, but scans
    // against a passed TL instead of this->timeline so beam states expand concurrently.  Appends
    // up to topk (bay,oi,ix,iy,ct) sorted by d_rank into `out`.
    // GUIDED-RECONSTRUCTION anchor (OUR take on the reference's rung_G, different mechanism):
    // cb_anchor[bid] = the bay this block sat in in the incumbent (-1 = free).  A per-block
    // DECAYING stay-weight (cb_anchor_w[bid]) is added to the cross-bay rank for any OTHER bay,
    // so the beam re-derives the incumbent's structure but can still migrate blocks where that
    // strictly lowers the objective -- a large neighbourhood the K~20 LNS can't reach.  Set
    // before contact_beam's OpenMP region, read-only inside -> thread-safe.  Empty = no anchoring.
    std::vector<int> cb_anchor;
    std::vector<double> cb_anchor_w;
    // W2 IN THE CANDIDATE RANK (the one term we were missing against the reference).
    // The reference ranks candidates by the full objective delta
    //     d_rank = w1*tardy + w2*d(obj2) + w3*pref - mu*contact
    // and ours had every term but w2*d(obj2).  That is not a detail: the largest pipeline win
    // ever measured here (prob_39 -2.30%) was a LOAD-BALANCE collapse -- Z2 3403 -> 1101, Z3
    // 8081 -> 6421, Z1 +6 -- and it was reached only INDIRECTLY, by routing on a preference
    // proxy inside a density gate.  With obj2 in the rank the beam sees that trade directly on
    // every candidate, on every instance, with no gate and no mode.  loads empty or w2 == 0 ->
    // the term vanishes and the rank is byte-identical to before.
    // env OGC_W2RANK=0 removes the term -> the candidate rank is byte-identical to the
    // pre-change engine, which is the OFF arm of the A/B.
    static bool w2rank_on(){ static const int v=[](){const char*e=getenv("OGC_W2RANK");return(e&&e[0]=='0')?0:1;}(); return v; }
    double dobj2_of(const std::vector<double>& loads,int bay,double wl) const {
        if(!w2rank_on() || n_bays<2 || (int)loads.size()<n_bays) return 0.0;
        // same normaliser contact_beam's obj2f uses (avg bay area / this bay's area), so the
        // candidate rank and the state rank speak about the SAME obj2
        double avg_ba=0.0; for(int j=0;j<n_bays;j++) avg_ba+=bw[j]*bh[j];
        avg_ba/=(double)n_bays;
        double mn=1e18,mx=-1e18,mn2=1e18,mx2=-1e18;
        for(int j=0;j<n_bays;j++){
            double uj=(bw[j]*bh[j]>1e-9)? avg_ba/(bw[j]*bh[j]) : 1.0;
            double v=uj*loads[j];
            if(v<mn)mn=v; if(v>mx)mx=v;
            double v2=(j==bay)? uj*(loads[j]+wl) : v;
            if(v2<mn2)mn2=v2; if(v2>mx2)mx2=v2;
        }
        return (mx2-mn2)-(mx-mn);
    }

    void best_cell_contact_tl(const std::vector<std::vector<Placed>>& TL,int bid,int cur,int step,
                              double pos_lam,double prefw,double mu,double w1,double w3,
                              double fut_beta,double mean_proc,int topk,std::vector<std::array<int,5>>& out,
                              double w2=0.0,const std::vector<double>* loads=nullptr){
        const BlockShape& bs=shapes[bid]; int P=(int)bs.pt; int ex=cur+P; double dd=shapes[bid].due;
        double s_max=0; if(!bs.prefs.empty()){ s_max=bs.prefs[0]; for(double v:bs.prefs) if(v>s_max)s_max=v; }
        double tardy = ex>dd? (double)(ex-dd):0.0;
        int norient=(int)bs.orients.size();
        struct Cand{ double drank; int bay,oi,ix,iy,ct; };
        std::vector<Cand> cands;
        int maxLb=0; for(int oi=0;oi<norient;oi++) maxLb=std::max(maxLb,(int)bs.orients[oi].layers.size());
        for(int bay=0;bay<n_bays;bay++){
            double bw_j=bw[bay],bh_j=bh[bay];
            int bayH=(int)std::ceil(bh_j),bayW=(int)std::ceil(bw_j); int wpr=(bayW+64)>>6;
            std::vector<char> occ;
            std::vector<std::vector<uint64_t>> F;
            std::vector<std::vector<uint64_t>> H;   // hard-reject twin of F (see below)
            bool use_sweep=RASTER&&maxLb>0&&bayH>0&&bayH<20000;
            const bool HARDREJ=HARDREJ_on();
            // OR-STAMP GRID CACHE (our port of the reference's incremental Grid): the (occ,F) pair
            // for (bay,cur,ex,maxLb, overlapping-placed-content) is memoised thread-locally, so the
            // many sibling beam states that share a bay's contents skip the O(placed x footprint)
            // layer stamping -- only the O(placed) content hash is paid.  A wrong hit could only mark
            // an infeasible cell "clear" -> committed placement then fails check_feasibility -> best-of
            // rejects it (never a wrong accepted answer).  env OGC_FCACHE=1; default off => identical.
            static thread_local std::unordered_map<uint64_t,
                std::pair<std::vector<char>,std::vector<std::vector<uint64_t>>>> fcache;
            static const int FCACHE=[](){const char*e=getenv("OGC_FCACHE");return(e&&e[0]=='1')?1:0;}();
            uint64_t fk=0; bool fhit=false;
            if(FCACHE){
                fk=1469598103934665603ULL;
                auto mix=[&](uint64_t v){ fk^=v; fk*=1099511628211ULL; };
                mix((uint64_t)bay); mix((uint64_t)cur*2654435761u+(uint64_t)ex); mix((uint64_t)maxLb);
                for(const Placed& te: TL[bay]){ if(!(cur<te.ex&&te.en<ex))continue;
                    bool ndd=(te.en<=cur&&cur<te.ex)||(te.en<ex&&ex<=te.ex);
                    bool td=(cur<=te.en&&te.en<ex)||(cur<te.ex&&te.ex<=ex); if(!ndd&&!td)continue;
                    mix((uint64_t)te.bid*131+(uint64_t)te.orient);
                    mix((uint64_t)((long)std::floor(te.ox+0.5))*8191+(long)std::floor(te.oy+0.5));
                    mix((uint64_t)te.en*65537u+(uint64_t)te.ex); }
                auto it=fcache.find(fk);
                if(it!=fcache.end()){ occ=it->second.first; F=it->second.second; fhit=true; }
            }
            if(!fhit){
                buildOcc(TL[bay],cur,ex,bayW,bayH,occ);
                // HARD-REJECT MAP.  F carries occupancy PLUS crane descent shadows, so a hit
                // on it proves nothing -- the placement may still be legal and the exact test
                // has to run.  Measured, that is 65-86% of all cells and 65-83% of the whole
                // beam runtime: the filter can only ever say YES.
                // H is the same union restricted to the residents' OWN layer k, i.e. plain
                // geometric overlap at that layer.  Two solids in the same cell of the same
                // layer is a physical collision, so a hit on H proves INFEASIBLE and the cell
                // can be dropped without the exact test.  H subset F, so the two together
                // sandwich the answer: miss F -> accept, hit H -> reject, between -> exact.
                if(use_sweep){ H.assign(maxLb,std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                    for(const Placed& te: TL[bay]){ if(!(cur<te.ex&&te.en<ex))continue;
                        const OrientData& eod=shapes[te.bid].orients[te.orient]; int ne=(int)eod.layers.size();
                        int tox=(int)std::floor(te.ox+0.5),toy=(int)std::floor(te.oy+0.5);
                        // LAYER 0 ONLY.  Layer INDEX is not height: blocks have different
                        // layer counts, so layer j of one is not the same slab as layer j of
                        // another, and rejecting on a same-index overlap is wrong -- the audit
                        // still caught 451-712 legal placements dropped that way.  Layer 0 is
                        // the one slab every block shares, because every block rests on the bay
                        // floor, so an interior-vs-interior overlap there is a genuine
                        // collision.  Interior on both sides because blocks may legally touch
                        // and rasterisation makes a shared boundary look like an overlap.
                        if(ne>0){ const LayerData&L0=eod.layers[0];
                            if(L0.npts>=3) or_layer_into_map(H[0],wpr,bayH,L0,tox,toy,true); }}}
                if(use_sweep){ F.assign(maxLb,std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                    for(const Placed& te: TL[bay]){ if(!(cur<te.ex&&te.en<ex))continue;
                        bool ndd=(te.en<=cur&&cur<te.ex)||(te.en<ex&&ex<=te.ex);
                        bool td=(cur<=te.en&&te.en<ex)||(cur<te.ex&&te.ex<=ex); if(!ndd&&!td)continue;
                        const OrientData& eod=shapes[te.bid].orients[te.orient]; int ne=(int)eod.layers.size();
                        int tox=(int)std::floor(te.ox+0.5),toy=(int)std::floor(te.oy+0.5);
                        for(int j=0;j<ne;j++){const LayerData&L=eod.layers[j];if(L.npts<3)continue;
                            if(ndd){int hi=std::min(j,maxLb-1);for(int k=0;k<=hi;k++)or_layer_into_map(F[k],wpr,bayH,L,tox,toy);}
                            if(td){for(int k=std::max(j,0);k<maxLb;k++)or_layer_into_map(F[k],wpr,bayH,L,tox,toy);}}}}
                if(FCACHE){ if(fcache.size()>8000) fcache.clear();
                    fcache.emplace(fk,std::make_pair(occ,F)); }
            }
            double pen = (bay<(int)bs.prefs.size())? (s_max-bs.prefs[bay]) : s_max;
            double bestsc=1e300; int boi=-1,bix=0,biy=0,bct=0;
            for(int oi=0;oi<norient;oi++){ const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
                double w=od.x1-od.x0,h=od.y1-od.y0; if(w>bw_j+1e-9||h>bh_j+1e-9)continue;
                const FP& fp=footprint(bid,oi);
                int lox=(int)std::ceil(-od.x0),hix=(int)std::floor(bw_j-od.x1);
                int loy=(int)std::ceil(-od.y0),hiy=(int)std::floor(bh_j-od.y1);
                bool any=false;
                auto try_cell=[&](int ix,int iy){
                    bool ok;
                    if(CBPROF_on()){
                        #pragma omp atomic
                        cb_n_cell += 1.0;
                    }
                    // TEST ORDER: hard-reject FIRST.  H rejects ~82% of cells and costs ONE
                    // layer-0 bitmap probe, while the F sweep costs up to nl probes and only
                    // clears ~15%.  Asking the cheap, high-yield question first lets the large
                    // majority of cells exit after a single probe.  Pure reordering -- the
                    // three outcomes and their conditions are unchanged.
                    bool hardhit=false;
                    if(use_sweep && HARDREJ && !H.empty() && nl>0){
                        const LayerData&L0=od.layers[0];
                        if(L0.npts>=3) hardhit=layer_hits_map(H[0],wpr,bayH,L0,ix,iy,true);
                    }
                    if(hardhit){
                        ok=false;
                        if(CBPROF_on()){
                            #pragma omp atomic
                            cb_n_hard += 1.0;
                        }
                        if(HARDAUDIT_on()){
                            bool truth=placement_feasible_tl(TL[bay],bay,bid,oi,(double)ix,(double)iy,cur,ex);
                            if(truth){
                                #pragma omp atomic
                                cb_n_badrej += 1.0;
                            }
                        }
                    }
                    else if(use_sweep){bool clear=true;
                        for(int k=0;k<nl&&clear;k++){const LayerData&L=od.layers[k];if(L.npts<3)continue;
                            if(CBPROF_on()){
                                #pragma omp atomic
                                cb_n_bitmap += 1.0;
                            }
                            if(layer_hits_map(F[k],wpr,bayH,L,ix,iy))clear=false;}
                        if(clear) ok=true;
                        else if(false && ({
                                bool hard=false;
                                if(nl>0){ const LayerData&L0=od.layers[0];
                                    if(L0.npts>=3) hard=layer_hits_map(H[0],wpr,bayH,L0,ix,iy,true); }
                                hard; })) {
                            ok=false;                      // proven overlap -- no exact test
                            if(CBPROF_on()){
                                #pragma omp atomic
                                cb_n_hard += 1.0;
                            }
                            if(HARDAUDIT_on()){
                                // AUDIT: verify the rejection against the exact test.  A cell
                                // that H rejected but placement_feasible_tl accepts is a legal
                                // placement we silently deleted -- the one failure mode that
                                // must be zero before this can be trusted.
                                bool truth=placement_feasible_tl(TL[bay],bay,bid,oi,(double)ix,(double)iy,cur,ex);
                                if(truth){
                                    #pragma omp atomic
                                    cb_n_badrej += 1.0;
                                }
                            }
                        }
                        else {
                            if(CBPROF_on()){
                                auto _e0=std::chrono::steady_clock::now();
                                ok=placement_feasible_tl(TL[bay],bay,bid,oi,(double)ix,(double)iy,cur,ex);
                                double _de=std::chrono::duration<double>(std::chrono::steady_clock::now()-_e0).count();
                                #pragma omp atomic
                                cb_n_exact += 1.0;
                                #pragma omp atomic
                                cb_t_exact += _de;
                            } else ok=placement_feasible_tl(TL[bay],bay,bid,oi,(double)ix,(double)iy,cur,ex);
                        }
                    } else ok=placement_feasible_tl(TL[bay],bay,bid,oi,(double)ix,(double)iy,cur,ex);
                    if(!ok)return;
                    int ct=contact_at(fp,ix,iy,occ,bayW,bayH);
                    double sc;
                    if(use_ourscore()){
                        double bbp=std::max(1.0,(od.x1-od.x0)+(od.y1-od.y0));
                        double cdens=(double)ct/bbp;
                        sc = -cdens*12.0 + ((double)iy+od.y1)*pos_lam*1.4 + (double)ix*pos_lam*0.02 + prefw*pen;
                    } else {
                        sc = -(double)ct + ((double)iy+od.y1)*pos_lam + (double)ix*pos_lam*0.01 + prefw*pen;
                    }
                    if(fut_beta>0.0){ double dl=(double)ix+od.x0,dr=bw_j-((double)ix+od.x1);
                        double db=(double)iy+od.y0,dt=bh_j-((double)iy+od.y1);
                        double dwall=std::min(std::min(dl,dr),std::min(db,dt));
                        sc += fut_beta*((double)P/std::max(1e-9,mean_proc))*dwall; }
                    any=true;
                    if(sc<bestsc){bestsc=sc;boi=oi;bix=ix;biy=iy;bct=ct;}
                };
                // CONTACT CANDIDATE POSITIONS.  This beam ranks by contact, so a position
                // touching nothing can never win -- yet the full grid sweep evaluates every
                // one of them.  Measured on prob_20: 202M cells, 55.6s of a 56.2s call, on
                // bays of 40500 cells.
                //
                // A contact needs an edge to coincide with something, so collect the x
                // offsets that put this block's left or right edge against a present
                // block's opposite edge or a wall, the same for y, and try the
                // combinations -- the corner positions.  prob_20 carries roughly ten
                // blocks per bay at any instant, so that is ~22 x 22 candidates where the
                // sweep had 40500.
                //
                // A restriction, not an equivalence: a position touching in x while free
                // in y is a real contact this set omits.  So when the corner set finds
                // nothing feasible, fall back to the full sweep for this orientation --
                // the beam's correctness never depends on the shortcut, only its speed.
                // env OGC_CPOS=0 pins the old sweep.
                // Cheaper of the two candidate sets wins, decided by arithmetic rather than
                // by a density gate: |xs|*|ys| against the swept cell count.  On prob_38 the
                // bays hold ~55 blocks at a time and are only ~2176 cells, so the corner set
                // (112 x 112) is BIGGER than the sweep and the first version of this made the
                // instance slower -- 1.06G cells to 1.38G.  Comparing the two costs picks the
                // sweep there and the corners on prob_20 automatically.
                bool usec=false;
                std::vector<int> xs, ys;
                if(CPOS_on()){
                    xs.assign({lox,hix}); ys.assign({loy,hiy});
                    for(const Placed& te: TL[bay]){
                        if(!(cur < te.ex && te.en < ex)) continue;
                        int xa=(int)std::ceil(te.bx1-od.x0), xb=(int)std::floor(te.bx0-od.x1);
                        if(xa>=lox&&xa<=hix) xs.push_back(xa);
                        if(xb>=lox&&xb<=hix) xs.push_back(xb);
                        int ya=(int)std::ceil(te.by1-od.y0), yb=(int)std::floor(te.by0-od.y1);
                        if(ya>=loy&&ya<=hiy) ys.push_back(ya);
                        if(yb>=loy&&yb<=hiy) ys.push_back(yb);
                    }
                    std::sort(xs.begin(),xs.end()); xs.erase(std::unique(xs.begin(),xs.end()),xs.end());
                    std::sort(ys.begin(),ys.end()); ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
                    double corner=(double)xs.size()*(double)ys.size();
                    double swept =(double)(std::max(0,(hix-lox)/std::max(1,step))+1)
                                 *(double)(std::max(0,(hiy-loy)/std::max(1,step))+1);
                    // 4x margin, not merely "cheaper": when the corner set finds nothing the
                    // sweep runs too, so a corner attempt that usually fails has to be cheap
                    // enough that paying for both is bounded.  prob_38 rejects 99.7% of cells,
                    // so its corner set almost always falls through -- requiring 4x caps that
                    // waste at 25% and hands the instance straight to the sweep, while prob_20's
                    // corner set is ~1% of its sweep and is unaffected.
                    usec = corner*4.0 < swept;
                    if(usec) for(int ix: xs) for(int iy: ys) try_cell(ix,iy);
                }
                if(!usec || !any)
                    for(int ix=lox;ix<=hix;ix+=step)for(int iy=loy;iy<=hiy;iy+=step) try_cell(ix,iy);
            }
            if(boi<0)continue;
            double drank = w1*tardy + w3*pen - mu*(double)bct
                         + (loads ? w2*dobj2_of(*loads, bay, bs.workload) : 0.0);
            // guided-reconstruction anchor: bias toward the incumbent bay for this block
            if(!cb_anchor.empty() && bid<(int)cb_anchor.size() && bid<(int)cb_anchor_w.size()
               && cb_anchor[bid]>=0 && bay!=cb_anchor[bid]) drank += cb_anchor_w[bid];
            cands.push_back({drank,bay,boi,bix,biy,bct});
        }
        std::sort(cands.begin(),cands.end(),[](const Cand&a,const Cand&b){return a.drank<b.drank;});
        int m=std::min((int)cands.size(),std::max(1,topk));
        for(int i=0;i<m;i++) out.push_back({cands[i].bay,cands[i].oi,cands[i].ix,cands[i].iy,cands[i].ct});
    }
    double cb_t_rebuild=0.0, cb_t_scan=0.0;
    double cb_n_cell=0.0, cb_n_bitmap=0.0, cb_n_exact=0.0, cb_t_exact=0.0, cb_n_hard=0.0;
    // Only the first-choice scan was ever timed.  On a dense instance the first choice
    // usually finds nothing, and the retry over later entry times rescans the whole
    // candidate set once per entry time -- that work was invisible.  cb_t_retry is that
    // path, cb_t_roll the per-state completion rollouts.
    double cb_t_retry=0.0, cb_t_roll=0.0; double cb_n_retry=0.0;
    double cb_n_arskip=0.0, cb_n_arbad=0.0;   // area precheck: skips, and skips that were wrong
    // DEFAULT OFF until the soundness audit below passes: a hard reject that is wrong
    // silently removes legal placements from the search.
    double cb_n_badrej=0.0;
    static bool HARDAUDIT_on(){ static const int v=[](){const char*e=getenv("OGC_HARDAUDIT");return (e&&e[0]=='1');}(); return v; }
    // DEFAULT ON.  An APPROXIMATE filter, and for a beam that is the right trade: audited
    // error 1.5-1.8e-5 of rejections (zero on prob_30/39/26/40/24), against 3.5-11.8x more
    // of the space searched in the same budget --
    //     cells in a fixed 40s beam:  prob_30 80M->374M   prob_35 85M->300M   prob_39 74M->875M
    // and exact placement_feasible_tl calls falling from 65-86% of cells to 1-3%.  Width
    // already discards vastly more legal candidates than this filter ever will.
    // (This default was reported ON in an earlier commit while the source still said OFF --
    // the edit lived only in a working tree a container reset destroyed.)
    static bool HARDREJ_on(){ static const int v=[](){const char*e=getenv("OGC_HARDREJ");return !(e&&e[0]=='0');}(); return v; }
    static bool ARAUDIT_on(){ static const int v=[](){const char*e=getenv("OGC_ARAUDIT");return(e&&e[0]=='1')?1:0;}(); return v; }
    // ARPRE -- area precheck for the retry path.  DEFAULT OFF: it is NOT the necessary
    // condition it was meant to be.  Auditing it (OGC_ARAUDIT=1: skip, then run the scan
    // anyway and see whether it would have succeeded) found 14333 of 18081 skips wrong on
    // prob_38 and 15446 of 21227 on prob_40 -- 79% and 73%.  It deletes real placements,
    // which is why prob_38 went 41.1M -> 104.4M and prob_40 1.99M -> 4.38M.  The arithmetic
    // has been through two corrections already (areas[] arrive scaled by SC while bw*bh is
    // raw; and occupancy is the MAX over instants in the window, not the sum across it) and
    // both were real bugs, but neither was the whole story -- so it stays off until the
    // audit reads zero.  OGC_ARPRE=1 enables.
    static bool ARPRE_on(){ static const int v=[](){const char*e=getenv("OGC_ARPRE");return(e&&e[0]=='1')?1:0;}(); return v; }
    // CPOS -- contact-candidate positions.  DEFAULT OFF: measured 14-36x faster and NET
    // WORSE.  See the note at the candidate-set construction for why.  OGC_CPOS=1 enables.
    static bool CPOS_on(){ static const int v=[](){const char*e=getenv("OGC_CPOS");return(e&&e[0]=='1')?1:0;}(); return v; }
    static bool CBPROF_on(){ static const int v=[](){const char*e=getenv("OGC_CBPROF");return(e&&e[0]=='1')?1:0;}(); return v; }
    struct CBState { std::vector<int> flat; std::vector<char> placed; std::vector<double> loads; double gt,gz3,gcontact; int nplaced; };
    // C++ CONTACT BEAM (OpenMP over beam states): the fast engine port of the Python _contact_beam
    // so a WIDE beam (B~50) fits in budget on congested instances.  Fixed dispatch `order`; each
    // state expands its dispatched block into its top-K contact positions (best_cell_contact_tl),
    // states ranked by cum_hard - mu*cum_contact + w2*obj2(loads) + w1*hz1, pruned to B; survivors
    // completed by a contact rollout.  Returns (exact obj, full flat) or (1e18,{}) on timeout.
    std::pair<double,std::vector<int>>
    contact_beam(std::vector<int> order, std::vector<double> areas, std::vector<double> workloads,
                 int B, int K, int step, double pos_lam, double prefw, double mu,
                 double w1, double w2, double w3, double fut_beta, double mean_proc, double time_budget_s,
                 std::vector<int> anchor=std::vector<int>(), std::vector<double> anchor_w=std::vector<double>(),
                 double area_scale=1.0){
        cb_anchor=std::move(anchor); cb_anchor_w=std::move(anchor_w);
        int nb=(int)shapes.size();
        for(int b=0;b<nb;b++) for(int oi=0;oi<(int)shapes[b].orients.size();oi++) footprint(b,oi);
        double area_total=0; for(int j=0;j<n_bays;j++) area_total+=bw[j]*bh[j];
        double avg_a=0; for(int b=0;b<nb;b++) avg_a+=areas[b]; avg_a=nb?avg_a/nb:1.0;
        double avg_ba=n_bays?area_total/n_bays:1.0;
        std::vector<double> u(n_bays); for(int j=0;j<n_bays;j++) u[j]=(bw[j]*bh[j]>1e-9)?avg_ba/(bw[j]*bh[j]):1.0;
        std::vector<double> mxp(nb,0); for(int b=0;b<nb;b++){const auto&pr=shapes[b].prefs;double mx=pr.empty()?0:pr[0];for(double v:pr)if(v>mx)mx=v;mxp[b]=mx;}
        int nord=(int)order.size();
        // WAIT-FOR-EXIT beam knobs (env): CBWAIT = max wait horizon (0=off, byte-identical);
        // CBMAXENT = cap on distinct entry times tried per state (bounds cost at 250 blocks).
        static const int CBWAIT=[](){const char*e=getenv("OGC_CBWAIT");return e?atoi(e):0;}();
        static const int CBMAXENT=[](){const char*e=getenv("OGC_CBMAXENT");return e?std::max(1,atoi(e)):4;}();
        const bool CBPROF=CBPROF_on(); cb_t_rebuild=0.0; cb_t_scan=0.0;
        cb_n_cell=cb_n_bitmap=cb_n_exact=cb_t_exact=cb_n_hard=cb_n_badrej=0.0;
        cb_t_retry=cb_t_roll=cb_n_retry=0.0; cb_n_arskip=cb_n_arbad=0.0;
        auto obj2f=[&](const std::vector<double>& loads){ double mn=1e18,mx=-1e18; for(int j=0;j<n_bays;j++){double v=u[j]*loads[j]; if(v<mn)mn=v; if(v>mx)mx=v;} return n_bays>1?(mx-mn):0.0; };
        double inc_obj=1e18;      // best COMPLETE objective seen -- the pruning threshold
        static const bool ADMP_LIVE=[](){const char*e=getenv("OGC_ADMP");return (e&&e[0]=='1');}();
        CBState init; init.placed.assign(nb,0); init.loads.assign(n_bays,0.0); init.gt=0;init.gz3=0;init.gcontact=0;init.nplaced=0;
        std::vector<CBState> beam; beam.push_back(std::move(init));
        auto t0=std::chrono::steady_clock::now();
        auto elapsed=[&](){ return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); };
        // ADAPTIVE BEAM WIDTH.  A width predicted from a formula is silently catastrophic:
        // the beam returns NOTHING when it overruns, and the same constant was 4x wrong the
        // moment the beam ran inside a worker pool (one core instead of four) -- every
        // worker then returned the greedy floor and the 300s answer was worse than the 60s
        // one.  So do not predict.  MEASURE: after each level, cost per (state x level) is
        // known exactly, so the width that just fits the remaining levels in the remaining
        // budget is known too.  Narrow when behind (completion is guaranteed), widen when
        // ahead (the budget is actually spent).  env OGC_ADAPTB=0 pins the width.
        static const bool ADAPTB=[](){const char*e=getenv("OGC_ADAPTB");return !(e&&e[0]=='0');}();
        const int Bmax=std::max(1,B), Bstart=ADAPTB?std::max(1,std::min(B,8)):B;
        int Bcur=Bstart; double work=0.0;   // work = sum over levels of (states expanded)
        for(int level=0; level<nord; level++){
            if(elapsed()>time_budget_s) return {1e18,{}};
            if(ADAPTB && level>0 && work>0.0){
                double per=elapsed()/work;                       // seconds per state-level
                double left=time_budget_s*0.90-elapsed();
                int rem=nord-level;
                int fit=(per>1e-12&&rem>0)? (int)(left/(per*(double)rem)) : Bmax;
                if(fit<1) fit=1;
                if(fit>Bcur*2) fit=Bcur*2;                       // grow smoothly
                Bcur=std::max(1,std::min(Bmax,fit));
            }
            const int B=Bcur;                                    // width used by THIS level
            // ADAPTIVE K (idea 8).  Width and candidates-per-state both spend the same
            // budget, and which one pays better is instance-dependent -- so let the same
            // measured-cost controller decide.  When the width controller has already hit
            // its ceiling there is spare budget, and the only way to spend it is to look at
            // MORE candidates per state.  env OGC_ADAPTK=0 pins K.
            static const bool ADAPTK=[](){const char*e=getenv("OGC_ADAPTK");return !(e&&e[0]=='0');}();
            int Kuse=K;
            if(ADAPTK && ADAPTB && level>0 && work>0.0){
                double per=elapsed()/work, left2=time_budget_s*0.90-elapsed();
                int rem2=nord-level;
                if(per>1e-12 && rem2>0){
                    double afford=left2/(per*(double)rem2);      // states we could still expand
                    if(afford > Bcur*1.5) Kuse=std::min(K*3, (int)(K*afford/std::max(1,Bcur)));
                }
                if(Kuse<1) Kuse=1;
            }
            int bi=order[level]; int r=(int)shapes[bi].rt, pt=(int)shapes[bi].pt; double dd=shapes[bi].due;
            double wl=workloads[bi]; const auto& pr=shapes[bi].prefs;
            int nbeam=(int)beam.size();
            work += (double)nbeam;          // states expanded so far -> the cost unit
            std::vector<std::vector<CBState>> perstate(nbeam);
            #pragma omp parallel
            {
                std::vector<std::vector<Placed>> TL(n_bays);
                std::vector<std::array<int,5>> cc;
                #pragma omp for schedule(dynamic)
                for(int si=0;si<nbeam;si++){
                    CBState& st=beam[si];
                    std::chrono::steady_clock::time_point _p0;
                    if(CBPROF) _p0=std::chrono::steady_clock::now();
                    load_flat_into(st.flat, TL);
                    if(CBPROF){ double _d=std::chrono::duration<double>(
                                    std::chrono::steady_clock::now()-_p0).count();
                        #pragma omp atomic
                        cb_t_rebuild += _d; }
                    auto& outv=perstate[si];
                    // AREA PRECHECK.  When the first-choice entry time has no free cell the
                    // search walks later entry times, and every attempt costs a full
                    // multi-bay, multi-orientation position scan -- measured 58707 of them on
                    // prob_38, 29.6s of a 33.3s call, 89% of the wall clock, and 54503 /
                    // 47.0s of 52.3s on prob_40.  Most of those attempts cannot succeed for a
                    // reason far cheaper to check than geometry: a bay holding less free area
                    // than the block's footprint has no room for it at any position or
                    // orientation.  Area is a NECESSARY condition, so skipping on it discards
                    // only attempts that were going to fail and the beam's output is
                    // unchanged -- this buys time, not a different search.
                    // env OGC_ARPRE=0 disables.
                    auto room_at=[&](int e,int exx)->bool{
                        for(int bay2=0;bay2<n_bays;bay2++){
                            // MAX occupancy over the window, not the sum across it.  Blocks whose
                            // intervals both meet [e,exx) need not be present at the same instant --
                            // [0,10) and [12,22) both intersect [5,15) yet never coexist -- so summing
                            // over the window over-counts, under-states the free area, and skips entry
                            // times that were feasible.  The new block occupies the whole window, so
                            // the binding instant is the busiest one; the candidate instants are e and
                            // every entry inside the window.
                            double used=0.0;
                            for(const Placed& tp: TL[bay2]){
                                int t=tp.en; if(t<e) t=e;
                                if(t>=exx) continue;
                                double at=0.0;
                                for(const Placed& te: TL[bay2])
                                    if(te.en<=t && t<te.ex) at+=areas[te.bid];
                                if(at>used) used=at;
                            }
                            {   double at=0.0;                    // the instant e itself
                                for(const Placed& te: TL[bay2])
                                    if(te.en<=e && e<te.ex) at+=areas[te.bid];
                                if(at>used) used=at; }
                            if(bw[bay2]*bh[bay2]-used >= areas[bi]) return true;
                        }
                        return false;
                    };
                    // WAIT-FOR-EXIT beam (OGC_CBWAIT>0): generate candidates both at the release
                    // time `r` AND at a bounded set of near-future bay exits, each carrying its OWN
                    // entry/exit (and thus tardiness).  A block that would spill to a non-preferred
                    // bay if forced in NOW can instead be a candidate that WAITS a little for its
                    // preferred bay to free -- the beam ranks the (higher-tardy, lower-Z3) wait
                    // candidate against the (lower-tardy, higher-Z3) now candidate by the true
                    // objective, so it searches the Z1<->Z3 frontier.  CBWAIT=max wait horizon;
                    // default 0 => original behaviour (byte-identical).  Bounded #entries keeps it
                    // affordable at 250 blocks (esp. paired with step-2).
                    std::vector<std::pair<int,int>> allc_ct;    // (entry, exit)
                    std::vector<std::array<int,5>> allc;        // bay,oi,ix,iy,ct  (parallel to allc_ct)
                    if(CBWAIT>0){
                        std::vector<int> ents; ents.push_back(r);
                        for(int bay=0;bay<n_bays;bay++) for(const Placed& te:TL[bay])
                            if(te.ex>r && te.ex<=r+CBWAIT) ents.push_back(te.ex);
                        std::sort(ents.begin(),ents.end()); ents.erase(std::unique(ents.begin(),ents.end()),ents.end());
                        if((int)ents.size()>CBMAXENT) ents.resize(CBMAXENT);
                        for(int et:ents){ cc.clear();
                            { std::chrono::steady_clock::time_point _r0;
                              if(CBPROF) _r0=std::chrono::steady_clock::now();
                            best_cell_contact_tl(TL,bi,et,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc,Kuse,cc,w2,&st.loads);
                              if(CBPROF){ double _dr=std::chrono::duration<double>(
                                    std::chrono::steady_clock::now()-_r0).count();
                                _Pragma("omp atomic") cb_t_retry += _dr;
                                _Pragma("omp atomic") cb_n_retry += 1.0; } }
                            for(auto&cd:cc){ allc.push_back(cd); allc_ct.push_back({et,et+pt}); } }
                    } else {
                        int cur=r; cc.clear();
                        std::chrono::steady_clock::time_point _s0;
                        if(CBPROF) _s0=std::chrono::steady_clock::now();
                        best_cell_contact_tl(TL,bi,cur,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc,Kuse,cc,w2,&st.loads);
                        if(CBPROF){ double _d2=std::chrono::duration<double>(
                                        std::chrono::steady_clock::now()-_s0).count();
                            #pragma omp atomic
                            cb_t_scan += _d2; }
                        if(cc.empty()){
                            std::vector<int> ents; ents.push_back(r);
                            for(int bay=0;bay<n_bays;bay++) for(const Placed& te:TL[bay]) if(te.ex>r) ents.push_back(te.ex);
                            std::sort(ents.begin(),ents.end()); ents.erase(std::unique(ents.begin(),ents.end()),ents.end());
                            for(int e:ents){ if(e==r)continue;
                                bool noroom = ARPRE_on() && !room_at(e,e+pt);
                                if(noroom){
                                    #pragma omp atomic
                                    cb_n_arskip += 1.0;
                                    // AUDIT: run the scan anyway and see whether the entry time we
                                    // were about to discard actually had a placement.  A nonzero
                                    // count means the precheck is not the necessary condition it
                                    // claims to be, and it is deleting real options.
                                    if(ARAUDIT_on()){
                                        cc.clear();
                                        best_cell_contact_tl(TL,bi,e,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc,Kuse,cc,w2,&st.loads);
                                        if(!cc.empty()){
                                            #pragma omp atomic
                                            cb_n_arbad += 1.0;
                                        }
                                    }
                                    continue;
                                }
                                cc.clear();
                                { std::chrono::steady_clock::time_point _r0;
                                  if(CBPROF) _r0=std::chrono::steady_clock::now();
                                best_cell_contact_tl(TL,bi,e,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc,Kuse,cc,w2,&st.loads);
                                  if(CBPROF){ double _dr=std::chrono::duration<double>(
                                        std::chrono::steady_clock::now()-_r0).count();
                                    _Pragma("omp atomic") cb_t_retry += _dr;
                                    _Pragma("omp atomic") cb_n_retry += 1.0; } }
                                if(!cc.empty()){cur=e;break;} }
                        }
                        for(auto&cd:cc){ allc.push_back(cd); allc_ct.push_back({cur,cur+pt}); }
                    }
                    // fallback when even the wait set found nothing: scan all exits (original path)
                    if(allc.empty() && CBWAIT>0){
                        std::vector<int> ents; ents.push_back(r);
                        for(int bay=0;bay<n_bays;bay++) for(const Placed& te:TL[bay]) if(te.ex>r) ents.push_back(te.ex);
                        std::sort(ents.begin(),ents.end()); ents.erase(std::unique(ents.begin(),ents.end()),ents.end());
                        for(int e:ents){
                            if(ARPRE_on() && !room_at(e,e+pt)) continue;
                            cc.clear();
                            { std::chrono::steady_clock::time_point _r0;
                              if(CBPROF) _r0=std::chrono::steady_clock::now();
                            best_cell_contact_tl(TL,bi,e,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc,Kuse,cc,w2,&st.loads);
                              if(CBPROF){ double _dr=std::chrono::duration<double>(
                                    std::chrono::steady_clock::now()-_r0).count();
                                _Pragma("omp atomic") cb_t_retry += _dr;
                                _Pragma("omp atomic") cb_n_retry += 1.0; } }
                            if(!cc.empty()){ for(auto&cd:cc){ allc.push_back(cd); allc_ct.push_back({e,e+pt}); } break; } }
                    }
                    if(allc.empty()){ outv.push_back(st); continue; }
                    for(size_t ci=0;ci<allc.size();ci++){
                        auto& cd=allc[ci]; int en=allc_ct[ci].first, exx=allc_ct[ci].second;
                        int bay=cd[0],oi=cd[1],ix=cd[2],iy=cd[3],ct=cd[4];
                        CBState c; c.flat=st.flat; c.placed=st.placed; c.loads=st.loads; c.nplaced=st.nplaced+1;
                        c.flat.push_back(bi);c.flat.push_back(bay);c.flat.push_back(oi);c.flat.push_back(ix);c.flat.push_back(iy);c.flat.push_back(en);c.flat.push_back(exx);
                        c.placed[bi]=1; c.loads[bay]+=wl;
                        c.gt = st.gt + (exx>dd?(double)(exx-dd):0.0);
                        double pen=(bay<(int)pr.size())?(mxp[bi]-pr[bay]):mxp[bi];
                        c.gz3=st.gz3+pen; c.gcontact=st.gcontact+ct;
                        outv.push_back(std::move(c));
                    }
                }
            }
            std::vector<CBState> children;
            std::vector<int> parent_of;      // for the per-parent quota below
            for(int pi=0;pi<(int)perstate.size();pi++)
                for(auto& c:perstate[pi]){ children.push_back(std::move(c)); parent_of.push_back(pi); }
            if(children.empty()) return {1e18,{}};
            int nch=(int)children.size();
            std::vector<std::pair<double,int>> keyed(nch);
            // THROUGHPUT-OBJECTIVE beam mode (OGC_THRUBEAM=1, high-density): rank states almost
            // purely by tardiness + an AMPLIFIED future-tardiness lookahead (OGC_THRUHZ x hz), and
            // DROP the Z3 bay-preference term (noise when Z1 dominates the objective).  Contact stays
            // a deep tie-break.  The idea (user): change the beam's OBJECTIVE so its search is steered
            // toward on-time throughput on congested instances instead of tight/preferred packing.
            static const int THRUBEAM=[](){const char*e=getenv("OGC_THRUBEAM");return(e&&e[0]=='1')?1:0;}();
            static const double THRUHZ=[](){const char*e=getenv("OGC_THRUHZ");return e?atof(e):3.0;}();
            #pragma omp parallel for schedule(dynamic)
            for(int i=0;i<nch;i++){ CBState& c=children[i];
                double hz = (c.nplaced<nb)? wb_hz1(c.flat,c.placed,areas,area_total,avg_a):0.0;
                if(THRUBEAM)
                    // KEEP Z3 (dropping it blew up Z3 for a tiny Z1 gain -> net worse); only AMPLIFY
                    // the future-tardiness lookahead so the search still steers away from congestion.
                    keyed[i]={ w1*(c.gt + THRUHZ*hz) + w3*c.gz3 - mu*c.gcontact + w2*obj2f(c.loads), i };
                else
                    keyed[i]={ w1*c.gt + w3*c.gz3 - mu*c.gcontact + w2*obj2f(c.loads) + w1*hz, i };
            }
            std::sort(keyed.begin(),keyed.end(),[](const std::pair<double,int>&a,const std::pair<double,int>&b){return a.first<b.first;});
            // CANONICAL DEDUP: two states that placed the SAME blocks in the same bays at the
            // same times are the same layout however they were reached, yet they occupy two
            // beam slots.  Hash the placement set order-INDEPENDENTLY (XOR of per-block field
            // hashes, so permutations collide) and keep only the best-ranked representative.
            // Frees width for genuinely different structures.  env OGC_DEDUP=0 disables.
            // MEASURED INERT: identical to the last digit on prob_30/39/22/26/35.  Our beam
            // uses a FIXED dispatch order, so every state at level k has placed the same block
            // SET and differs only in placements -- two states can only collide if they made
            // identical choices, which candidate generation already prevents.  The reference
            // needs this because its orders vary.  Left in (it is free) but expect nothing.
            static const bool DEDUP=[](){const char*e=getenv("OGC_DEDUP");return !(e&&e[0]=='0');}();
            if(DEDUP){
                std::unordered_set<uint64_t> seen; seen.reserve((size_t)nch*2);
                int wk=0;
                for(int i=0;i<nch;i++){
                    const std::vector<int>& f=children[keyed[i].second].flat;
                    uint64_t h=0;
                    for(size_t q=0;q+6<f.size();q+=7){
                        uint64_t e=1469598103934665603ULL;
                        for(int z=0;z<7;z++){ e^=(uint64_t)(uint32_t)f[q+z]; e*=1099511628211ULL; }
                        h^=e;                      // XOR -> block order does not matter
                    }
                    if(seen.insert(h).second) keyed[wk++]=keyed[i];
                }
                if(wk>0){ keyed.resize(wk); nch=wk; }
            }
            // OBJECTIVE-KEY DEDUP -- TRIED AND REFUTED, kept as a note because the idea is
            // a natural one.  x, y and orientation appear nowhere in the objective (w1*Z1 sees
            // entry times, w2*Z2 and w3*Z3 see bay assignment), so states agreeing on
            // (block, bay, entry) score identically forever and holding both looked like two
            // beam slots spent on one point of the objective space.
            //
            // MEASURED: the duplicate rate is exactly 0%.  Hashing only (block, bay, entry) and
            // capping at ONE representative per key left every state standing --
            //   prob_38 11478/11478, prob_20 16153/16153, prob_30 6884/6884, prob_29 12846/12846.
            // The dispatch order is fixed, so every state at a level has placed the same block
            // SET; distinct parents therefore hand distinct keys to their children by induction,
            // and best_cell_contact returns at most one position per (bay, entry), so a single
            // parent never produces two candidates that agree on the key either.  Collisions are
            // structurally impossible, not merely rare.
            //
            // The useful reading is the opposite of the premise: the beam does not waste width on
            // geometric variants, it never explores geometry at all.  Each (bay, entry) choice
            // carries exactly one contact-greedy position, so a state whose packing turns out
            // badly has no sibling with the same assignment and a different layout to fall back
            // on.
            // ADMISSIBLE PRUNING: a child whose lower bound already meets the best COMPLETE
            // solution seen cannot lead to a better one, so dropping it frees a beam slot for
            // a branch that still can -- the same width then searches strictly more.
            // DEFAULT OFF -- measured a LOSS.  60s, B=96: prob_39 8,077,283 -> 9,149,439
            // (+13.3%), prob_26 8,820,294 -> 9,770,979 (+10.8%), prob_30 +0.6%, prob_22 tie.
            // The bound has to omit Z2 (the range of u_j*load_j can SHRINK as load is added,
            // so no positive bound on it is admissible), which leaves it far below the true
            // objective -- too loose to cut anything, while the live-incumbent rollout it
            // needs costs real time.  Pure overhead, so it buys negative search.
            static const bool ADMP=[](){const char*e=getenv("OGC_ADMP");return (e&&e[0]=='1');}();
            if(ADMP && inc_obj<1e17){
                int wkeep=0;
                for(int i=0;i<nch;i++)
                    if(wb_lb(children[keyed[i].second],w1,w3,mxp) < inc_obj-1e-9) keyed[wkeep++]=keyed[i];
                if(wkeep>0){ keyed.resize(wkeep); nch=wkeep; }
            }
            int keep=std::min(nch,B);
            // PER-PARENT QUOTA (the reference caps children per parent at max(2,(B+1)/2)).
            // Without it one strong parent can fill the entire next beam with its own
            // children, so the beam carries B copies of a single structure and its width
            // buys nothing.  The quota costs a little rank quality per level and buys
            // structural diversity, which is what a beam is for.  env OGC_PPQ=0 disables.
            static const bool PPQ=[](){const char*e=getenv("OGC_PPQ");return !(e&&e[0]=='0');}();
            std::vector<CBState> nb2; nb2.reserve(keep);
            if(PPQ && (int)perstate.size()>1){
                const int quota=std::max(2,(B+1)/2);
                std::vector<int> taken(perstate.size(),0);
                for(int i=0;i<nch && (int)nb2.size()<keep;i++){
                    int idx=keyed[i].second, par=parent_of[idx];
                    if(taken[par]>=quota) continue;
                    taken[par]++; nb2.push_back(std::move(children[idx]));
                }
                for(int i=0;i<nch && (int)nb2.size()<keep;i++){   // top up if the quota starved us
                    int idx=keyed[i].second;
                    if(children[idx].flat.empty() && children[idx].nplaced==0) continue;
                    nb2.push_back(std::move(children[idx]));
                }
            } else {
                for(int i=0;i<keep;i++) nb2.push_back(std::move(children[keyed[i].second]));
            }
            beam.swap(nb2);
            // Keep a LIVE incumbent so the bound above has something to prune against.
            // Without this inc_obj only exists after the last level and the pruning never
            // fires at all.  One greedy completion of the current leader every ~10th level
            // is ~10 rollouts per beam -- cheap next to B*n state expansions -- and it is
            // exactly the quantity the bound needs.
            if(ADMP_LIVE && !beam.empty() && (level%std::max(1,nord/10)==0)){
                auto res0=greedy_contact_from(beam[0].flat,order,step,pos_lam,prefw,mu,w1,w3,fut_beta,mean_proc);
                const std::vector<int>& f0=res0.second;
                if((int)f0.size()==7*nb){
                    double z1=0,z3=0; std::vector<double> ld(n_bays,0.0);
                    for(size_t i2=0;i2+6<f0.size();i2+=7){ int b2=f0[i2],bay2=f0[i2+1],ex2=f0[i2+6];
                        double dd2=shapes[b2].due; if(ex2>dd2) z1+=ex2-dd2;
                        z3 += (bay2<(int)shapes[b2].prefs.size())?(mxp[b2]-shapes[b2].prefs[bay2]):mxp[b2];
                        ld[bay2]+=workloads[b2]; }
                    double ob0=w1*z1+w2*std::floor(obj2f(ld))+w3*z3;
                    if(ob0<inc_obj) inc_obj=ob0;
                }
            }
        }
        double best_obj=1e18; std::vector<int> best_flat;
        for(auto& st: beam){
            std::chrono::steady_clock::time_point _g0;
            if(CBPROF) _g0=std::chrono::steady_clock::now();
            auto res = greedy_contact_from(st.flat, order, step, pos_lam, prefw, mu, w1, w3, fut_beta, mean_proc);
            if(CBPROF) cb_t_roll += std::chrono::duration<double>(
                           std::chrono::steady_clock::now()-_g0).count();
            std::vector<int>& flat = res.second;
            if((int)flat.size()!=7*nb) continue;
            double z1=0,z3=0; std::vector<double> loads(n_bays,0.0);
            for(size_t i=0;i+6<flat.size();i+=7){ int b=flat[i],bay=flat[i+1],ex2=flat[i+6];
                double dd2=shapes[b].due; if(ex2>dd2) z1+=ex2-dd2;
                z3 += (bay<(int)shapes[b].prefs.size())?(mxp[b]-shapes[b].prefs[bay]):mxp[b];
                loads[bay]+=workloads[b];
            }
            double ob = w1*z1 + w2*std::floor(obj2f(loads)) + w3*z3;
            if(ob<inc_obj) inc_obj=ob;
            if(ob<best_obj){best_obj=ob;best_flat=flat;}
        }
        return {best_obj,best_flat};
    }

    // Event-driven greedy completion from the CURRENT timeline.  Places every UNPLACED
    // block (leftbottom, earliest feasible event time) in `prio` dispatch order and returns
    // total tardiness of the newly-placed blocks.  The timeline is cloned and restored, so
    // this is a pure evaluation (the beam calls it thousands of times to score branches).
    // want_full=true also returns the placements [bid,bay,ori,ix,iy,en,ex]* for the fine
    // final solution.  step = grid step (coarse for scoring, 1 for the final build).
    // Same as greedy_rollout but the starting placement state is passed in as a flat array
    // [bid,bay,ori,ix,iy,en,ex]* (built into the timeline in C++), so the caller need not
    // reconstruct the engine via N pybind add() calls -- removes the Python hot-loop overhead.
    std::pair<double,std::vector<int>>
    greedy_rollout_from(std::vector<int> state_flat, std::vector<double> prio, int cur0,
                        int step, bool want_full, int maxplace, bool approx,
                        double w1p=0.0, double w3p=0.0, double prefw=0.0){
        auto saved = timeline;
        for(auto& t : timeline) t.clear();
        for(size_t i=0;i+6<state_flat.size();i+=7)
            add(state_flat[i+1],state_flat[i],state_flat[i+2],
                (double)state_flat[i+3],(double)state_flat[i+4],state_flat[i+5],state_flat[i+6]);
        auto r = greedy_rollout_core(prio,cur0,step,want_full,maxplace,approx,w1p,w3p,prefw);
        timeline = saved;
        return r;
    }
    std::pair<double,std::vector<int>>
    greedy_rollout(std::vector<double> prio, int cur0, int step, bool want_full, int maxplace, bool approx,
                   double w1p=0.0, double w3p=0.0, double prefw=0.0){
        auto saved = timeline;
        auto r = greedy_rollout_core(prio,cur0,step,want_full,maxplace,approx,w1p,w3p,prefw);
        timeline = saved;
        return r;
    }
    // ===================== WIDE-BEAM (no-rollout) constructor =====================
    // Friend's method: keep B partial states ("multiverses"); branch the highest-priority
    // ready block on per-bay K diverse crane-aware feasible candidate positions (NOT
    // leftbottom -- diverse spread, the beam's composite score picks the tight ones); score
    // children by g + congestion-h (cheap area-relaxed schedule, no rollout); keep top-B;
    // late-prune.  Wide breadth + cheap accurate scoring; everything in C++ so K can be ~30.
    void load_flat(const std::vector<int>& flat){
        for(auto& t:timeline) t.clear();
        for(size_t i=0;i+6<flat.size();i+=7){
            int bid=flat[i],bay=flat[i+1],orient=flat[i+2];
            double ox=(double)flat[i+3],oy=(double)flat[i+4]; int en=flat[i+5],ex=flat[i+6];
            const OrientData& od=shapes[bid].orients[orient];
            timeline[bay].push_back({en,ex,bid,orient,ox,oy,od.x0+ox,od.y0+oy,od.x1+ox,od.y1+oy,bay});
        }
    }
    // Collect feasible (orient,ix,iy) for a block in ONE bay (sweep-pruned, exact set),
    // then pick up to K positions spread across the bay (diverse, no leftbottom bias):
    // sort by (iy,ix) and take K evenly-spaced.  Timeline must already hold the state.
    // ---- footprint cache: union of a block-orient's layer touch-rasters (for contact) ----
    struct FP { int cx0,cy0,cw,ch; std::vector<char> g; };
    std::map<int,FP> _fpcache;
    const FP& footprint(int bid,int oi){
        int key=bid*64+oi; auto it=_fpcache.find(key); if(it!=_fpcache.end()) return it->second;
        const OrientData& od=shapes[bid].orients[oi];
        int cx0=INT_MAX,cy0=INT_MAX,cx1=INT_MIN,cy1=INT_MIN;
        for(const auto&L:od.layers){ if(L.cw==0)continue;
            cx0=std::min(cx0,L.cx0); cy0=std::min(cy0,L.cy0);
            cx1=std::max(cx1,L.cx0+L.cw); cy1=std::max(cy1,L.cy0+L.ch); }
        FP fp;
        if(cx0==INT_MAX){ fp.cx0=fp.cy0=fp.cw=fp.ch=0; return _fpcache.emplace(key,std::move(fp)).first->second; }
        fp.cx0=cx0; fp.cy0=cy0; fp.cw=cx1-cx0; fp.ch=cy1-cy0; fp.g.assign((size_t)fp.cw*fp.ch,0);
        for(const auto&L:od.layers){ if(L.cw==0)continue;
            for(int r=0;r<L.ch;r++) for(int c=0;c<L.cw;c++)
                if(L.bits[(size_t)r*L.wpr+(c>>6)] & (1ULL<<(c&63))){
                    int gc=(L.cx0+c)-cx0, gr=(L.cy0+r)-cy0;
                    if(gc>=0&&gc<fp.cw&&gr>=0&&gr<fp.ch) fp.g[(size_t)gr*fp.cw+gc]=1; }
        }
        return _fpcache.emplace(key,std::move(fp)).first->second;
    }
    // thread-safe placement_feasible against a passed bay timeline (for parallel wide_beam).
    bool placement_feasible_tl(const std::vector<Placed>& btl,int bay,int bid,int orient,double x,double y,int en,int ex){
        const OrientData& od=shapes[bid].orients[orient];
        double nx0=od.x0+x,ny0=od.y0+y,nx1=od.x1+x,ny1=od.y1+y;
        // bay containment, exact: the grader rejects any footprint outside the bay with
        // `outside.area > 0`, so a 1e-6 slack here is slack in the direction that gets a
        // solution thrown out.  Equality still passes, so flush-against-the-wall stays legal.
        if(nx0<0.0||ny0<0.0||nx1>bw[bay]||ny1>bh[bay]) return false;
        for(const Placed& te : btl){
            if(!(en < te.ex && te.en < ex)) continue;
            if(!bb_ov(nx0,ny0,nx1,ny1,te.bx0,te.by0,te.bx1,te.by1)) continue;
            if(te.en <= en && en < te.ex){ if(desc_hit(bid,orient,x,y,te)) return false; }
            if(te.en < ex && ex <= te.ex){ if(desc_hit(bid,orient,x,y,te)) return false; }
            if(en <= te.en && te.en < ex){ if(desc_hit_rev(te,bid,orient,x,y)) return false; }
            if(en < te.ex && te.ex <= ex){ if(desc_hit_rev(te,bid,orient,x,y)) return false; }
        }
        return true;
    }
    // bay occupancy grid (union footprint of blocks present during [en,ex)).
    void buildOcc(const std::vector<Placed>& btl,int en,int ex,int bayW,int bayH,std::vector<char>& occ){
        occ.assign((size_t)bayW*bayH,0);
        for(const Placed& te: btl){
            if(!(en<te.ex && te.en<ex)) continue;
            const FP& fp=footprint(te.bid,te.orient);
            int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
            for(int r=0;r<fp.ch;r++) for(int c=0;c<fp.cw;c++) if(fp.g[(size_t)r*fp.cw+c]){
                int wx=tox+fp.cx0+c, wy=toy+fp.cy0+r;
                if(wx>=0&&wx<bayW&&wy>=0&&wy<bayH) occ[(size_t)wy*bayW+wx]=1; }
        }
    }
    // CONTACT PERIMETER (tight-packing quality): count of the block's boundary cells whose
    // outward 4-neighbour is a bay wall or an occupied cell.  High = nestled tightly.
    int contact_at(const FP& fp,int ix,int iy,const std::vector<char>& occ,int bayW,int bayH){
        static const int DX[4]={1,-1,0,0}, DY[4]={0,0,1,-1};
        int ct=0;
        for(int r=0;r<fp.ch;r++) for(int c=0;c<fp.cw;c++){
            if(!fp.g[(size_t)r*fp.cw+c]) continue;
            for(int k=0;k<4;k++){
                int nc=c+DX[k], nr=r+DY[k];
                if(nc>=0&&nc<fp.cw&&nr>=0&&nr<fp.ch && fp.g[(size_t)nr*fp.cw+nc]) continue; // internal edge
                int wx=ix+fp.cx0+nc, wy=iy+fp.cy0+nr;
                if(wx<0||wx>=bayW||wy<0||wy>=bayH){ ct++; continue; }      // bay wall
                if(occ[(size_t)wy*bayW+wx]) ct++;                          // touches a block
            }
        }
        return ct;
    }
    // ---- PER-LAYER footprint cache + layered contact (more accurate 3D tightness) ----
    struct FPL { int nl; std::vector<int> cx0,cy0,cw,ch; std::vector<std::vector<char>> g; };
    std::map<int,FPL> _fplcache;
    bool _perlayer=false;
    const FPL& footprintL(int bid,int oi){
        int key=bid*64+oi; auto it=_fplcache.find(key); if(it!=_fplcache.end()) return it->second;
        const OrientData& od=shapes[bid].orients[oi]; int nl=(int)od.layers.size();
        FPL fp; fp.nl=nl; fp.cx0.assign(nl,0);fp.cy0.assign(nl,0);fp.cw.assign(nl,0);fp.ch.assign(nl,0);fp.g.resize(nl);
        for(int k=0;k<nl;k++){ const LayerData&L=od.layers[k];
            if(L.cw==0) continue;
            fp.cx0[k]=L.cx0; fp.cy0[k]=L.cy0; fp.cw[k]=L.cw; fp.ch[k]=L.ch; fp.g[k].assign((size_t)L.cw*L.ch,0);
            for(int r=0;r<L.ch;r++) for(int c=0;c<L.cw;c++)
                if(L.bits[(size_t)r*L.wpr+(c>>6)] & (1ULL<<(c&63))) fp.g[k][(size_t)r*L.cw+c]=1;
        }
        return _fplcache.emplace(key,std::move(fp)).first->second;
    }
    // per-layer occupancy: occL[k] = union of present blocks' layer-k footprints (layer-aligned).
    void buildOccL(const std::vector<Placed>& btl,int en,int ex,int bayW,int bayH,int maxL,
                   std::vector<std::vector<char>>& occL){
        occL.assign(maxL, std::vector<char>((size_t)bayW*bayH,0));
        for(const Placed& te: btl){
            if(!(en<te.ex && te.en<ex)) continue;
            const FPL& fp=footprintL(te.bid,te.orient);
            int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
            for(int k=0;k<fp.nl && k<maxL;k++){ if(fp.cw[k]==0) continue;
                for(int r=0;r<fp.ch[k];r++) for(int c=0;c<fp.cw[k];c++) if(fp.g[k][(size_t)r*fp.cw[k]+c]){
                    int wx=tox+fp.cx0[k]+c, wy=toy+fp.cy0[k]+r;
                    if(wx>=0&&wx<bayW&&wy>=0&&wy<bayH) occL[k][(size_t)wy*bayW+wx]=1; }
            }
        }
    }
    int contact_at_layered(const FPL& fp,int ix,int iy,const std::vector<std::vector<char>>& occL,int bayW,int bayH){
        static const int DX[4]={1,-1,0,0}, DY[4]={0,0,1,-1};
        int ct=0;
        for(int k=0;k<fp.nl && k<(int)occL.size();k++){ if(fp.cw[k]==0) continue;
            const std::vector<char>& oc=occL[k]; int cw=fp.cw[k],ch=fp.ch[k];
            for(int r=0;r<ch;r++) for(int c=0;c<cw;c++){
                if(!fp.g[k][(size_t)r*cw+c]) continue;
                for(int q=0;q<4;q++){ int nc=c+DX[q], nr=r+DY[q];
                    if(nc>=0&&nc<cw&&nr>=0&&nr<ch && fp.g[k][(size_t)nr*cw+nc]) continue;
                    int wx=ix+fp.cx0[k]+nc, wy=iy+fp.cy0[k]+nr;
                    if(wx<0||wx>=bayW||wy<0||wy>=bayH){ ct++; continue; }
                    if(oc[(size_t)wy*bayW+wx]) ct++;
                }
            }
        }
        return ct;
    }
    // per-bay: feasible positions, scored by CONTACT (desc) with low-top tie-break, top-K
    // spread across columns.  outsel = (orient,ix,iy,contact).  NOT leftbottom.
    void scan_bay_contact(const std::vector<Placed>& btl,int bid,int bay,int en,int ex,int step,int K,
                          std::vector<std::array<int,4>>& outsel){
        const BlockShape& bs=shapes[bid]; int norient=(int)bs.orients.size();
        double bw_j=bw[bay], bh_j=bh[bay];
        int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
        int bayH=(int)std::ceil(bh_j), bayW=(int)std::ceil(bw_j); int wpr=(bayW+64)>>6;
        std::vector<std::vector<uint64_t>> F;
        bool use_sweep = RASTER && maxL>0 && bayH>0 && bayH<20000;
        if(use_sweep){
            F.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
            for(const Placed& te: btl){
                if(!(en < te.ex && te.en < ex)) continue;
                bool newdesc=(te.en<=en&&en<te.ex)||(te.en<ex&&ex<=te.ex);
                bool tedesc =(en<=te.en&&te.en<ex)||(en<te.ex&&te.ex<=ex);
                if(!newdesc&&!tedesc) continue;
                const OrientData& eod=shapes[te.bid].orients[te.orient]; int ne=(int)eod.layers.size();
                int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
                for(int j=0;j<ne;j++){ const LayerData& L=eod.layers[j]; if(L.npts<3)continue;
                    if(newdesc){ int hi=std::min(j,maxL-1); for(int k=0;k<=hi;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                    if(tedesc){ for(int k=std::max(j,0);k<maxL;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                }
            }
        }
        std::vector<char> occ; std::vector<std::vector<char>> occL;
        if(_perlayer) buildOccL(btl,en,ex,bayW,bayH,maxL,occL);
        else buildOcc(btl,en,ex,bayW,bayH,occ);
        // (contact, orient, ix, iy) for each feasible position
        std::vector<std::array<int,4>> all;
        for(int oi=0; oi<norient; oi++){
            const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
            double w=od.x1-od.x0, h=od.y1-od.y0;
            if(w>bw_j+1e-9 || h>bh_j+1e-9) continue;
            const FP& fp=footprint(bid,oi);
            int lo_x=(int)std::ceil(-od.x0), hi_x=(int)std::floor(bw_j-od.x1);
            int lo_y=(int)std::ceil(-od.y0), hi_y=(int)std::floor(bh_j-od.y1);
            size_t before=all.size();
            // one candidate position: filter, then score by contact
            auto try_pos=[&](int ix,int iy){
                bool ok;
                if(use_sweep){ bool clear=true;
                    for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                        if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                    ok = clear ? true : placement_feasible_tl(btl,bay,bid,oi,(double)ix,(double)iy,en,ex);
                } else ok = placement_feasible_tl(btl,bay,bid,oi,(double)ix,(double)iy,en,ex);
                if(ok){ int ct = _perlayer ? contact_at_layered(footprintL(bid,oi),ix,iy,occL,bayW,bayH)
                                           : contact_at(fp,ix,iy,occ,bayW,bayH);
                        all.push_back({ct,oi,ix,iy}); }
            };
            // CONTACT CANDIDATE POSITIONS.  This beam ranks by contact, so a position that
            // touches nothing can never win -- and yet a full grid sweep evaluates every one
            // of them.  Measured on prob_20: 202M cells, 55.6s of a 56.2s call, on bays of
            // 40500 cells each.
            //
            // A contact needs an edge to coincide with something, so collect the x offsets
            // that put this block's left or right edge against a present block's opposite
            // edge or against a wall, the same for y, and try the combinations -- the corner
            // positions.  prob_20 carries roughly ten blocks per bay at any instant, so that
            // is ~22 x 22 = 484 candidates where the sweep had 40500.
            //
            // It is a restriction, not an equivalence: a position touching in x while free in
            // y is a real contact this set does not contain.  So when the corner set yields
            // nothing feasible, fall back to the full sweep for this orientation rather than
            // let the block go unplaceable -- correctness of the beam does not depend on the
            // shortcut, only its speed.  env OGC_CPOS=0 pins the old sweep.
            static const bool CPOS=[](){const char*e=getenv("OGC_CPOS");return !(e&&e[0]=='0');}();
            if(CPOS){
                std::vector<int> xs{lo_x,hi_x}, ys{lo_y,hi_y};
                for(const Placed& te: btl){
                    if(!(en < te.ex && te.en < ex)) continue;
                    int xa=(int)std::ceil(te.bx1-od.x0), xb=(int)std::floor(te.bx0-od.x1);
                    if(xa>=lo_x&&xa<=hi_x) xs.push_back(xa);
                    if(xb>=lo_x&&xb<=hi_x) xs.push_back(xb);
                    int ya=(int)std::ceil(te.by1-od.y0), yb=(int)std::floor(te.by0-od.y1);
                    if(ya>=lo_y&&ya<=hi_y) ys.push_back(ya);
                    if(yb>=lo_y&&yb<=hi_y) ys.push_back(yb);
                }
                std::sort(xs.begin(),xs.end()); xs.erase(std::unique(xs.begin(),xs.end()),xs.end());
                std::sort(ys.begin(),ys.end()); ys.erase(std::unique(ys.begin(),ys.end()),ys.end());
                for(int ix: xs) for(int iy: ys) try_pos(ix,iy);
            }
            if(!CPOS || all.size()==before)
                for(int ix=lo_x; ix<=hi_x; ix+=step) for(int iy=lo_y; iy<=hi_y; iy+=step) try_pos(ix,iy);
        }
        int tot=(int)all.size();
        if(tot==0) return;
        // rank by CONTACT desc, then low top-edge (iy) -> tight, high-quality positions.
        std::sort(all.begin(),all.end(),[](const std::array<int,4>&a,const std::array<int,4>&b){
            if(a[0]!=b[0]) return a[0]>b[0]; return a[3]<b[3]; });
        if(tot<=K){ for(auto&p:all) outsel.push_back({p[1],p[2],p[3],p[0]}); return; }
        // take top-K by contact but spread in x so the K aren't all the same column
        int xthr=(int)std::max(1.0, bw_j/(double)(K));
        std::vector<int> chosenx;
        for(auto& p : all){ if((int)outsel.size()>=K) break;
            bool far=true; for(int cx:chosenx) if(std::abs(p[2]-cx)<xthr){far=false;break;}
            if(far){ outsel.push_back({p[1],p[2],p[3],p[0]}); chosenx.push_back(p[2]); } }
        for(auto& p : all){ if((int)outsel.size()>=K) break;
            bool dup=false; for(auto&q:outsel) if(q[0]==p[1]&&q[1]==p[2]&&q[2]==p[3]){dup=true;break;}
            if(!dup) outsel.push_back({p[1],p[2],p[3],p[0]}); }
    }
    // FREE-CAPACITY-INTEGRAL Z1 tail heuristic (ported from the reference beamsolver _h_z1):
    // remaining blocks, due-sorted cumulative area demand D_k, are poured into the state's
    // free-capacity integral F(t) (rate = area_total - occupancy*avg_area); the k-th estimated
    // completion past due_k is future tardiness the exact g cannot see yet.  Predicts real
    // congestion delay far better than a flat area relaxation.  Returns raw tardiness.
    // ADMISSIBLE LOWER BOUND on a partial beam state (idea 3).
    // Every term must be a bound that CANNOT overshoot, or the beam prunes the optimum:
    //   Z1  -- tardiness already incurred.  Unplaced blocks can only add to it.
    //   Z3  -- penalty already incurred, plus, for each UNPLACED block, the smallest penalty
    //          any bay could give it (0 whenever some bay is its favourite, but not always).
    //   Z2  -- the range of u_j*load_j can still SHRINK as load is added, so no positive
    //          bound is safe.  Left out entirely rather than risk pruning the optimum.
    // The result is a true lower bound on any completion of this state, so a state whose
    // bound already meets the incumbent cannot lead anywhere better.
    double wb_lb(const CBState& st,double w1,double w3,const std::vector<double>& mxp) const {
        double z3rest=0.0;
        for(int b=0;b<(int)st.placed.size();b++){
            if(st.placed[b]) continue;
            const auto& pr=shapes[b].prefs;
            double best=mxp[b];
            for(int j=0;j<n_bays && j<(int)pr.size();j++){
                double pen=mxp[b]-pr[j];
                if(pen<best) best=pen;
            }
            z3rest+=best;
        }
        return w1*st.gt + w3*(st.gz3+z3rest);
    }

    double wb_hz1(const std::vector<int>& flat, const std::vector<char>& placed,
                  const std::vector<double>& areas, double area_total, double avg_a){
        int nb=(int)shapes.size();
        std::vector<std::pair<int,double>> ev;
        for(size_t i=0;i+6<flat.size();i+=7){ int en=flat[i+5],ex=flat[i+6];
            ev.push_back({en,1.0}); ev.push_back({ex,-1.0}); }
        std::vector<std::pair<int,double>> rem; int minrel=INT_MAX;
        for(int b=0;b<nb;b++) if(!placed[b]){ rem.push_back({(int)shapes[b].due,areas[b]}); minrel=std::min(minrel,(int)shapes[b].rt); }
        if(rem.empty()) return 0.0;
        std::sort(rem.begin(),rem.end());
        std::sort(ev.begin(),ev.end());
        double t=(minrel==INT_MAX)?0.0:(double)minrel;
        double F=0.0, occ=0.0, tardy=0.0, D=0.0; int idx=0;
        while(idx<(int)ev.size() && (double)ev[idx].first<=t){ occ+=ev[idx].second; idx++; }
        for(auto& rd : rem){
            int due_k=rd.first; D += rd.second;
            while(true){
                double cap=std::max(area_total*0.15, area_total-occ*avg_a);
                double nxt=(idx<(int)ev.size())?(double)ev[idx].first:1e18;
                double need_t=(D-F)/cap;
                if(t+need_t<=nxt){ double tau=t+need_t; if(tau>due_k) tardy+=(tau-due_k); F=D; if(tau>t)t=tau; break; }
                else { F+=cap*(nxt-t); t=nxt; occ+=ev[idx].second; idx++; }
            }
        }
        return tardy;
    }
    // Exposed wrapper: free-capacity-integral future-tardiness estimate for a PARTIAL solution
    // (flat = placed blocks) -- the reference beam's h_z1 rank term.  Lets a Python contact
    // beam add w1*hz1_est(...) so it foresees congestion delay (recovers Z1 the myopic rank loses).
    double hz1_est(std::vector<int> flat, std::vector<double> areas){
        int nb=(int)shapes.size(); std::vector<char> placed(nb,0);
        for(size_t i=0;i+6<flat.size();i+=7) placed[flat[i]]=1;
        double area_total=0; for(int j=0;j<n_bays;j++) area_total+=bw[j]*bh[j];
        double avg_a=0; for(int b=0;b<nb;b++) avg_a+=areas[b]; avg_a = nb? avg_a/nb : 1.0;
        return wb_hz1(flat,placed,areas,area_total,avg_a);
    }
    // WATERFILL admissible lower bound on final obj2 (load imbalance), ported from the
    // reference _h_obj2: pour remaining workload w_rem into the lower u_i*L_i levels; the
    // reachable min of max_ij|u_i L_i - u_j L_j| is a true LB.
    double wb_hobj2(const std::vector<double>& loads, const std::vector<double>& u, double w_rem){
        int m=n_bays; if(m<2) return 0.0;
        std::vector<std::pair<double,double>> v(m);
        for(int i=0;i<m;i++) v[i]={u[i]*loads[i], u[i]};
        std::sort(v.begin(),v.end());
        double vmax=v[m-1].first, rem=w_rem, level=v[0].first, caps=0.0; int idx=0;
        while(rem>1e-12 && level<vmax-1e-12){
            while(idx<m && v[idx].first<=level+1e-12){ caps+=1.0/v[idx].second; idx++; }
            double nxt = idx<m? v[idx].first : vmax; nxt=std::min(nxt,vmax);
            double need=(nxt-level)*caps;
            if(need>=rem){ level += (caps>0.0)? rem/caps : 0.0; rem=0.0; }
            else { rem-=need; level=nxt; }
        }
        return std::max(0.0, vmax-level);
    }
    void load_flat_into(const std::vector<int>& flat, std::vector<std::vector<Placed>>& TL){
        for(auto& t:TL) t.clear();
        for(size_t i=0;i+6<flat.size();i+=7){
            int bid=flat[i],bay=flat[i+1],orient=flat[i+2];
            double ox=(double)flat[i+3],oy=(double)flat[i+4]; int en=flat[i+5],ex=flat[i+6];
            const OrientData& od=shapes[bid].orients[orient];
            TL[bay].push_back({en,ex,bid,orient,ox,oy,od.x0+ox,od.y0+oy,od.x1+ox,od.y1+oy,bay});
        }
    }
    void scan_all_bays(const std::vector<std::vector<Placed>>& TL,int bid,int en,int ex,int step,int K,std::vector<std::array<int,5>>& out){
        out.clear();
        for(int bay=0;bay<n_bays;bay++){
            std::vector<std::array<int,4>> sel;
            scan_bay_contact(TL[bay],bid,bay,en,ex,step,K,sel);
            for(auto& s: sel) out.push_back({bay,s[0],s[1],s[2],s[3]});  // bay,orient,ix,iy,contact
        }
    }
    struct WBState { std::vector<int> flat; std::vector<char> placed; std::vector<double> loads; double gt, gz3, gcontact; int nplaced; };
    // FAITHFUL PORT (milestone 1): fixed-order depth-consistent beam with the reference's
    // ACCURATE scoring -- per-candidate objective-delta selection (d_rank), per-bay load
    // tracking, waterfill h_obj2, free-cap-integral h_z1, contact reward.  cps = candidates
    // kept per state (objective-selected), the reference's cand_per_state.
    std::pair<double,std::vector<int>>
    wide_beam(std::vector<int> order, std::vector<double> areas, std::vector<double> workloads,
              int B, int K, int step, double w1p, double w2p, double w3p, double mu,
              double time_budget_s, int nent, int cps){
        int nb=(int)shapes.size();
        std::vector<double> mxp(nb,0);
        double area_total=0; for(int j=0;j<n_bays;j++) area_total+=bw[j]*bh[j];
        double avg_a=0; for(int b=0;b<nb;b++) avg_a+=areas[b]; avg_a = nb? avg_a/nb : 1.0;
        double avg_ba = n_bays? area_total/n_bays : 1.0;
        std::vector<double> u(n_bays); for(int j=0;j<n_bays;j++) u[j]= (bw[j]*bh[j]>1e-9)? avg_ba/(bw[j]*bh[j]) : 1.0;
        for(int b=0;b<nb;b++){ const auto&pr=shapes[b].prefs; double mx=pr.empty()?0:pr[0]; for(double v:pr)if(v>mx)mx=v; mxp[b]=mx; }
        int nord=(int)order.size();
        std::vector<double> suffix_w(nord+1,0.0);
        for(int i=nord-1;i>=0;i--) suffix_w[i]=suffix_w[i+1]+workloads[order[i]];
        double mu_pos = 1e-3*std::min(w1p,w3p), wait_w = mu_pos*20.0;
        _perlayer = (std::getenv("OGC_PERLAYER")!=nullptr);
        for(int b=0;b<nb;b++) for(int oi=0;oi<(int)shapes[b].orients.size();oi++){ footprint(b,oi); if(_perlayer) footprintL(b,oi); }
        WBState init; init.placed.assign(nb,0); init.loads.assign(n_bays,0.0); init.gt=0; init.gz3=0; init.gcontact=0; init.nplaced=0;
        std::vector<WBState> beam; beam.push_back(std::move(init));
        auto t0=std::chrono::steady_clock::now();
        auto elapsed=[&](){ return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); };
        for(int level=0; level<nord; level++){
            if(elapsed()>time_budget_s) break;
            int bi=order[level]; int r=(int)shapes[bi].rt, pt=(int)shapes[bi].pt; double dd=shapes[bi].due;
            double wl=workloads[bi], w_rem=suffix_w[level+1];
            const auto& pr=shapes[bi].prefs;
            int nbeam=(int)beam.size();
            std::vector<std::vector<WBState>> perstate(nbeam);
            #pragma omp parallel
            {
                std::vector<std::vector<Placed>> TL(n_bays);
                std::vector<std::array<int,5>> lcand;
                #pragma omp for schedule(dynamic)
                for(int si=0; si<nbeam; si++){
                    WBState& st = beam[si];
                    load_flat_into(st.flat, TL);
                    std::vector<int> entries; entries.push_back(r);
                    for(int bay=0;bay<n_bays;bay++) for(const Placed& te: TL[bay]) if(te.ex>r) entries.push_back(te.ex);
                    std::sort(entries.begin(),entries.end()); entries.erase(std::unique(entries.begin(),entries.end()),entries.end());
                    // gather candidates over the earliest `nent` feasible entries
                    std::vector<std::array<int,6>> cl;   // bay,oi,ix,iy,ct,entry
                    int emin=-1, nfound=0;
                    for(int e : entries){
                        scan_all_bays(TL,bi,e,e+pt,step,K,lcand);
                        if(lcand.empty()) continue;
                        if(emin<0) emin=e;
                        for(auto& cd : lcand) cl.push_back({cd[0],cd[1],cd[2],cd[3],cd[4],e});
                        if(++nfound >= nent) break;
                    }
                    if(cl.empty()) continue;
                    // OBJECTIVE-DELTA (d_rank) selection: keep the top `cps` candidates by the
                    // true marginal objective, not raw contact -> finer positions finally help.
                    double hb = wb_hobj2(st.loads,u,w_rem);
                    std::vector<std::pair<double,int>> dr(cl.size());
                    for(size_t j=0;j<cl.size();j++){
                        int bay=cl[j][0],ct=cl[j][4],e=cl[j][5]; int ex=e+pt;
                        double tardy = ex>dd? (double)(ex-dd):0.0;
                        double pen = (bay<(int)pr.size())? (mxp[bi]-pr[bay]) : mxp[bi];
                        std::vector<double> nl=st.loads; nl[bay]+=wl;
                        double dbal = w2p*(wb_hobj2(nl,u,w_rem)-hb);
                        dr[j] = { w1p*tardy + w3p*pen + dbal - mu*(double)ct + wait_w*(double)(e-emin), (int)j };
                    }
                    std::sort(dr.begin(),dr.end(),[](const std::pair<double,int>&a,const std::pair<double,int>&b){return a.first<b.first;});
                    int keepc=std::min((int)dr.size(),cps);
                    auto& out=perstate[si];
                    for(int t=0;t<keepc;t++){
                        auto& cd=cl[dr[t].second];
                        int bay=cd[0],oi=cd[1],ix=cd[2],iy=cd[3],ct=cd[4],e=cd[5]; int ex=e+pt;
                        WBState c; c.flat=st.flat; c.placed=st.placed; c.loads=st.loads; c.nplaced=st.nplaced+1;
                        c.flat.push_back(bi); c.flat.push_back(bay); c.flat.push_back(oi);
                        c.flat.push_back(ix); c.flat.push_back(iy); c.flat.push_back(e); c.flat.push_back(ex);
                        c.placed[bi]=1; c.loads[bay]+=wl;
                        c.gt = st.gt + (ex>dd?(double)(ex-dd):0.0);
                        double pen=(bay<(int)pr.size())?(mxp[bi]-pr[bay]):mxp[bi];
                        c.gz3 = st.gz3 + pen; c.gcontact = st.gcontact + ct;
                        out.push_back(std::move(c));
                    }
                }
            }
            std::vector<WBState> children;
            for(auto& ps : perstate) for(auto& c : ps) children.push_back(std::move(c));
            if(children.empty()) break;
            int nch=(int)children.size();
            std::vector<std::pair<double,int>> keyed(nch);
            #pragma omp parallel for schedule(dynamic)
            for(int i=0;i<nch;i++){
                WBState& c=children[i];
                double hz = (c.nplaced<nb) ? wb_hz1(c.flat,c.placed,areas,area_total,avg_a) : 0.0;
                double ho = (c.nplaced<nb) ? wb_hobj2(c.loads,u,w_rem) : 0.0;
                keyed[i] = {w1p*(c.gt+hz) + w2p*ho + w3p*c.gz3 - mu*c.gcontact, i};
            }
            std::sort(keyed.begin(),keyed.end(),[](const std::pair<double,int>&a,const std::pair<double,int>&b){return a.first<b.first;});
            // FRONT-LOADED width (env OGC_WBFRONT=1): wide early, narrow to BMIN late.  A
            // speed/scalability knob (avg width ~B0/2) -- default OFF; fixed width gave better
            // quality at matched B0 in testing.
            int keep;
            if(std::getenv("OGC_WBFRONT")){
                const int BMIN=4; double prog=(double)(level+1)/(double)order.size();
                keep=std::min((int)keyed.size(), std::max(BMIN,(int)std::lround(BMIN+(double)(B-BMIN)*(1.0-prog))));
            } else keep=std::min((int)keyed.size(),B);
            std::vector<WBState> nb2; nb2.reserve(keep);
            for(int i=0;i<keep;i++) nb2.push_back(std::move(children[keyed[i].second]));
            beam.swap(nb2);
        }
        // FINAL pick = min EXACT objective (cum_hard + w2*floor(obj2_now)); contact/h are guides.
        double best_obj=1e18; std::vector<int> best_flat;
        for(auto& st : beam) if(st.nplaced==nb){
            double o2=0.0; for(int i=0;i<n_bays;i++) for(int j=i+1;j<n_bays;j++){ double d=std::fabs(u[i]*st.loads[i]-u[j]*st.loads[j]); if(d>o2)o2=d; }
            double ob=w1p*st.gt + w2p*std::floor(o2) + w3p*st.gz3;
            if(ob<best_obj){best_obj=ob;best_flat=st.flat;}
        }
        return {best_obj,best_flat};
    }
    // find the first (low-y) feasible position for block bid in bay at [en,ex); false if none.
    // SWEEP-PRUNED: build the per-new-layer forbidden bay-grid bitmaps F[k] once (same as
    // feasible_scan) so cells that miss every F[k] are DEFINITELY feasible and skip the
    // O(present) exact placement_feasible loop that dominates in a dense bay.  Identical
    // feasibility set as the raw scan, ~orders faster when the bay is congested.
    bool find_pos_in_bay(int bid,int bay,int en,int ex,int& oo,int& oix,int& oiy){
        const BlockShape& bs=shapes[bid]; double bw_j=bw[bay],bh_j=bh[bay];
        int norient=(int)bs.orients.size();
        int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
        int bayH=(int)std::ceil(bh_j), bayW=(int)std::ceil(bw_j); int wpr=(bayW+64)>>6;
        std::vector<std::vector<uint64_t>> F;
        bool use_sweep = RASTER && maxL>0 && bayH>0 && bayH<20000;
        if(use_sweep){
            F.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
            for(const Placed& te: timeline[bay]){
                if(!(en < te.ex && te.en < ex)) continue;
                bool newdesc=(te.en<=en&&en<te.ex)||(te.en<ex&&ex<=te.ex);
                bool tedesc =(en<=te.en&&te.en<ex)||(en<te.ex&&te.ex<=ex);
                if(!newdesc&&!tedesc) continue;
                const OrientData& eod=shapes[te.bid].orients[te.orient];
                int ne=(int)eod.layers.size();
                int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
                for(int j=0;j<ne;j++){ const LayerData& L=eod.layers[j]; if(L.npts<3)continue;
                    if(newdesc){ int hi=std::min(j,maxL-1); for(int k=0;k<=hi;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                    if(tedesc){ for(int k=std::max(j,0);k<maxL;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                }
            }
        }
        for(int oi=0;oi<norient;oi++){
            const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
            double w=od.x1-od.x0,h=od.y1-od.y0;
            if(w>bw_j+1e-9||h>bh_j+1e-9) continue;
            int lox=(int)std::ceil(-od.x0),hix=(int)std::floor(bw_j-od.x1);
            int loy=(int)std::ceil(-od.y0),hiy=(int)std::floor(bh_j-od.y1);
            for(int iy=loy;iy<=hiy;iy++) for(int ix=lox;ix<=hix;ix++){
                bool ok;
                if(use_sweep){
                    bool clear=true;
                    for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                        if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                    ok = clear ? true : placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                } else ok = placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                if(ok){ oo=oi;oix=ix;oiy=iy; return true; }
            }
        }
        return false;
    }
    // Z3 (bay-preference) REASSIGNMENT improvement: move blocks to a more-preferred bay at a
    // feasible entry (same entry, or entry-shifted) and 2-block bay swaps, accepting iff the
    // true objective delta w1*d_tardy + w3*d_pen < 0.  Iterates to the time budget (time-
    // scalable).  Returns the improved flat solution (7 ints per block).
    std::vector<int> z3_reassign(std::vector<int> flat, double w1, double w3, double time_budget_s){
        int nb=(int)shapes.size();
        std::vector<std::array<int,7>> recs(nb); std::vector<char> has(nb,0);
        for(size_t i=0;i+6<flat.size();i+=7){ int b=flat[i]; recs[b]={b,flat[i+1],flat[i+2],flat[i+3],flat[i+4],flat[i+5],flat[i+6]}; has[b]=1; }
        for(auto&t:timeline)t.clear();
        for(int b=0;b<nb;b++) if(has[b]){ auto&r=recs[b]; add(r[1],b,r[2],(double)r[3],(double)r[4],r[5],r[6]); }
        std::vector<double> mxp(nb);
        for(int b=0;b<nb;b++){ const auto&pr=shapes[b].prefs; double mx=pr.empty()?0:pr[0]; for(double v:pr)if(v>mx)mx=v; mxp[b]=mx; }
        auto prefv=[&](int b,int bay){ return (bay<(int)shapes[b].prefs.size())? shapes[b].prefs[bay] : 0.0; };
        auto t0=std::chrono::steady_clock::now();
        auto elapsed=[&](){ return std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); };
        // objective handled here = w1*Z1 + w3*Z3 (Z2 unchanged; pipeline gate guards it).
        auto evalobj=[&](){ double z1=0,z3=0;
            for(int b=0;b<nb;b++) if(has[b]){ auto&r=recs[b]; double dd=shapes[b].due;
                if(r[6]>dd) z1+=r[6]-dd; z3+=mxp[b]-prefv(b,r[1]); }
            return w1*z1+w3*z3; };
        auto rebuild=[&](const std::vector<std::array<int,7>>& R){
            for(auto&t:timeline)t.clear();
            for(int b=0;b<nb;b++) if(has[b]){ const auto&r=R[b]; add(r[1],b,r[2],(double)r[3],(double)r[4],r[5],r[6]); } };
        // one hill-climb to local optimum (single-block moves + 2-block bay swaps).
        auto hillclimb=[&](){ bool improved=true;
          while(improved && elapsed()<time_budget_s){
            improved=false;
            std::vector<int> ord; for(int b=0;b<nb;b++) if(has[b]) ord.push_back(b);
            std::sort(ord.begin(),ord.end(),[&](int a,int c){ return (mxp[a]-prefv(a,recs[a][1])) > (mxp[c]-prefv(c,recs[c][1])); });
            // (1) single-block moves to a more-preferred bay
            for(int b: ord){
                if(elapsed()>time_budget_s) break;
                auto& r=recs[b]; int cur_bay=r[1]; double cur_pen=mxp[b]-prefv(b,cur_bay);
                if(cur_pen<=0) continue;
                int en=r[5],ex=r[6]; double dd=shapes[b].due, cur_tardy=(ex>dd)?(ex-dd):0.0;
                remove(b);
                double bestd=-1e-9; int btb=-1,bo=0,bix=0,biy=0,be=0,bex=0;
                for(int tb=0;tb<n_bays;tb++){
                    if(prefv(b,tb)<=prefv(b,cur_bay)) continue;
                    double npen=mxp[b]-prefv(b,tb); int oo,oix,oiy;
                    if(find_pos_in_bay(b,tb,en,ex,oo,oix,oiy)){
                        double d=w3*(npen-cur_pen);
                        if(d<bestd){ bestd=d; btb=tb;bo=oo;bix=oix;biy=oiy;be=en;bex=ex; }
                    } else {
                        // entry-shift: earliest feasible later entry in tb (exit times)
                        std::vector<int> es; es.push_back((int)shapes[b].rt);
                        for(const Placed& te: timeline[tb]) if(te.ex>en) es.push_back(te.ex);
                        std::sort(es.begin(),es.end()); es.erase(std::unique(es.begin(),es.end()),es.end());
                        // scan MANY shifted windows (find_pos is sweep-pruned/fast): the earliest
                        // feasible entry minimizes added tardiness, but the preferred bay may be
                        // congested early -- a later feasible window can still beat cur if the Z3
                        // gain outweighs the extra Z1 (w1*dtardy + w3*dpen < 0).
                        int tried=0;
                        for(int e2: es){ if(++tried>64) break; int ex2=e2+(int)shapes[b].pt;
                            double nt=(ex2>dd)?(ex2-dd):0.0; double d=w1*(nt-cur_tardy)+w3*(npen-cur_pen);
                            if(d>=bestd) continue;   // even best-case placement here can't beat current best
                            if(find_pos_in_bay(b,tb,e2,ex2,oo,oix,oiy)){
                                bestd=d; btb=tb;bo=oo;bix=oix;biy=oiy;be=e2;bex=ex2; break; }
                        }
                    }
                }
                if(btb>=0){ add(btb,b,bo,(double)bix,(double)biy,be,bex); recs[b]={b,btb,bo,bix,biy,be,bex}; improved=true; }
                else { add(cur_bay,b,r[2],(double)r[3],(double)r[4],en,ex); }
            }
            // (2) 2-block bay swaps: a in Ba, c in Bb; both improve by swapping bays.
            for(int ia=0; ia<(int)ord.size(); ia++){
                if(elapsed()>time_budget_s) break;
                int a=ord[ia]; auto& ra=recs[a]; int Ba=ra[1]; double apen=mxp[a]-prefv(a,Ba);
                if(apen<=0) continue;
                for(int ic=ia+1; ic<(int)ord.size(); ic++){
                    int c=ord[ic]; auto& rc=recs[c]; int Bc=rc[1]; if(Bc==Ba) continue;
                    // a wants Bc AND c wants Ba (net pref gain)?
                    double dpen = (mxp[a]-prefv(a,Bc)) + (mxp[c]-prefv(c,Ba)) - apen - (mxp[c]-prefv(c,Bc));
                    if(w3*dpen >= -1e-9) continue;   // swap wouldn't help prefs
                    int ea=ra[5],exa=ra[6], ec=rc[5],exc=rc[6];
                    remove(a); remove(c);
                    int ao,aix,aiy,co,cix,ciy;
                    bool fa=find_pos_in_bay(a,Bc,ea,exa,ao,aix,aiy);
                    bool fc = fa && find_pos_in_bay(c,Ba,ec,exc,co,cix,ciy);
                    if(fa && fc){
                        add(Bc,a,ao,(double)aix,(double)aiy,ea,exa); add(Ba,c,co,(double)cix,(double)ciy,ec,exc);
                        ra={a,Bc,ao,aix,aiy,ea,exa}; rc={c,Ba,co,cix,ciy,ec,exc}; improved=true; break;
                    } else {
                        add(Ba,a,ra[2],(double)ra[3],(double)ra[4],ea,exa); add(Bc,c,rc[2],(double)rc[3],(double)rc[4],ec,exc);
                    }
                }
            }
          }
        };
        // RUIN-RECREATE (LNS): the hill-climb gets stuck when a penalized block wants bay P
        // but P is full at its window -- freeing P needs several well-placed blocks to move
        // out together, a lateral step no single move takes.  Ruin removes a batch overlapping
        // P's window, recreate re-inserts them best-preferred-first at their FIXED [en,ex]
        // (so Z1 is invariant -- only Z3 moves), letting the penalized block claim P.
        auto ruin_recreate=[&](uint64_t& rng)->bool{
            // pick target bay P weighted toward the most unrealized preference gain.
            std::vector<double> want(n_bays,0.0);
            for(int b=0;b<nb;b++) if(has[b]){ double cp=mxp[b]-prefv(b,recs[b][1]);
                if(cp>0){ // which bay would satisfy it? its argmax-pref bay
                    int bp=recs[b][1]; double bv=prefv(b,bp);
                    for(int j=0;j<n_bays;j++){ double v=prefv(b,j); if(v>bv){bv=v;bp=j;} }
                    want[bp]+=cp; } }
            double tot=0; for(double v:want) tot+=v; if(tot<=0) return false;
            rng=rng*6364136223846793005ULL+1442695040888963407ULL;
            double pick=((double)((rng>>33)&0x7FFFFFFF)/(double)0x7FFFFFFF)*tot; int P=0;
            for(int j=0;j<n_bays;j++){ if(pick<want[j]){P=j;break;} pick-=want[j]; }
            // choose a pivot penalized block g wanting P; its window seeds the ruin.
            std::vector<int> wanters;
            for(int b=0;b<nb;b++) if(has[b]){ int bp=recs[b][1]; double bv=prefv(b,bp);
                for(int j=0;j<n_bays;j++){ double v=prefv(b,j); if(v>bv){bv=v;bp=j;} }
                if(bp==P && (mxp[b]-prefv(b,recs[b][1]))>0) wanters.push_back(b); }
            if(wanters.empty()) return false;
            rng=rng*6364136223846793005ULL+1442695040888963407ULL;
            int g=wanters[(rng>>33)%wanters.size()]; int eg=recs[g][5],exg=recs[g][6];
            // ruin set S = g + blocks currently in P overlapping [eg,exg] + other wanters
            // overlapping, capped at K.  K varies 6..30 for intensify/diversify balance.
            rng=rng*6364136223846793005ULL+1442695040888963407ULL;
            int K=6+(int)((rng>>33)%25); std::vector<int> S; std::vector<char> inS(nb,0);
            S.push_back(g); inS[g]=1;
            for(int b=0;b<nb;b++) if(has[b]&&!inS[b]&&recs[b][1]==P){
                int e=recs[b][5],x=recs[b][6]; if(e<exg&&eg<x){ S.push_back(b); inS[b]=1; if((int)S.size()>=K)break; } }
            for(int b: wanters){ if((int)S.size()>=K) break; if(inS[b])continue;
                int e=recs[b][5],x=recs[b][6]; if(e<exg&&eg<x){ S.push_back(b); inS[b]=1; } }
            if((int)S.size()<2) return false;
            std::vector<std::array<int,7>> snap; for(int b:S) snap.push_back(recs[b]);
            for(int b:S) remove(b);
            // recreate: most-penalized first.  For each block pick the (bay,entry) minimizing
            // w1*tardy + w3*penalty -- fixed window in every bay, plus entry-SHIFTED windows in
            // the more-preferred bays (so a block can pay a little Z1 to reach a congested
            // preferred bay, the Z1<->Z3 trade the fixed-window pass can't make).  Original spot
            // is always among the candidates, so a block can always be placed back.
            std::sort(S.begin(),S.end(),[&](int a,int c){ return (mxp[a]-prefv(a,recs[a][1]))>(mxp[c]-prefv(c,recs[c][1])); });
            bool ok=true;
            for(int b:S){ int en0=recs[b][5],ex0=recs[b][6]; int obay=recs[b][1];
                double dd=shapes[b].due;
                double bestv=1e18; int pb=-1,po=0,pix=0,piy=0,pe=en0,pex=ex0;
                int oo,oix,oiy;
                for(int tb=0;tb<n_bays;tb++){
                    double pen=mxp[b]-prefv(b,tb);
                    // (a) fixed window
                    double t0v=(ex0>dd)?(ex0-dd):0.0; double v0=w1*t0v+w3*pen;
                    if(v0<bestv-1e-9 && find_pos_in_bay(b,tb,en0,ex0,oo,oix,oiy)){
                        bestv=v0; pb=tb;po=oo;pix=oix;piy=oiy;pe=en0;pex=ex0; }
                    // (b) entry-shift only into strictly-preferred bays (Z1-for-Z3 trade)
                    if(prefv(b,tb)>prefv(b,obay)){
                        std::vector<int> es; es.push_back((int)shapes[b].rt);
                        for(const Placed& te: timeline[tb]) if(te.ex>(int)shapes[b].rt) es.push_back(te.ex);
                        std::sort(es.begin(),es.end()); es.erase(std::unique(es.begin(),es.end()),es.end());
                        int tried=0;
                        for(int e2: es){ if(++tried>64) break; int ex2=e2+(int)shapes[b].pt;
                            double nt=(ex2>dd)?(ex2-dd):0.0; double v=w1*nt+w3*pen;
                            if(v>=bestv-1e-9) continue;
                            if(find_pos_in_bay(b,tb,e2,ex2,oo,oix,oiy)){
                                bestv=v; pb=tb;po=oo;pix=oix;piy=oiy;pe=e2;pex=ex2; break; }
                        }
                    }
                }
                if(pb<0){ ok=false; break; }
                add(pb,b,po,(double)pix,(double)piy,pe,pex); recs[b]={b,pb,po,pix,piy,pe,pex};
            }
            if(!ok){ // restore batch exactly: drop any partial placements, re-add originals
                for(auto&r:snap) remove(r[0]);   // remove() is a safe no-op if absent
                for(auto&r:snap){ int b=r[0]; add(r[1],b,r[2],(double)r[3],(double)r[4],r[5],r[6]); recs[b]=r; }
                return false;
            }
            return true;
        };
        hillclimb();
        std::vector<std::array<int,7>> best_recs=recs; double best_obj=evalobj();
        uint64_t rng=0x9E3779B97F4A7C15ULL; int nofuel=0;
        while(elapsed()<time_budget_s){
            bool did=ruin_recreate(rng);
            if(!did){ if(++nofuel>4*n_bays+8) break; continue; }  // nothing left to ruin
            nofuel=0;
            hillclimb();
            double o=evalobj();
            if(o<best_obj-1e-9){ best_obj=o; best_recs=recs; }
            else { recs=best_recs; rebuild(recs); }   // always perturb from the best-so-far
        }
        recs=best_recs;
        std::vector<int> out; for(int b=0;b<nb;b++) if(has[b]){ auto&r=recs[b]; for(int k=0;k<7;k++) out.push_back(r[k]); }
        return out;
    }
    // Returns projected TARDINESS (Z1) by default; if w3p>0 returns the projected OBJECTIVE
    // w1p*Z1 + w3p*Z3 of the newly-placed blocks (Z3 = sum of bay-preference penalties), and
    // prefw biases lb_best toward preferred bays so the rollout can trade Z1 against Z3.
    std::pair<double,std::vector<int>>
    greedy_rollout_core(std::vector<double> prio, int cur0, int step, bool want_full, int maxplace,
                        bool approx, double w1p=0.0, double w3p=0.0, double prefw=0.0){
        int nb=(int)shapes.size();
        std::vector<char> placed(nb,0);
        for(auto& bay:timeline) for(auto& p:bay) if(p.bid>=0&&p.bid<nb) placed[p.bid]=1;
        std::vector<int> pending;
        for(int b=0;b<nb;b++) if(!placed[b]) pending.push_back(b);
        double tard=0.0, z3=0.0; std::vector<int> out; int nplaced=0;
        int cur=cur0; long guard=0;
        while(!pending.empty()){
            if(maxplace>0 && nplaced>=maxplace) break;
            if(++guard>2000000) break;
            std::vector<int> ready;
            for(int b:pending) if((int)shapes[b].rt<=cur) ready.push_back(b);
            std::sort(ready.begin(),ready.end(),[&](int a,int c){return prio[a]<prio[c];});
            std::vector<char> placedset(nb,0); bool any=false;
            for(int b:ready){
                int obay,oori,oix,oiy;
                if(lb_best(b,cur,step,obay,oori,oix,oiy,approx,prefw)){
                    int ex=cur+(int)shapes[b].pt;
                    add(obay,b,oori,(double)oix,(double)oiy,cur,ex);
                    double dd=shapes[b].due; tard += (ex>dd)?(ex-dd):0.0;
                    if(w3p>0.0){ const std::vector<double>& pr=shapes[b].prefs;
                        if(obay<(int)pr.size()){ double mx=pr[0]; for(double v:pr) if(v>mx)mx=v; z3 += (mx-pr[obay]); } }
                    placedset[b]=1; any=true; nplaced++;
                    if(want_full){ out.push_back(b);out.push_back(obay);out.push_back(oori);
                                   out.push_back(oix);out.push_back(oiy);out.push_back(cur);out.push_back(ex);}
                }
            }
            if(any){
                std::vector<int> np; np.reserve(pending.size());
                for(int b:pending) if(!placedset[b]) np.push_back(b);
                pending.swap(np);
            }
            long nextt=(long)2e18;
            for(int b:pending){ long r=(long)shapes[b].rt; if(r>cur && r<nextt) nextt=r; }
            for(auto& bay:timeline) for(auto& p:bay){ if(p.ex>cur && p.ex<nextt) nextt=p.ex; }
            if(nextt>=(long)1e18){ if(!pending.empty()){ cur=cur+1; continue; } else break; }
            cur=(int)nextt;
        }
        double val = (w3p>0.0) ? (w1p*tard + w3p*z3) : tard;   // objective if Z3-aware, else Z1
        return {val, out};   // caller (wrapper) restores timeline
    }

    // Full-grid feasible-position scan replicating place_custom's inner (bay,orient,ix,iy)
    // loop EXACTLY (same ceil/floor grid, same bay->orient->ix->iy order, same
    // placement_feasible) in ONE C++ call.  Returns feasible (bay,orient,ix,iy) as an
    // Nx4 int array so the Python scorer consumes an identical candidate stream.
    py::array_t<int> feasible_scan(int bid, std::vector<int> bay_list, int en, int ex, int step){
        const BlockShape& bs=shapes[bid];
        int norient=(int)bs.orients.size();
        std::vector<int> out;
        for(int bay : bay_list){
            double bw_j=bw[bay], bh_j=bh[bay];
            // SWEEP prune: build per-new-layer forbidden bay-grid bitmaps once per bay
            // (conservative -> a position whose layers miss every F[k] is DEFINITELY
            // feasible, skipping the O(present) exact loop that dominates on feasible
            // cells in a dense bay).  Identical feasibility set as the exact scan.
            int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
            int bayH=(int)std::ceil(bh_j), bayW=(int)std::ceil(bw_j);
            int wpr=(bayW+64)>>6;
            std::vector<std::vector<uint64_t>> F;
            bool use_sweep = RASTER && maxL>0 && bayH>0 && bayH<20000;
            if(use_sweep){
                F.assign(maxL, std::vector<uint64_t>((size_t)bayH*wpr,0ULL));
                for(const Placed& te: timeline[bay]){
                    if(!(en < te.ex && te.en < ex)) continue;
                    bool newdesc=(te.en<=en&&en<te.ex)||(te.en<ex&&ex<=te.ex);
                    bool tedesc =(en<=te.en&&te.en<ex)||(en<te.ex&&te.ex<=ex);
                    if(!newdesc&&!tedesc) continue;
                    const OrientData& eod=shapes[te.bid].orients[te.orient];
                    int ne=(int)eod.layers.size();
                    int tox=(int)std::floor(te.ox+0.5), toy=(int)std::floor(te.oy+0.5);
                    for(int j=0;j<ne;j++){ const LayerData& L=eod.layers[j]; if(L.npts<3)continue;
                        if(newdesc){ int hi=std::min(j,maxL-1); for(int k=0;k<=hi;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                        if(tedesc){ for(int k=std::max(j,0);k<maxL;k++) or_layer_into_map(F[k],wpr,bayH,L,tox,toy); }
                    }
                }
            }
            for(int oi=0; oi<norient; oi++){
                const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
                double w=od.x1-od.x0, h=od.y1-od.y0;
                if(w>bw_j+1e-9 || h>bh_j+1e-9) continue;
                int lo_x=(int)std::ceil(-od.x0), hi_x=(int)std::floor(bw_j-od.x1);
                int lo_y=(int)std::ceil(-od.y0), hi_y=(int)std::floor(bh_j-od.y1);
                for(int ix=lo_x; ix<=hi_x; ix+=step)
                    for(int iy=lo_y; iy<=hi_y; iy+=step){
                        bool ok;
                        if(use_sweep){
                            bool clear=true;
                            for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                                if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                            ok = clear ? true : placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                        } else ok = placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                        if(ok){ out.push_back(bay); out.push_back(oi); out.push_back(ix); out.push_back(iy); }
                    }
            }
        }
        int nrows=(int)out.size()/4;
        py::array_t<int> arr({nrows,4});
        if(nrows>0) std::memcpy(arr.mutable_data(), out.data(), out.size()*sizeof(int));
        return arr;
    }

    // Batch feasibility for an explicit (xs,ys) position list of ONE (bay,orient).
    // Returns a bool mask in the same order -> lets place_custom keep its EXACT position
    // enumeration + tie-break order (byte-identical) while replacing N per-position pybind
    // round-trips with a single call.  Works for both the full-grid and windowed loops.
    py::array_t<bool> feasible_mask(int bay,int bid,int orient,
                                    py::array_t<int,py::array::c_style|py::array::forcecast> xs,
                                    py::array_t<int,py::array::c_style|py::array::forcecast> ys,
                                    int en,int ex){
        int n=(int)xs.shape(0);
        py::array_t<bool> out(n);
        const int* xp=xs.data(); const int* yp=ys.data(); bool* op=out.mutable_data();
        for(int i=0;i<n;i++) op[i]=placement_feasible(bay,bid,orient,(double)xp[i],(double)yp[i],en,ex);
        return out;
    }

    // WINDOWED SWEEP-pruned feasibility scan for ONE bay: replicates place_custom's
    // windowed cell enumeration (per orient: lo/hi bbox clamp + per-rect step-aligned
    // sub-range, matching the Python _pbi build) and returns every feasible (orient,ix,iy)
    // in ONE C++ call with the SWEEP forbidden-bitmap prune -- replacing the per-cell
    // placement_feasible pybind round-trips (the 250-block step=1 rescan bottleneck:
    // ~18.5M calls / ~19s).  rects_flat = [wlx,whx,wly,why]*R.  The Python side consumes
    // it as a membership set over its own (oi,ix,iy) enumeration, so order is irrelevant
    // and the feasibility set is identical.
    py::array_t<int> feasible_scan_win(int bid, int bay, int en, int ex, int step,
                                       std::vector<int> rects_flat){
        const BlockShape& bs=shapes[bid];
        int norient=(int)bs.orients.size();
        int R=(int)rects_flat.size()/4;
        std::vector<int> out;
        double bw_j=bw[bay], bh_j=bh[bay];
        int maxL=0; for(int oi=0;oi<norient;oi++) maxL=std::max(maxL,(int)bs.orients[oi].layers.size());
        int bayH=(int)std::ceil(bh_j), bayW=(int)std::ceil(bw_j);
        int wpr=(bayW+64)>>6;
        // Direct per-cell C++ checks (no SWEEP bitmap: measured net-neutral on the small
        // windowed rescans, and the build/count overhead is pure cost).  The pybind boundary
        // is crossed ONCE per (bay,orient) instead of once per cell.
        bool use_sweep=false;
        std::vector<std::vector<uint64_t>> F;
        for(int oi=0; oi<norient; oi++){
            const OrientData& od=bs.orients[oi]; int nl=(int)od.layers.size();
            double w=od.x1-od.x0, h=od.y1-od.y0;
            if(w>bw_j+1e-9 || h>bh_j+1e-9) continue;
            int lo_x=(int)std::ceil(-od.x0), hi_x=(int)std::floor(bw_j-od.x1);
            int lo_y=(int)std::ceil(-od.y0), hi_y=(int)std::floor(bh_j-od.y1);
            for(int r=0;r<R;r++){
                int wlx=rects_flat[4*r], whx=rects_flat[4*r+1], wly=rects_flat[4*r+2], why=rects_flat[4*r+3];
                // step-aligned sub-range, matching the Python _pbi clamp exactly (the
                // branch is only taken when wlx>lo_x, so integer div is on positives ->
                // C++ '/' == Python '//').
                int ax = (wlx<=lo_x)? lo_x : lo_x+((wlx-lo_x+step-1)/step)*step;
                int bx = (whx>hi_x)? hi_x : whx;
                int ay = (wly<=lo_y)? lo_y : lo_y+((wly-lo_y+step-1)/step)*step;
                int by = (why>hi_y)? hi_y : why;
                for(int ix=ax; ix<=bx; ix+=step){
                    for(int iy=ay; iy<=by; iy+=step){
                        bool ok;
                        if(use_sweep){
                            bool clear=true;
                            for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                                if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                            ok = clear ? true : placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                        } else ok = placement_feasible(bay,bid,oi,(double)ix,(double)iy,en,ex);
                        if(ok){ out.push_back(oi); out.push_back(ix); out.push_back(iy); }
                    }
                }
            }
        }
        int nrows=(int)out.size()/3;
        py::array_t<int> arr({nrows,3});
        if(nrows>0) std::memcpy(arr.mutable_data(), out.data(), out.size()*sizeof(int));
        return arr;
    }
};

int classify_pair(py::array_t<double,py::array::c_style|py::array::forcecast> A,
                  py::array_t<double,py::array::c_style|py::array::forcecast> B){
    int na=(int)A.shape(0), nb=(int)B.shape(0);
    return classify(A.data(),na,0,0,B.data(),nb,0,0);
}
double intersection_area(py::array_t<double,py::array::c_style|py::array::forcecast> A,
                         py::array_t<double,py::array::c_style|py::array::forcecast> B){
    int na=(int)A.shape(0), nb=(int)B.shape(0);
    return classify(A.data(),na,0,0,B.data(),nb,0,0)==1 ? 1.0 : 0.0;
}

PYBIND11_MODULE(ogc_fast,m){
    m.def("classify_pair",&classify_pair);
    m.def("intersection_area",&intersection_area);
    py::class_<Engine>(m,"Engine").def(py::init<>())
        .def("init",&Engine::init)
        .def("reserve_blocks",&Engine::reserve_blocks)
        .def("set_nfp_provider",&Engine::set_nfp_provider)
        .def("register_block",&Engine::register_block)
        .def("add",&Engine::add)
        .def("remove",&Engine::remove)
        .def("clear_all",&Engine::clear_all)
        .def("compute_bbox",&Engine::compute_bbox)
        .def("placement_feasible",&Engine::placement_feasible)
        .def("find_best_placement",&Engine::find_best_placement)
        .def("feasible_scan",&Engine::feasible_scan)
        .def("feasible_scan_win",&Engine::feasible_scan_win)
        .def("feasible_mask",&Engine::feasible_mask)
        .def("greedy_rollout",&Engine::greedy_rollout,
             py::arg("prio"),py::arg("cur0"),py::arg("step"),py::arg("want_full"),
             py::arg("maxplace"),py::arg("approx"),
             py::arg("w1p")=0.0,py::arg("w3p")=0.0,py::arg("prefw")=0.0)
        .def("greedy_rollout_from",&Engine::greedy_rollout_from,
             py::arg("state_flat"),py::arg("prio"),py::arg("cur0"),py::arg("step"),
             py::arg("want_full"),py::arg("maxplace"),py::arg("approx"),
             py::arg("w1p")=0.0,py::arg("w3p")=0.0,py::arg("prefw")=0.0)
        .def("best_cell_lb",&Engine::best_cell_lb)
        .def("best_cell_contact",&Engine::best_cell_contact,
             py::arg("bid"),py::arg("cur"),py::arg("step"),py::arg("pos_lam"),py::arg("prefw"),
             py::arg("mu"),py::arg("w1"),py::arg("w3"),py::arg("topk"),
             py::arg("fut_beta")=0.0,py::arg("mean_proc")=1.0,
             py::arg("w2")=0.0,py::arg("loads")=std::vector<double>{})
        .def("greedy_contact",&Engine::greedy_contact,
             py::arg("order"),py::arg("step"),py::arg("pos_lam"),py::arg("prefw"),
             py::arg("mu"),py::arg("w1"),py::arg("w3"))
        .def("greedy_contact_from",&Engine::greedy_contact_from,
             py::arg("state_flat"),py::arg("order"),py::arg("step"),py::arg("pos_lam"),
             py::arg("prefw"),py::arg("mu"),py::arg("w1"),py::arg("w3"),
             py::arg("fut_beta")=0.0,py::arg("mean_proc")=1.0)
        .def("hz1_est",&Engine::hz1_est,py::arg("flat"),py::arg("areas"))
        .def_readonly("cb_n_hard",&Engine::cb_n_hard)
        .def_readonly("cb_n_badrej",&Engine::cb_n_badrej)
        .def_readonly("cb_n_cell",&Engine::cb_n_cell)
        .def_readonly("cb_t_retry",&Engine::cb_t_retry)
        .def_readonly("cb_n_retry",&Engine::cb_n_retry)
        .def_readonly("cb_t_roll",&Engine::cb_t_roll)
        .def_readonly("cb_n_arskip",&Engine::cb_n_arskip)
        .def_readonly("cb_n_arbad",&Engine::cb_n_arbad)
        .def_readonly("cb_n_bitmap",&Engine::cb_n_bitmap)
        .def_readonly("cb_n_exact",&Engine::cb_n_exact)
        .def_readonly("cb_t_exact",&Engine::cb_t_exact)
        .def_readonly("cb_t_rebuild",&Engine::cb_t_rebuild)
        .def_readonly("cb_t_scan",&Engine::cb_t_scan)
        .def("contact_beam",&Engine::contact_beam,
             py::arg("order"),py::arg("areas"),py::arg("workloads"),py::arg("B"),py::arg("K"),
             py::arg("step"),py::arg("pos_lam"),py::arg("prefw"),py::arg("mu"),
             py::arg("w1"),py::arg("w2"),py::arg("w3"),py::arg("fut_beta"),
             py::arg("mean_proc"),py::arg("time_budget_s"),
             py::arg("anchor")=std::vector<int>(),py::arg("anchor_w")=std::vector<double>(),
             py::arg("area_scale")=1.0)
        .def("set_bcl_prefw",&Engine::set_bcl_prefw)
        .def("wide_beam",&Engine::wide_beam,
             py::arg("order"),py::arg("areas"),py::arg("workloads"),py::arg("B"),py::arg("K"),
             py::arg("step"),py::arg("w1p"),py::arg("w2p"),py::arg("w3p"),py::arg("mu"),
             py::arg("time_budget_s"),py::arg("nent")=1,py::arg("cps")=6)
        .def("z3_reassign",&Engine::z3_reassign,
             py::arg("flat"),py::arg("w1"),py::arg("w3"),py::arg("time_budget_s"));
}
