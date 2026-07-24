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
    return (((d1>EPS&&d2<-EPS)||(d1<-EPS&&d2>EPS))&&((d3>EPS&&d4<-EPS)||(d3<-EPS&&d4>EPS)));
}
static bool pip(double px,double py,const double* poly,int n,double ox,double oy){
    for(int i=0;i<n;i++){
        double ax=poly[2*i]+ox,ay=poly[2*i+1]+oy; int ni=(i+1)%n;
        double bx=poly[2*ni]+ox,by=poly[2*ni+1]+oy;
        double o=orient_(ax,ay,bx,by,px,py);
        if(std::fabs(o)<=EPS&&on_seg(ax,ay,bx,by,px,py)) return false;
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
        if(nx0<-1e-6||ny0<-1e-6||nx1>bw[bay]+1e-6||ny1>bh[bay]+1e-6) return false;
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
                        if(od.x0+x<-1e-6||od.y0+y<-1e-6||od.x1+x>bw[bay]+1e-6||od.y1+y>bh[bay]+1e-6) continue;
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
        if(nx0<-1e-6||ny0<-1e-6||nx1>bw[bay]+1e-6||ny1>bh[bay]+1e-6) return false;
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
            for(int ix=lo_x; ix<=hi_x; ix+=step) for(int iy=lo_y; iy<=hi_y; iy+=step){
                bool ok;
                if(use_sweep){ bool clear=true;
                    for(int k=0;k<nl&&clear;k++){ const LayerData& L=od.layers[k]; if(L.npts<3)continue;
                        if(layer_hits_map(F[k],wpr,bayH,L,ix,iy)) clear=false; }
                    ok = clear ? true : placement_feasible_tl(btl,bay,bid,oi,(double)ix,(double)iy,en,ex);
                } else ok = placement_feasible_tl(btl,bay,bid,oi,(double)ix,(double)iy,en,ex);
                if(ok){ int ct = _perlayer ? contact_at_layered(footprintL(bid,oi),ix,iy,occL,bayW,bayH)
                                           : contact_at(fp,ix,iy,occ,bayW,bayH);
                        all.push_back({ct,oi,ix,iy}); }
            }
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
        .def("set_bcl_prefw",&Engine::set_bcl_prefw)
        .def("wide_beam",&Engine::wide_beam,
             py::arg("order"),py::arg("areas"),py::arg("workloads"),py::arg("B"),py::arg("K"),
             py::arg("step"),py::arg("w1p"),py::arg("w2p"),py::arg("w3p"),py::arg("mu"),
             py::arg("time_budget_s"),py::arg("nent")=1,py::arg("cps")=6);
}
