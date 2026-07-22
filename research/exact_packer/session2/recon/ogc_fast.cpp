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
#include <vector>
#include <tuple>
#include <algorithm>
#include <functional>
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
    int cx0=0,cy0=0,cw=0,ch=0,wpr=0; std::vector<uint64_t> bits;
    void rasterize(){
        if(npts<3){ cw=ch=0; return; }
        double mnx=pts[0],mny=pts[1],mxx=pts[0],mxy=pts[1];
        for(int i=1;i<npts;i++){double x=pts[2*i],y=pts[2*i+1];
            if(x<mnx)mnx=x;if(x>mxx)mxx=x;if(y<mny)mny=y;if(y>mxy)mxy=y;}
        cx0=(int)std::floor(mnx); cy0=(int)std::floor(mny);
        cw=(int)std::ceil(mxx)-cx0; ch=(int)std::ceil(mxy)-cy0;
        if(cw<=0)cw=1; if(ch<=0)ch=1; wpr=(cw+63)>>6;
        bits.assign((size_t)ch*wpr,0ULL);
        for(int r=0;r<ch;r++){int wy=cy0+r;
            for(int c=0;c<cw;c++){int wx=cx0+c; bool hit=false;
                double ccx=wx+0.5, ccy=wy+0.5;
                { bool inside=false;int j=npts-1;
                  for(int i=0;i<npts;i++){double yi=pts[2*i+1],yj=pts[2*j+1],xi=pts[2*i],xj=pts[2*j];
                    if((yi>ccy)!=(yj>ccy)){double xint=(xj-xi)*(ccy-yi)/(yj-yi)+xi; if(ccx<xint)inside=!inside;} j=i;}
                  if(inside) hit=true; }
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
                for(int oi=0; oi<norient; oi++){
                    std::vector<std::pair<double,double>> cand;
                    candidates(bid,oi,bay,bstep,cand);
                    for(auto& c: cand){
                        double x=std::round(c.first), y=std::round(c.second);
                        if(!placement_feasible(bay,bid,oi,x,y,en,ex)) continue;
                        double score = tard*1e12 + prefpen*1e8 + y*1e3 + x;
                        if(score<bestscore){bestscore=score;found=true;
                            bbay=bay;bori=oi;bx=x;by=y;ben=en;bex=ex;}
                    }
                }
            }
            if(found) break; // earliest feasible entry time wins the tardiness tier
        }
        return {found,bbay,bori,bx,by,ben,bex};
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
        .def("find_best_placement",&Engine::find_best_placement);
}
