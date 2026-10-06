/* sky.c - spectral sky radiance for a spherical Earth, sun above or below the horizon.

   Three species, each with a tabulated density profile and per-wavelength
   extinction and scattering coefficients per unit density:
     0  air       Rayleigh phase function
     1  aerosol   Henyey-Greenstein phase function
     2  ozone     absorber only
   Single scattering is integrated deterministically along each view ray.
   Higher orders come from a backward Monte Carlo path tracer with
   next-event estimation towards the sun and spectral (weighted) delta tracking,
   so one path carries every wavelength.

   Frame: Earth's centre at the origin, observer at (0, 0, R + h_obs), z up at
   the observer. The sun is a point at infinity in direction `sun`.
   Not modelled: refraction, polarisation, the sun's finite disc.

   Build: cc -O3 -shared -fPIC -o libsky.dylib sky.c
*/
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <Accelerate/Accelerate.h>

#define NS 3
#define NLMAX 64

/* ---- atmosphere state (set once from Python) ---- */
static double R, RTOP, HOBS;
static int NH;            /* density table length */
static double DH;         /* density table spacing, m */
static double *DENS;      /* [NS][NH] */
static int NL;
static double SEXT[NS][NLMAX], SSCA[NS][NLMAX], ESUN[NLMAX];
static double G_HG, ALBEDO;
static double MAJ;        /* majorant of extinction over h and lambda */

/* ---- sun column look-up table ---- */
static int LH, LX;        /* altitude rows, elevation columns */
static double LDH;        /* altitude spacing */
static float *LUT;        /* [LH][LX][NS] log(column + 1) */

static inline double dens(int s, double h) {
    if (h < 0) h = 0;
    double u = h / DH;
    int i = (int)u;
    if (i >= NH - 1) return 0.0;
    double f = u - i;
    const double *d = DENS + (size_t)s * NH;
    return d[i] + f * (d[i + 1] - d[i]);
}

/* Column density of each species along a ray from radius r with direction
   cosine mu (to the local vertical), out to the top of the atmosphere.
   Returns 0 if the ray hits the ground (columns then irrelevant). */
static int column_exact(double r, double mu, double col[NS]) {
    for (int s = 0; s < NS; s++) col[s] = 0;
    double rt2 = r * r * (1 - mu * mu);
    if (mu < 0 && rt2 < R * R) return 0;
    double s0 = r * mu;                       /* signed distance from tangent point */
    double s1 = sqrt(RTOP * RTOP - rt2);
    double s = s0;
    while (s < s1) {
        double sa = fabs(s) + 1.0;
        double ds = 12.5 * sqrt(rt2 + s * s) / sa;   /* keep dh <= ~12.5 m */
        if (ds > 500.0) ds = 500.0;
        if (ds < 5.0) ds = 5.0;
        if (s + ds > s1) ds = s1 - s;
        double sm = s + 0.5 * ds;
        double h = sqrt(rt2 + sm * sm) - R;
        for (int k = 0; k < NS; k++) col[k] += dens(k, h) * ds;
        s += ds;
    }
    return 1;
}

static inline double horizon_elev(double r) {   /* elevation of the geometric horizon, radians (<= 0) */
    if (r <= R) return 0.0;
    return -acos(R / r);
}

int sky_init(double R_, double RTOP_, double HOBS_, int NH_, double DH_, const double *dens_,
             int NL_, const double *sext, const double *ssca, const double *esun,
             double g, double albedo) {
    R = R_; RTOP = RTOP_; HOBS = HOBS_; NH = NH_; DH = DH_; NL = NL_;
    if (NL > NLMAX) return -1;
    free(DENS);
    DENS = malloc(sizeof(double) * NS * NH);
    memcpy(DENS, dens_, sizeof(double) * NS * NH);
    for (int s = 0; s < NS; s++)
        for (int l = 0; l < NL; l++) {
            SEXT[s][l] = sext[s * NL + l];
            SSCA[s][l] = ssca[s * NL + l];
        }
    for (int l = 0; l < NL; l++) ESUN[l] = esun[l];
    G_HG = g; ALBEDO = albedo;
    MAJ = 0;
    for (int i = 0; i < NH; i++)
        for (int l = 0; l < NL; l++) {
            double m = 0;
            for (int s = 0; s < NS; s++) m += DENS[(size_t)s * NH + i] * SEXT[s][l];
            if (m > MAJ) MAJ = m;
        }
    MAJ *= 1.0001;
    return 0;
}

/* LUT parametrisation: altitude h = H u^2 with u uniform (dense near the ground,
   where grazing columns change fastest); x in [0,1] maps to elevation
   e = e_hor(r) + (pi/2 - e_hor) x^2, dense near grazing. */
int lut_alloc(int lh, int lx, double ldh) {
    LH = lh; LX = lx; LDH = ldh;
    free(LUT);
    LUT = malloc(sizeof(float) * (size_t)LH * LX * NS);
    return LUT ? 0 : -1;
}

void lut_fill_rows(int i0, int i1) {   /* callable from several threads on disjoint rows */
    for (int i = i0; i < i1; i++) {
        double uu = (double)i / (LH - 1);
        double r = R + (RTOP - R) * uu * uu;
        double eh = horizon_elev(r);
        for (int j = 0; j < LX; j++) {
            double x = (double)j / (LX - 1);
            double e = eh + (M_PI / 2 - eh) * x * x;
            double col[NS];
            double mu = sin(e);
            if (j == 0) mu = sin(eh) + 1e-12;   /* exactly grazing: nudge above */
            column_exact(r, mu, col);
            for (int s = 0; s < NS; s++)
                LUT[((size_t)i * LX + j) * NS + s] = (float)log(col[s] + 1.0);
        }
    }
}

/* Sun columns from a point at radius r whose local vertical makes cosine mu
   with the sun. Returns 0 if the sun is below the point's horizon. */
static inline int sun_columns(double r, double mu, double col[NS]) {
    double h = r - R;
    if (h < 0) h = 0, r = R;
    if (h >= RTOP - R) { for (int s = 0; s < NS; s++) col[s] = 0; return 1; }
    double eh = horizon_elev(r);
    if (mu > 1) mu = 1;
    double e = asin(mu);
    if (e < eh) return 0;
    double x = sqrt((e - eh) / (M_PI / 2 - eh));
    double u = sqrt(h / (RTOP - R)) * (LH - 1), v = x * (LX - 1);
    int i = (int)u, j = (int)v;
    if (i >= LH - 1) i = LH - 2;
    if (j >= LX - 1) j = LX - 2;
    double fu = u - i, fv = v - j;
    for (int s = 0; s < NS; s++) {
        double a = LUT[((size_t)i * LX + j) * NS + s];
        double b = LUT[((size_t)i * LX + j + 1) * NS + s];
        double c = LUT[((size_t)(i + 1) * LX + j) * NS + s];
        double d = LUT[((size_t)(i + 1) * LX + j + 1) * NS + s];
        double lv = (1 - fu) * ((1 - fv) * a + fv * b) + fu * ((1 - fv) * c + fv * d);
        col[s] = exp(lv) - 1.0;
    }
    return 1;
}

/* test hook: compare LUT against exact integration */
int sun_columns_test(double h, double elev, double *lut_col, double *exact_col) {
    double r = R + h, mu = sin(elev);
    int a = sun_columns(r, mu, lut_col);
    int b = column_exact(r, mu, exact_col);
    return a * 2 + b;
}

static inline double phase_rayleigh(double c) { return 3.0 / (16.0 * M_PI) * (1 + c * c); }
static inline double phase_hg(double c) {
    double g = G_HG, d = 1 + g * g - 2 * g * c;
    return (1 - g * g) / (4 * M_PI * d * sqrt(d));
}

static inline void norm3(double *v) {
    double n = sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    v[0] /= n; v[1] /= n; v[2] /= n;
}

/* ---- single scattering along view rays ---- */

/* For each of n view directions (dirs[3n], unit, observer frame) write NL radiances
   to out[n*NL], W m^-2 sr^-1 nm^-1. If heights != NULL it also accumulates, for
   the luminance-weighted contribution, a histogram over scattering altitude
   (nbins of width hbin metres) into heights[n*nbins], weighted by the
   spectral weights wl[NL] (e.g. CIE ybar). */
void single_scatter(int n, const double *dirs, const double *sun, double max_dh,
                    double *out, int nbins, double hbin, const double *wl, double *heights) {
    double o[3] = {0, 0, R + HOBS};
    for (int k = 0; k < n; k++) {
        const double *d = dirs + 3 * k;
        double *L = out + (size_t)k * NL;
        for (int l = 0; l < NL; l++) L[l] = 0;
        double r0 = R + HOBS, mu0 = d[2];
        double rt2 = r0 * r0 * (1 - mu0 * mu0);
        double s0 = r0 * mu0, s1 = sqrt(RTOP * RTOP - rt2);
        if (mu0 < 0 && rt2 < R * R) continue;   /* looks at the ground */
        double cosang = d[0] * sun[0] + d[1] * sun[1] + d[2] * sun[2];
        double pR = phase_rayleigh(cosang), pM = phase_hg(cosang);
        double cv[NS] = {0, 0, 0};
        double s = s0;
        while (s < s1) {
            double sa = fabs(s) + 1.0;
            double ds = max_dh * sqrt(rt2 + s * s) / sa;
            if (ds > 1000.0) ds = 1000.0;
            if (ds < 2.0) ds = 2.0;
            if (s + ds > s1) ds = s1 - s;
            double sm = s + 0.5 * ds, t = sm - s0;
            double p[3] = {o[0] + t * d[0], o[1] + t * d[1], o[2] + t * d[2]};
            double r = sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]);
            double h = r - R;
            double nd[NS];
            for (int q = 0; q < NS; q++) nd[q] = dens(q, h);
            double cmid[NS];
            for (int q = 0; q < NS; q++) cmid[q] = cv[q] + nd[q] * 0.5 * ds;
            double mus = (p[0] * sun[0] + p[1] * sun[1] + p[2] * sun[2]) / r;
            double cs[NS];
            if (sun_columns(r, mus, cs)) {
                double acc = 0;
                for (int l = 0; l < NL; l++) {
                    double tau = 0;
                    for (int q = 0; q < NS; q++) tau += SEXT[q][l] * (cmid[q] + cs[q]);
                    double sc = nd[0] * SSCA[0][l] * pR + nd[1] * SSCA[1][l] * pM;
                    double v = sc * exp(-tau) * ESUN[l] * ds;
                    L[l] += v;
                    if (heights) acc += v * wl[l];
                }
                if (heights) {
                    int b = (int)(h / hbin);
                    if (b >= 0 && b < nbins) heights[(size_t)k * nbins + b] += acc;
                }
            }
            for (int q = 0; q < NS; q++) cv[q] += nd[q] * ds;
            s += ds;
        }
    }
}

/* ---- Monte Carlo multiple scattering ---- */

typedef struct { uint64_t s[4]; } rng_t;
static inline uint64_t rotl(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }
static inline uint64_t next_u64(rng_t *r) {
    uint64_t *s = r->s, res = rotl(s[1] * 5, 7) * 9, t = s[1] << 17;
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3]; s[2] ^= t; s[3] = rotl(s[3], 45);
    return res;
}
static inline double rnd(rng_t *r) { return (next_u64(r) >> 11) * 0x1.0p-53; }
static void seed_rng(rng_t *r, uint64_t seed) {
    for (int i = 0; i < 4; i++) {
        seed += 0x9e3779b97f4a7c15ULL;
        uint64_t z = seed;
        z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
        z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
        r->s[i] = z ^ (z >> 31);
    }
}

/* Orthonormal basis around w; returns direction with cosine c, azimuth phi. */
static void dir_from(const double *w, double c, double phi, double *out) {
    double sn = sqrt(fmax(0.0, 1 - c * c));
    double a[3] = {1, 0, 0};
    if (fabs(w[0]) > 0.9) { a[0] = 0; a[1] = 1; }
    double u[3] = {w[1] * a[2] - w[2] * a[1], w[2] * a[0] - w[0] * a[2], w[0] * a[1] - w[1] * a[0]};
    norm3(u);
    double v[3] = {w[1] * u[2] - w[2] * u[1], w[2] * u[0] - w[0] * u[2], w[0] * u[1] - w[1] * u[0]};
    for (int i = 0; i < 3; i++) out[i] = sn * (cos(phi) * u[i] + sin(phi) * v[i]) + c * w[i];
}

static double sample_rayleigh_cos(rng_t *r) {   /* invert CDF of (1+c^2) */
    double u = 4 * rnd(r) - 2;                 /* c^3 + 3c = 4u' ... solved by Cardano */
    double q = sqrt(u * u + 1);
    return cbrt(u + q) + cbrt(u - q);
}
static double sample_hg_cos(rng_t *r) {
    double g = G_HG, x = rnd(r);
    if (fabs(g) < 1e-6) return 2 * x - 1;
    double t = (1 - g * g) / (1 - g + 2 * g * x);
    return (1 + g * g - t * t) / (2 * g);
}

/* distance to sphere of radius rad from p along d: smallest positive root, or -1 */
static inline double hit_sphere(const double *p, const double *d, double rad) {
    double b = p[0] * d[0] + p[1] * d[1] + p[2] * d[2];
    double c = p[0] * p[0] + p[1] * p[1] + p[2] * p[2] - rad * rad;
    double disc = b * b - c;
    if (disc < 0) return -1;
    double sq = sqrt(disc);
    double t0 = -b - sq, t1 = -b + sq;
    if (t0 > 1e-6) return t0;
    if (t1 > 1e-6) return t1;
    return -1;
}

/* Analog-style estimator kept as an independent check on multi_scatter():
   weighted delta tracking, next-event estimation only at collision vertices.
   Unbiased but very noisy in deep twilight, where little of the air is sunlit.
   out[n*NL] receives radiance from scattering orders min_order..max_order. */
void multi_scatter_dt(int n, const double *dirs, const double *sun, int npath, int min_order,
                   int max_order, uint64_t seed, double *out) {
    rng_t rg;
    seed_rng(&rg, seed);
    for (int k = 0; k < n; k++) {
        double *L = out + (size_t)k * NL;
        for (int l = 0; l < NL; l++) L[l] = 0;
        for (int ip = 0; ip < npath; ip++) {
            double p[3] = {0, 0, R + HOBS};
            double d[3] = {dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]};
            double w[NLMAX];
            for (int l = 0; l < NL; l++) w[l] = 1.0;
            int order = 0;
            for (int bounce = 0; bounce < 200; bounce++) {
                double tg = hit_sphere(p, d, R);
                double tt = hit_sphere(p, d, RTOP);
                double tend = tt;
                int ground = 0;
                if (tg > 0 && (tt < 0 || tg < tt)) { tend = tg; ground = 1; }
                if (tend < 0) break;
                /* weighted delta tracking */
                double t = 0;
                int scattered = 0;
                double x[3], nd[NS];
                for (;;) {
                    t += -log(1 - rnd(&rg)) / MAJ;
                    if (t >= tend) break;
                    for (int i = 0; i < 3; i++) x[i] = p[i] + t * d[i];
                    double h = sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]) - R;
                    for (int q = 0; q < NS; q++) nd[q] = dens(q, h);
                    double as = 0, an = 0;
                    double ms[NLMAX], mn[NLMAX];
                    for (int l = 0; l < NL; l++) {
                        double mt = 0;
                        for (int q = 0; q < NS; q++) mt += nd[q] * SEXT[q][l];
                        ms[l] = nd[0] * SSCA[0][l] + nd[1] * SSCA[1][l];
                        mn[l] = MAJ - mt;
                        as += w[l] * ms[l];
                        an += w[l] * mn[l];
                    }
                    double ps = as / (as + an);
                    if (rnd(&rg) < ps) {
                        for (int l = 0; l < NL; l++) w[l] *= ms[l] / (MAJ * ps);
                        scattered = 1;
                        break;
                    } else {
                        for (int l = 0; l < NL; l++) w[l] *= mn[l] / (MAJ * (1 - ps));
                    }
                }
                if (!scattered && !ground) break;   /* escaped to space */
                order++;
                if (order > max_order) break;
                if (!scattered) {
                    /* Lambertian ground */
                    for (int i = 0; i < 3; i++) x[i] = p[i] + tend * d[i];
                    double nrm[3] = {x[0], x[1], x[2]};
                    norm3(nrm);
                    double mus = nrm[0] * sun[0] + nrm[1] * sun[1] + nrm[2] * sun[2];
                    double cs[NS];
                    if (order >= min_order && mus > 0 && sun_columns(R, mus, cs)) {
                        for (int l = 0; l < NL; l++) {
                            double tau = 0;
                            for (int q = 0; q < NS; q++) tau += SEXT[q][l] * cs[q];
                            L[l] += w[l] * ALBEDO / M_PI * mus * exp(-tau) * ESUN[l];
                        }
                    }
                    double c = sqrt(rnd(&rg));
                    double nd2[3];
                    dir_from(nrm, c, 2 * M_PI * rnd(&rg), nd2);
                    for (int l = 0; l < NL; l++) w[l] *= ALBEDO;
                    for (int i = 0; i < 3; i++) { p[i] = x[i] + nrm[i] * 0.01; d[i] = nd2[i]; }
                } else {
                    double r = sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]);
                    double mus = (x[0] * sun[0] + x[1] * sun[1] + x[2] * sun[2]) / r;
                    double cang = d[0] * sun[0] + d[1] * sun[1] + d[2] * sun[2];
                    double pR = phase_rayleigh(cang), pM = phase_hg(cang);
                    double cs[NS];
                    double sR[NLMAX], sM[NLMAX];
                    for (int l = 0; l < NL; l++) { sR[l] = nd[0] * SSCA[0][l]; sM[l] = nd[1] * SSCA[1][l]; }
                    if (order >= min_order && sun_columns(r, mus, cs)) {
                        for (int l = 0; l < NL; l++) {
                            double tau = 0;
                            for (int q = 0; q < NS; q++) tau += SEXT[q][l] * cs[q];
                            double pm = (sR[l] * pR + sM[l] * pM) / (sR[l] + sM[l]);
                            L[l] += w[l] * pm * exp(-tau) * ESUN[l];
                        }
                    }
                    /* choose a lobe, then one-sample MIS weight per wavelength */
                    double aR = 0, aM = 0;
                    for (int l = 0; l < NL; l++) {
                        double f = w[l] / (sR[l] + sM[l]);
                        aR += f * sR[l]; aM += f * sM[l];
                    }
                    double qR = aR / (aR + aM);
                    double c = rnd(&rg) < qR ? sample_rayleigh_cos(&rg) : sample_hg_cos(&rg);
                    double nd2[3];
                    dir_from(d, c, 2 * M_PI * rnd(&rg), nd2);
                    double pr = phase_rayleigh(c), pm2 = phase_hg(c);
                    double pdf = qR * pr + (1 - qR) * pm2;
                    for (int l = 0; l < NL; l++)
                        w[l] *= (sR[l] * pr + sM[l] * pm2) / (sR[l] + sM[l]) / pdf;
                    for (int i = 0; i < 3; i++) { p[i] = x[i]; d[i] = nd2[i]; }
                }
                /* Russian roulette */
                if (order >= 3) {
                    double m = 0;
                    for (int l = 0; l < NL; l++) m += w[l];
                    m /= NL;
                    double surv = m < 1 ? m : 1;
                    if (surv < 0.05) surv = 0.05;
                    if (rnd(&rg) > surv) break;
                    for (int l = 0; l < NL; l++) w[l] /= surv;
                }
            }
        }
        for (int l = 0; l < NL; l++) L[l] /= npath;
    }
}

/* ---- Monte Carlo with deterministic in-scattering on every segment ----

   Each path segment is ray-marched once. Sunlight singly scattered anywhere
   along the segment is integrated deterministically (so a segment that passes
   through the thin sunlit shell always contributes); the next vertex is then
   drawn from the marched optical depth (forced collision unless the segment
   ends on the ground) with spectral MIS, so per-wavelength weights stay bounded. Light that has scattered
   k times in total, counting ground reflections, is "order k". */

typedef struct { double t, ds, nd[NS], c0[NS], tau0; } step_t;

/* guide lobe: von Mises-Fisher, concentration GUIDE_K, aimed GUIDE_ELEV above the
   local horizon towards the sun's azimuth, chosen with probability GUIDE_P */
static double GUIDE_P = 0.5, GUIDE_K = 6.0, GUIDE_C = 0.98480775, GUIDE_S = 0.17364818;
void set_guide(double p, double k, double elev_deg) {
    GUIDE_P = p; GUIDE_K = k; GUIDE_C = cos(elev_deg * M_PI / 180); GUIDE_S = sin(elev_deg * M_PI / 180);
}

static int march(const double *p, const double *d, double max_dh, step_t *st, int cap,
                 double *len, int *ground, double *tauref, const double *sref) {
    double r0 = sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]);
    double mu0 = (p[0] * d[0] + p[1] * d[1] + p[2] * d[2]) / r0;
    double rt2 = r0 * r0 * (1 - mu0 * mu0);
    double s0 = r0 * mu0, s1;
    *ground = 0;
    if (mu0 < 0 && rt2 < R * R) { s1 = -sqrt(R * R - rt2); *ground = 1; }   /* hits ground */
    else s1 = sqrt(RTOP * RTOP - rt2);
    if (r0 > RTOP) r0 = RTOP;
    double s = s0, c[NS] = {0, 0, 0}, tau = 0;
    int k = 0;
    while (s < s1 && k < cap) {
        double sa = fabs(s) + 1.0;
        double ds = max_dh * sqrt(rt2 + s * s) / sa;
        if (ds > 4000.0) ds = 4000.0;
        if (ds < 2.0) ds = 2.0;
        if (s + ds > s1) ds = s1 - s;
        double sm = s + 0.5 * ds;
        double h = sqrt(rt2 + sm * sm) - R;
        step_t *q = st + k++;
        q->t = s - s0; q->ds = ds; q->tau0 = tau;
        double b = 0;
        for (int i = 0; i < NS; i++) {
            q->nd[i] = dens(i, h);
            q->c0[i] = c[i];
            c[i] += q->nd[i] * ds;
            b += q->nd[i] * sref[i];
        }
        tau += b * ds;
        s += ds;
    }
    *len = s1 - s0;
    *tauref = tau;
    return k;
}

void multi_scatter(int n, const double *dirs, const double *sun, int npath, int min_order,
                   int max_order, uint64_t seed, double max_dh, double *out) {
    rng_t rg;
    seed_rng(&rg, seed);
    int cap = 1 << 15;
    step_t *st = malloc(sizeof(step_t) * cap);
    double sref[NS];
    for (int i = 0; i < NS; i++) {
        sref[i] = 0;
        for (int l = 0; l < NL; l++) sref[i] += SEXT[i][l];
        sref[i] /= NL;
    }
    for (int k = 0; k < n; k++) {
        double *L = out + (size_t)k * NL;
        for (int l = 0; l < NL; l++) L[l] = 0;
        for (int ip = 0; ip < npath; ip++) {
            double p[3] = {0, 0, R + HOBS};
            double d[3] = {dirs[3 * k], dirs[3 * k + 1], dirs[3 * k + 2]};
            double w[NLMAX];
            for (int l = 0; l < NL; l++) w[l] = 1.0;
            for (int seg = 1; seg <= max_order; seg++) {
                double len, tauL;
                int ground;
                int ns = march(p, d, max_dh, st, cap, &len, &ground, &tauL, sref);
                double cang = d[0] * sun[0] + d[1] * sun[1] + d[2] * sun[2];
                double pR = phase_rayleigh(cang), pM = phase_hg(cang);
                /* deterministic in-scattering of sunlight along this segment: order seg */
                if (seg >= min_order) {
                    for (int j = 0; j < ns; j++) {
                        step_t *q = st + j;
                        double tm = q->t + 0.5 * q->ds;
                        double x[3] = {p[0] + tm * d[0], p[1] + tm * d[1], p[2] + tm * d[2]};
                        double r = sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]);
                        double mus = (x[0] * sun[0] + x[1] * sun[1] + x[2] * sun[2]) / r;
                        double cs[NS];
                        if (!sun_columns(r, mus, cs)) continue;
                        double cm[NS], et[NLMAX];
                        for (int i = 0; i < NS; i++) cm[i] = q->c0[i] + 0.5 * q->nd[i] * q->ds + cs[i];
                        for (int l = 0; l < NL; l++) {
                            double tau = 0;
                            for (int i = 0; i < NS; i++) tau += SEXT[i][l] * cm[i];
                            et[l] = -tau;
                        }
                        vvexp(et, et, &NL);
                        double aR = q->nd[0] * pR * q->ds, aM = q->nd[1] * pM * q->ds;
                        for (int l = 0; l < NL; l++)
                            L[l] += w[l] * (aR * SSCA[0][l] + aM * SSCA[1][l]) * et[l] * ESUN[l];
                    }
                }
                /* sunlight reflected by the ground at the end of the segment: also order seg */
                double ctot[NS] = {0, 0, 0};
                if (ns > 0)
                    for (int i = 0; i < NS; i++) ctot[i] = st[ns - 1].c0[i] + st[ns - 1].nd[i] * st[ns - 1].ds;
                double xg[3], nrm[3], musg = 0;
                if (ground) {
                    for (int i = 0; i < 3; i++) xg[i] = p[i] + len * d[i];
                    for (int i = 0; i < 3; i++) nrm[i] = xg[i];
                    norm3(nrm);
                    musg = nrm[0] * sun[0] + nrm[1] * sun[1] + nrm[2] * sun[2];
                    double cs[NS];
                    if (seg >= min_order && musg > 0 && sun_columns(R, musg, cs)) {
                        for (int l = 0; l < NL; l++) {
                            double tau = 0;
                            for (int i = 0; i < NS; i++) tau += SEXT[i][l] * (ctot[i] + cs[i]);
                            L[l] += w[l] * ALBEDO / M_PI * musg * exp(-tau) * ESUN[l];
                        }
                    }
                }
                if (seg == max_order || ns == 0) break;
                /* next vertex: one-sample spectral MIS. A hero wavelength h is drawn with
                   probability q_l proportional to w_l, and its own free path decides the
                   event; the weight then divides by the q-mixture of every wavelength's
                   pdf, which keeps weights bounded however thick the segment is. */
                double TL[NLMAX], qv[NLMAX], qs = 0;
                for (int l = 0; l < NL; l++) {
                    double tau = 0;
                    for (int i = 0; i < NS; i++) tau += SEXT[i][l] * ctot[i];
                    TL[l] = -tau;
                    qs += w[l];
                }
                vvexp(TL, TL, &NL);
                if (!(qs > 0)) break;
                int h = NL - 1;
                {
                    double u = rnd(&rg) * qs, acc = 0;
                    for (int l = 0; l < NL; l++) { qv[l] = w[l] / qs; acc += w[l]; if (u < acc && h == NL - 1) h = l; }
                }
                double target;
                int to_ground = 0;
                if (ground) {
                    target = -log(1 - rnd(&rg));
                    double tauh = -log(TL[h] > 1e-300 ? TL[h] : 1e-300);
                    if (target >= tauh) to_ground = 1;
                } else {
                    target = -log(1 - rnd(&rg) * (1 - TL[h]));
                }
                if (to_ground) {
                    double pgm = 0;
                    for (int l = 0; l < NL; l++) pgm += qv[l] * TL[l];
                    for (int l = 0; l < NL; l++) w[l] *= TL[l] / pgm * ALBEDO;
                    double c = sqrt(rnd(&rg));
                    double nd2[3];
                    dir_from(nrm, c, 2 * M_PI * rnd(&rg), nd2);
                    for (int i = 0; i < 3; i++) { p[i] = xg[i] + nrm[i] * 0.01; d[i] = nd2[i]; }
                } else {
                    /* locate the step where wavelength h's optical depth reaches target */
                    int lo = 0, hi = ns - 1;
                    while (lo < hi) {
                        int mid = (lo + hi + 1) / 2;
                        double tm = 0;
                        for (int i = 0; i < NS; i++) tm += SEXT[i][h] * st[mid].c0[i];
                        if (tm <= target) lo = mid; else hi = mid - 1;
                    }
                    step_t *q = st + lo;
                    double t0 = 0, bh = 0;
                    for (int i = 0; i < NS; i++) { t0 += SEXT[i][h] * q->c0[i]; bh += SEXT[i][h] * q->nd[i]; }
                    if (bh <= 0) break;
                    double dt = (target - t0) / bh;
                    if (dt < 0) dt = 0;
                    if (dt > q->ds) dt = q->ds;
                    double cpt[NS], el[NLMAX], bt[NLMAX], sR[NLMAX], sM[NLMAX];
                    for (int i = 0; i < NS; i++) cpt[i] = q->c0[i] + q->nd[i] * dt;
                    for (int l = 0; l < NL; l++) {
                        double tau = 0, b = 0;
                        for (int i = 0; i < NS; i++) { tau += SEXT[i][l] * cpt[i]; b += SEXT[i][l] * q->nd[i]; }
                        el[l] = -tau; bt[l] = b;
                        sR[l] = q->nd[0] * SSCA[0][l];
                        sM[l] = q->nd[1] * SSCA[1][l];
                    }
                    vvexp(el, el, &NL);
                    double mix = 0;
                    for (int l = 0; l < NL; l++) {
                        double nrmz = ground ? 1.0 : (1 - TL[l]);
                        if (nrmz > 0) mix += qv[l] * bt[l] * el[l] / nrmz;
                    }
                    if (!(mix > 0)) break;
                    for (int l = 0; l < NL; l++) w[l] *= (sR[l] + sM[l]) * el[l] / mix;
                    double tt = q->t + dt;
                    double x[3] = {p[0] + tt * d[0], p[1] + tt * d[1], p[2] + tt * d[2]};
                    double aR = 0, aM = 0;
                    for (int l = 0; l < NL; l++) {
                        double f = w[l] / (sR[l] + sM[l] + 1e-300);
                        aR += f * sR[l]; aM += f * sM[l];
                    }
                    if (aR + aM <= 0) break;
                    double qR = aR / (aR + aM);
                    /* direction: mixture of the phase function and, once the sun is below
                       this point's horizon, a guide lobe aimed low towards the sun's azimuth
                       (where the sunlit air is nearest); weights use the mixture pdf. */
                    double up[3] = {x[0], x[1], x[2]};
                    norm3(up);
                    double sup = up[0] * sun[0] + up[1] * sun[1] + up[2] * sun[2];
                    double gm[3] = {sun[0] - sup * up[0], sun[1] - sup * up[1], sun[2] - sup * up[2]};
                    double gn = sqrt(gm[0] * gm[0] + gm[1] * gm[1] + gm[2] * gm[2]);
                    double alpha = (sup < 0.05 && gn > 1e-6) ? GUIDE_P : 0.0;
                    if (alpha > 0) {
                        for (int i = 0; i < 3; i++) gm[i] = GUIDE_C * gm[i] / gn + GUIDE_S * up[i];
                        norm3(gm);
                    }
                    double nd2[3];
                    if (rnd(&rg) < alpha) {
                        double xi = rnd(&rg);
                        double cg = 1 + log(xi + (1 - xi) * exp(-2 * GUIDE_K)) / GUIDE_K;
                        if (cg > 1) cg = 1;
                        if (cg < -1) cg = -1;
                        dir_from(gm, cg, 2 * M_PI * rnd(&rg), nd2);
                    } else {
                        double c = rnd(&rg) < qR ? sample_rayleigh_cos(&rg) : sample_hg_cos(&rg);
                        dir_from(d, c, 2 * M_PI * rnd(&rg), nd2);
                    }
                    double c = d[0] * nd2[0] + d[1] * nd2[1] + d[2] * nd2[2];
                    double pr = phase_rayleigh(c), pm2 = phase_hg(c);
                    double pdfd = (1 - alpha) * (qR * pr + (1 - qR) * pm2);
                    if (alpha > 0) {
                        double cg = gm[0] * nd2[0] + gm[1] * nd2[1] + gm[2] * nd2[2];
                        pdfd += alpha * GUIDE_K / (2 * M_PI * (1 - exp(-2 * GUIDE_K))) * exp(GUIDE_K * (cg - 1));
                    }
                    for (int l = 0; l < NL; l++)
                        w[l] *= (sR[l] * pr + sM[l] * pm2) / (sR[l] + sM[l] + 1e-300) / pdfd;
                    for (int i = 0; i < 3; i++) { p[i] = x[i]; d[i] = nd2[i]; }
                }
                if (seg >= 3) {
                    double m = 0;
                    for (int l = 0; l < NL; l++) m += w[l];
                    m /= NL;
                    double surv = m < 1 ? m : 1;
                    if (surv < 0.05) surv = 0.05;
                    if (rnd(&rg) > surv) break;
                    for (int l = 0; l < NL; l++) w[l] /= surv;
                }
            }
        }
        for (int l = 0; l < NL; l++) L[l] /= npath;
    }
    free(st);
}
