"""O_null1: CPU-only geometry, statistics and immutable artifacts (D-057)."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ZONES = {"skin": [12, 14, 16, 15], "background": [0], "hair_face": [1, 2],
         "occluders": [13], "clothing": [3, 4, 5, 6, 7, 10]}
NORMATIVE_ZONES = ("skin", "background", "hair_face", "occluders")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def sha256(path, lf=False):
    if lf:
        return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_new(image, path):
    with Path(path).open("xb") as stream:
        image.save(stream, format="PNG")


def rgb(path):
    with Image.open(path) as im:
        require(im.getexif().get(274, 1) == 1, "EXIF orientation changes the pinned A canvas")
        return im.convert("RGB")


def mask(path, size):
    with Image.open(path) as im:
        require(im.mode in ("1", "L") and im.size == size, "invalid binary mask mode/grid")
        a = np.asarray(im.convert("L"))
    require(np.isin(a, [0, 255]).all(), "mask must contain only 0/255")
    return a == 255


def save_mask(values, path):
    save_new(Image.fromarray(np.asarray(values, dtype=np.uint8) * 255), path)


def zones_from_labels(labels):
    require(labels.ndim == 2 and np.issubdtype(labels.dtype, np.integer), "invalid parser labels")
    require(np.isin(labels, range(18)).all(), "unknown parser label; stop")
    return {name: np.isin(labels, ids) for name, ids in ZONES.items()}


def geometry(route, size=(725, 1536)):
    """Pixel-edge coordinates; support membership uses original pixel centers."""
    require(tuple(size) == (725, 1536), "only the pinned A geometry is prepared")
    w, h = size
    if route == "klein":
        scale = math.sqrt(1024 * 1024 / (w * h))
        sw, sh = round(w * scale), round(h * scale)
        # sd.VAE.vae_encode_crop_pixels: spatial compression=16 for Flux2 BN VAE.
        cw, ch = sw // 16 * 16, sh // 16 * 16
        x, y = (sw % 16) // 2, (sh % 16) // 2
        return {"scaled": [sw, sh], "internal": [cw, ch], "crop_scaled": [x, y, x+cw, y+ch],
                "box_on_A": [x*w/sw, y*h/sh, (x+cw)*w/sw, (y+ch)*h/sh],
                "inverse": "Pillow affine BICUBIC, pixel-edge map; support by pixel centers"}
    if route == "qie":
        sw, sh = 688, 1504  # pinned FluxKontextImageScale table choice for A
        x = round((w - h * sw / sh) / 2)
        return {"scaled": [sw, sh], "internal": [sw, sh], "box_on_A": [x, 0, w-x, h],
                "inverse": "Pillow LANCZOS to exact integer source crop, paste whole box"}
    if route == "r1ei":
        return {"scaled": [1024, 1024], "internal": [1024, 1024],
                "box_on_A": [-136, 193, 860, 1189],
                "inverse": "Pillow LANCZOS to 996x996, paste whole box; no insertion mask"}
    require(route == "fashn", "unknown route")
    return {"scaled": [407, 864], "internal": [576, 864], "unpad": [407, 864],
            "box_on_A": [0, 0, w, h], "inverse": "Pillow LANCZOS to original A canvas"}


def support_for_geometry(size, geo):
    w, h = size
    left, top, right, bottom = geo["box_on_A"]
    xx, yy = np.arange(w) + 0.5, np.arange(h) + 0.5
    return ((yy[:, None] >= top) & (yy[:, None] < bottom)
            & (xx[None, :] >= left) & (xx[None, :] < right))


def reproject(A, decoded, route):
    geo = geometry(route, A.size)
    expected = geo.get("unpad", geo["internal"])
    require(list(decoded.size) == expected and decoded.mode == "RGB", "unexpected native output grid/mode")
    left, top, right, bottom = geo["box_on_A"]
    support = support_for_geometry(A.size, geo)
    if route == "klein":
        sx, sy = decoded.width/(right-left), decoded.height/(bottom-top)
        projected = decoded.transform(A.size, Image.Transform.AFFINE,
                                      (sx, 0, -left*sx, 0, sy, -top*sy), Image.Resampling.BICUBIC)
        result = Image.composite(projected, A, Image.fromarray(support.astype(np.uint8)*255))
    else:
        resized = decoded.resize((int(right-left), int(bottom-top)), Image.Resampling.LANCZOS)
        result = A.copy()
        result.paste(resized, (int(left), int(top)))
    require(np.array_equal(np.asarray(result)[~support], np.asarray(A)[~support]), "copied pixels changed")
    return result, support, geo


def distribution(values):
    if not values.size:
        return None
    p = np.percentile(values, [50, 95, 99, 99.5], method="linear")
    return {"n": int(values.size), "p50": float(p[0]), "p95": float(p[1]), "p99": float(p[2]),
            "p995": float(p[3]), "max": int(values.max()), "mean": float(values.mean()),
            "histogram_0_255": np.bincount(values, minlength=256).tolist()}


def tolerance(stats):
    return None if stats is None else max(1, math.ceil(stats["p995"]))


def null_statistics(a_path, output, support_path, zone_paths, route_config):
    A, O = rgb(a_path), rgb(output)
    require(A.size == O.size, "canvas mismatch")
    with Image.open(output) as image:
        require(image.mode == "RGB", "O_null1 must be RGB8")
    support = mask(support_path, A.size)
    require(support.any(), "empty reconstruction support")
    require(set(zone_paths) == set(ZONES), "all five zone masks are required")
    d = np.abs(np.asarray(O).astype(np.int32)-np.asarray(A).astype(np.int32)).max(axis=2)
    require((d[~support] == 0).all(), "outside support must be copied A")
    stats = {"support": distribution(d[support]), "by_zone": {}}
    counts = {"canvas": int(d.size), "support": int(support.sum()), "by_zone": {}}
    for name, path in zone_paths.items():
        zone = mask(path, A.size)
        selected = zone & support
        counts["by_zone"][name] = {"total": int(zone.sum()), "support": int(selected.sum())}
        stats["by_zone"][name] = distribution(d[selected])
    return {"schema_version": 1, "kind": "O_null1", "metric": "max_RGB(abs(uint8(O_null1)-uint8(A)))",
            "quantile": "numpy percentile linear; tolerance=max(1,ceil(p99.5))",
            "tol_p995_support": tolerance(stats["support"]),
            "tol_p995_by_zone": {k: tolerance(stats["by_zone"][k]) for k in NORMATIVE_ZONES},
            "support_fraction": float(support.mean()), "counts": counts, "statistics": stats,
            "sha256": {"a": sha256(a_path), "o_null1": sha256(output), "support": sha256(support_path),
                       "zones": {k: sha256(v) for k, v in zone_paths.items()}},
            "route_config": route_config,
            "status": "MEASURED_PENDING_CLAUDE_REVIEW", "clothing": "reported only; no normative tolerance"}
