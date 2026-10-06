"""Turn the rendered XYZ sky grids into images for the page.

For each sun elevation, one exposure is chosen from the 300 DU sky and applied to
every ozone case, so the cases can be compared like-for-like. The tone curve is
linear through the mid-tones and only compresses highlights (the glow round the
sun), keeping hue; out-of-gamut colours are desaturated towards their own grey.

    .venv/bin/python make_images.py             # panoramas + frames.json for the page
    .venv/bin/python make_images.py --domes     # page domes at sun -5 deg, hero.png, thumb.png
"""
import glob
import json
import math
import os
import sys

import numpy as np
from PIL import Image

from skymodel import M_XYZ_TO_SRGB, srgb_encode, xyz_to_xy

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "raw", "frames")
IMG = os.path.join(HERE, "img")

PANO_W, PANO_H, PANO_EL = 2048, 364, 64.0   # 360 deg wide, 0..64 deg tall: 5.69 px per degree both ways
KEY = 0.28                                   # log-average sky luminance maps to this


def load(du, se):
    return np.load(os.path.join(FRAMES, f"o3_{du}_sun_{se:+05.1f}.npz"))


def ms_log(f):
    """Log of the coarse multiple-scattering grid, with the zenith node (one direction,
    sampled once per azimuth) replaced by its mean, and a light [1,2,1] smoothing in azimuth."""
    ms = np.log(np.maximum(f["ms_xyz"].astype(float), 1e-30))
    ms[:, -1, :] = ms[:, -1, :].mean(axis=0)
    pad = np.concatenate([ms[1:2], ms, ms[-2:-1]], axis=0)     # mirror at 0 and 180 deg
    return 0.25 * pad[:-2] + 0.5 * pad[1:-1] + 0.25 * pad[2:]


def total_xyz(f, ms=None):
    """SS on the fine grid plus MS interpolated (log-linear) from the coarse grid."""
    az, el = f["az"], f["el"]
    maz, mel = f["ms_az"], f["ms_el"]
    if ms is None:
        ms = ms_log(f)
    # interpolate along elevation, then azimuth
    tmp = np.empty((len(maz), len(el), 3))
    for i in range(len(maz)):
        for c in range(3):
            tmp[i, :, c] = np.interp(el, mel, ms[i, :, c])
    out = np.empty((len(az), len(el), 3))
    for j in range(len(el)):
        for c in range(3):
            out[:, j, c] = np.interp(az, maz, tmp[:, j, c])
    return f["ss_xyz"].astype(float) + np.exp(out)


def smoothed_ms(du, elevs):
    """MS log-grids for one ozone case, smoothed [1,2,1] across neighbouring sun elevations
    once the sun is more than 5 deg down (where the sky is mostly multiply scattered and noisiest).
    The curvature of log-brightness against elevation is small, so the bias is too."""
    logs = [ms_log(load(du, e)) for e in elevs]
    out = []
    for i, e in enumerate(elevs):
        if e > -5.25 or i == 0 or i == len(elevs) - 1:
            out.append(logs[i])
        else:
            out.append(0.25 * logs[i - 1] + 0.5 * logs[i] + 0.25 * logs[i + 1])
    return out


def log_average_luminance(xyz, el):
    """Solid-angle weighted geometric mean of Y over the upper hemisphere."""
    Y = np.maximum(xyz[..., 1], 1e-12)
    w = np.cos(np.radians(el))[None, :] * np.gradient(el)[None, :] * np.ones((xyz.shape[0], 1))
    return float(np.exp((w * np.log(Y)).sum() / w.sum()))


def horizontal_illuminance(xyz, az, el):
    """Illuminance on a horizontal surface from the whole sky (lux): both mirrored halves."""
    a, e = np.radians(az), np.radians(el)
    f = xyz[..., 1] * (np.sin(e) * np.cos(e))[None, :]
    return float(2 * np.trapezoid(np.trapezoid(f, e, axis=1), a))


def tone_map(xyz, k):
    rgb = np.tensordot(xyz * k, M_XYZ_TO_SRGB.T, axes=([-1], [0]))
    Y = (xyz * k)[..., 1:2]
    # gamut: desaturate towards grey of the same luminance until no channel is negative
    mn = rgb.min(axis=-1, keepdims=True)
    t = np.where(mn < 0, Y / np.maximum(Y - mn, 1e-12), 1.0)
    rgb = Y + (rgb - Y) * np.clip(t, 0, 1)
    m = np.maximum(rgb.max(axis=-1, keepdims=True), 1e-12)
    knee = 0.62
    fm = np.where(m <= knee, m, knee + (1 - knee) * (1 - np.exp(-(m - knee) / (1 - knee))))
    scaled = rgb * fm / m
    w = np.clip((m - 1) / (m + 4), 0, 1) * 0.9          # very bright -> towards white, like film
    return scaled * (1 - w) + fm * w


def to_image(rgb_lin, rng):
    s = srgb_encode(np.clip(rgb_lin, 0, 1)) * 255
    s = s + (rng.random(s.shape) - rng.random(s.shape))  # triangular dither against banding
    return Image.fromarray(np.clip(np.round(s), 0, 255).astype(np.uint8))


def panorama(xyz, az, el):
    """Equirectangular strip, sun's azimuth at the centre, both mirrored halves."""
    xs = (np.arange(PANO_W) + 0.5) / PANO_W * 360 - 180
    ys = (1 - (np.arange(PANO_H) + 0.5) / PANO_H) * PANO_EL
    A = np.abs(xs)
    ia = np.interp(A, az, np.arange(len(az)))
    ie = np.interp(ys, el, np.arange(len(el)))
    a0 = np.clip(np.floor(ia).astype(int), 0, len(az) - 2)
    e0 = np.clip(np.floor(ie).astype(int), 0, len(el) - 2)
    fa, fe = (ia - a0)[None, :, None], (ie - e0)[:, None, None]
    g = xyz
    v00 = g[a0[None, :], e0[:, None]]
    v10 = g[a0[None, :] + 1, e0[:, None]]
    v01 = g[a0[None, :], e0[:, None] + 1]
    v11 = g[a0[None, :] + 1, e0[:, None] + 1]
    return (1 - fa) * (1 - fe) * v00 + fa * (1 - fe) * v10 + (1 - fa) * fe * v01 + fa * fe * v11


def strip(xyz, az, el, centre, span, top, px_per_deg=6.0):
    """A horizon strip centred on azimuth `centre` (degrees from the sun), `span` wide, 0..top tall."""
    w, h = int(round(span * px_per_deg)), int(round(top * px_per_deg))
    xs = centre + ((np.arange(w) + 0.5) / w - 0.5) * span
    A = np.abs(((xs + 180) % 360) - 180)
    ys = (1 - (np.arange(h) + 0.5) / h) * top
    ia = np.interp(A, az, np.arange(len(az)))
    ie = np.interp(ys, el, np.arange(len(el)))
    a0 = np.clip(np.floor(ia).astype(int), 0, len(az) - 2)
    e0 = np.clip(np.floor(ie).astype(int), 0, len(el) - 2)
    fa, fe = (ia - a0)[None, :, None], (ie - e0)[:, None, None]
    return ((1 - fa) * (1 - fe) * xyz[a0[None, :], e0[:, None]] + fa * (1 - fe) * xyz[a0[None, :] + 1, e0[:, None]]
            + (1 - fa) * fe * xyz[a0[None, :], e0[:, None] + 1] + fa * fe * xyz[a0[None, :] + 1, e0[:, None] + 1])


def make_east(se=-1.0):
    """Facing east (away from the sun) just after sunset, with and without ozone, same exposure."""
    f3 = load(300, se)
    k = KEY / log_average_luminance(total_xyz(f3), f3["el"])
    for du in (300, 0):
        f = load(du, se)
        img = to_image(tone_map(strip(total_xyz(f), f["az"], f["el"], 180, 140, 26), k), np.random.default_rng(2))
        img.save(os.path.join(IMG, f"east_{du}.webp"), "WEBP", quality=88, method=6)


def dome(xyz, az, el, size):
    """Equidistant fisheye, zenith at the centre, sun at the bottom (west down)."""
    c = (np.arange(size) + 0.5) / size * 2 - 1
    X, Yc = np.meshgrid(c, c)
    r = np.hypot(X, Yc)
    zen = r * 90
    elev = 90 - zen
    A = np.degrees(np.abs(np.arctan2(X, Yc)))       # 0 at the bottom of the image (towards the sun)
    ia = np.interp(A, az, np.arange(len(az)))
    ie = np.interp(np.clip(elev, 0, 90), el, np.arange(len(el)))
    a0 = np.clip(np.floor(ia).astype(int), 0, len(az) - 2)
    e0 = np.clip(np.floor(ie).astype(int), 0, len(el) - 2)
    fa, fe = (ia - a0)[..., None], (ie - e0)[..., None]
    out = ((1 - fa) * (1 - fe) * xyz[a0, e0] + fa * (1 - fe) * xyz[a0 + 1, e0]
           + (1 - fa) * fe * xyz[a0, e0 + 1] + fa * fe * xyz[a0 + 1, e0 + 1])
    return out, r <= 1


def sun_disc(f, k):
    """Colour (tone-mapped linear sRGB, before encoding) of the direct solar disc."""
    from skymodel import ESUN, spectrum_to_xyz
    T = f["direct"]
    if T.max() <= 0:
        return None
    omega = 2 * math.pi * (1 - math.cos(math.radians(0.2666)))
    xyz = spectrum_to_xyz(ESUN * T / omega)
    return tone_map(xyz[None, :], k)[0], float(xyz[1])


def main():
    os.makedirs(IMG, exist_ok=True)
    files = glob.glob(os.path.join(FRAMES, "o3_300_sun_*.npz"))
    elevs = sorted({float(os.path.basename(p)[11:16]) for p in files}, reverse=True)
    cases = [du for du in (300, 0, 100)
             if all(os.path.exists(os.path.join(FRAMES, f"o3_{du}_sun_{e:+05.1f}.npz")) for e in elevs)]
    rng = np.random.default_rng(5)
    meta = {"elevations": elevs, "cases": cases, "pano": [PANO_W, PANO_H, PANO_EL], "frames": {}}
    ms = {du: smoothed_ms(du, elevs) for du in cases}
    for i, se in enumerate(elevs):
        f300 = load(300, se)
        k = KEY / log_average_luminance(total_xyz(f300, ms[300][i]), f300["el"])
        for du in cases:
            f = load(du, se)
            xyz = total_xyz(f, ms[du][i])
            img = to_image(tone_map(panorama(xyz, f["az"], f["el"]), k), rng)
            name = f"pano_{du}_{se:+05.1f}.webp"
            img.save(os.path.join(IMG, name), "WEBP", quality=80, method=6)
            sd = sun_disc(f, k)
            meta["frames"][f"{du}/{se}"] = {
                "img": "img/" + name,
                "exposure": k,
                "zenith_Y": float(xyz[0, -1, 1]),
                "illuminance": horizontal_illuminance(xyz, f["az"], f["el"]),
                "sun": None if sd is None else [round(float(v), 4) for v in sd[0]],
            }
        print(f"sun {se:+5.1f}  exposure {k:.3g}", flush=True)
    json.dump(meta, open(os.path.join(HERE, "data", "frames.json"), "w"), indent=0)


def dome_rgb(se, du, size, k=None, ms=None):
    f = load(du, se)
    xyz = total_xyz(f, ms)
    if k is None:
        f3 = load(300, se)
        k = KEY / log_average_luminance(total_xyz(f3), f3["el"])
    d, mask = dome(xyz, f["az"], f["el"], size)
    return tone_map(d, k), mask


def make_domes(se=-5.0, size=560):
    """The two static domes for the page (same exposure), plus the split-dome
    hero.png and thumb.png for the house pages: with ozone on the left half, none on
    the right. The sky is mirror-symmetric about the sun's meridian (the vertical
    axis here), so each half shows everything."""
    ms = {du: ms_log(load(du, se)) for du in (300, 0)}      # -5 deg is not smoothed in time
    f3 = load(300, se)
    k = KEY / log_average_luminance(total_xyz(f3, ms[300]), f3["el"])
    for du in (300, 0):
        rgb, mask = dome_rgb(se, du, size, k, ms[du])
        img = to_image(rgb, np.random.default_rng(1)).convert("RGBA")
        a = np.array(img)
        a[..., 3] = np.where(mask, 255, 0)
        Image.fromarray(a).save(os.path.join(IMG, f"dome_{du}.webp"), "WEBP", quality=88, method=6)
    for name, size_px, pad in (("hero.png", 1100, 40), ("thumb.png", 560, 20)):
        n = size_px - 2 * pad
        left, mask = dome_rgb(se, 300, n, k, ms[300])
        right, _ = dome_rgb(se, 0, n, k, ms[0])
        rgb = left.copy()
        rgb[:, n // 2:] = right[:, n // 2:]
        s = srgb_encode(np.clip(rgb, 0, 1)) * 255
        bg = np.array([10, 15, 29], float)                 # the page's night panel
        s = np.where(mask[..., None], s, bg)
        s[:, n // 2 - max(1, n // 400): n // 2 + max(1, n // 400)] = bg   # a hairline at the split
        canvas = np.tile(bg, (size_px, size_px, 1))
        canvas[pad:pad + n, pad:pad + n] = s
        im = Image.fromarray(np.round(canvas).astype(np.uint8))
        im.save(os.path.join(HERE, name), optimize=True)
        print(name, os.path.getsize(os.path.join(HERE, name)) // 1024, "KB")


if __name__ == "__main__":
    if "--domes" in sys.argv:
        make_domes()
        make_east()
    else:
        main()
