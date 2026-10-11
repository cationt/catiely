"""D-059 grid metadata and nearest mask transport, CPU only.

RGB A_forward is an executor artifact, NOT reconstructed by an auditor here.
Coordinates are pixel edges; integer crop conventions match the pinned executors.
One MP follows ImageScaleToTotalPixels: 1024**2 pixels.
"""
import math

import numpy as np
from PIL import Image

KONTEXT_RESOLUTIONS = ((672,1568),(688,1504),(720,1456),(752,1392),(800,1328),
                      (832,1248),(880,1184),(944,1104),(1024,1024),(1104,944),
                      (1184,880),(1248,832),(1328,800),(1392,752),(1456,720),
                      (1504,688),(1568,672))


def require(value, message):
    if not value:
        raise ValueError(message)


def center_box(size, target):
    """Integer symmetric crop from pinned ComfyUI common_upscale(center)."""
    w, h = size
    tw, th = target
    x = round((w - w * ((tw/th)/(w/h))) / 2) if w/h > tw/th else 0
    y = round((h - h * ((w/h)/(tw/th))) / 2) if w/h < tw/th else 0
    return [x, y, w-x, h-y]


def kontext_size(size):
    _, w, h = min((abs(size[0]/size[1]-w/h), w, h) for w,h in KONTEXT_RESOLUTIONS)
    return w, h


def insertion_box(size, bbox):
    """Pinned Easy-Insert square_crop_by_mask, scale=1.2; no clipping."""
    w, h = size
    if bbox is None:  # the pinned empty-mask behavior
        cx, cy, side = w/2, h/2, float(min(w,h))
    else:
        l, t, r, b = bbox
        require(r > l and b > t, "invalid insertion bbox")
        cx, cy, side = (l+r)/2, (t+b)/2, max(r-l,b-t)*1.2
    side = max(1, int(round(side)))
    l, t = int(round(cx-side/2)), int(round(cy-side/2))
    return [l,t,l+side,t+side]


def forward_grid(route, size, parameters=None):
    """Describe an exact case tuple; defaults are G0 tuples, table/1MP explicit.

    R1-EI needs insertion_bbox (including explicit None) or a frozen crop_box.
    contact_fringe_px is optional for calibration, which has no frozen case yet.
    It never acquires an invented default or becomes a threshold in this module.
    """
    p = dict(parameters or {})
    w, h = size
    require(all(type(v) is int and v > 0 for v in size), "invalid A size")
    steps = []
    box = [0,0,w,h]
    if route == "klein":
        policy = p.pop("policy", "crop16")
        if policy == "crop16":
            cw, ch = w//16*16, h//16*16
            require(cw > 0 and ch > 0, "A smaller than VAE multiple")
            require(cw*ch <= 1.1*1024**2, "crop exceeds D-059 1.1MP; explicit 1MP tuple/null required")
            x,y = (w-cw)//2,(h-ch)//2
            box = [x,y,x+cw,y+ch]
            steps = [{"crop": box}]
            scale = 1.0
            policy = "ImageCrop multiples16, no resize"
        elif policy == "1mp":
            s = math.sqrt(1024**2/(w*h))
            sw,sh = round(w*s),round(h*s)
            cw,ch = sw//16*16,sh//16*16
            x,y = (sw%16)//2,(sh%16)//2
            require(cw > 0 and ch > 0, "empty scaled crop")
            steps = [{"resize": [sw,sh]}, {"crop": [x,y,x+cw,y+ch]}]
            box = [x*w/sw,y*h/sh,(x+cw)*w/sw,(y+ch)*h/sh]
            scale = s
            policy = "ImageScaleToTotalPixels nearest-exact 1MP -> VAE crop16"
        else:
            raise ValueError("unknown Klein policy")
    elif route == "qie":
        policy = p.pop("policy", "544x960")
        require(policy in ("544x960", "kontext_table"), "unknown QIE policy")
        cw,ch = (544,960) if policy == "544x960" else kontext_size(size)
        box = center_box(size, (cw,ch))
        steps = [{"crop": box}, {"resize": [cw,ch]}]
        scale = max(cw/w,ch/h)
        policy = ("ImageScale lanczos center 544x960" if policy == "544x960" else
                  "FluxKontextImageScale table, lanczos center")
    elif route == "r1ei":
        require("crop_box" in p or "insertion_bbox" in p, "R1-EI requires frozen insertion bbox/crop box")
        require(not ("crop_box" in p and "insertion_bbox" in p), "ambiguous R1-EI box")
        box = p.pop("crop_box") if "crop_box" in p else insertion_box(size,p.pop("insertion_bbox"))
        l,t,r,b = box
        require(all(type(v) is int for v in box) and r-l == b-t and r>l, "invalid square crop")
        cw,ch = 1024,1024
        scale = 1024/(r-l)
        steps = [{"crop": list(box)}, {"resize": [cw,ch]}]
        policy = "Easy-Insert insertion bbox x1.2 -> black-padded square -> PIL LANCZOS 1024x1024"
    elif route == "fashn":
        scale = min(1.0,864/max(w,h))
        cw,ch = int(w*scale),int(h*scale)
        require(cw > 0 and ch > 0, "empty FASHN fit")
        steps = [{"resize": [cw,ch]}]
        # ResizePad has its own fit (allows upsampling); unpad keeps that size.
        pad_scale = min(576/cw,864/ch)
        cw,ch = int(cw*pad_scale),int(ch*pad_scale)
        steps.append({"resize": [cw,ch]})
        scale *= pad_scale
        policy = "AspectPreserveResize fit864 no upsample -> ResizePad576x864 -> unpad"
    else:
        raise ValueError("unknown route")
    fringe = p.pop("contact_fringe_px", None)
    require(not p, "unknown geometry parameters: " + str(sorted(p)))
    require(fringe is None or (math.isfinite(fringe) and fringe >= 0), "invalid fringe")
    l,t,r,b = box
    sx,sy = cw/(r-l),ch/(b-t)
    return {"route": route, "width": cw, "height": ch, "a_size": [w,h],
            "forward_policy": policy, "box_on_A": list(box), "mask_steps": steps,
            "mask_resampling": "Pillow NEAREST", "affine_A_to_grid": [sx,0,-l*sx,0,sy,-t*sy],
            "scale_linear": scale,
            "contact_fringe_px_internal": None if fringe is None else max(1,math.floor(fringe*scale+0.5)),
            "memory_smoke_required": route == "klein" and cw*ch > 1024**2}


def forward_mask(values, grid):
    """Transport a binary mask, with zero validity outside the A canvas."""
    a = np.asarray(values)
    require(a.dtype == np.bool_ and list(a.shape[::-1]) == grid["a_size"], "mask grid/type mismatch")
    im = Image.fromarray(a.astype(np.uint8)*255)
    for step in grid["mask_steps"]:
        im = im.crop(step["crop"]) if "crop" in step else im.resize(step["resize"], Image.Resampling.NEAREST)
    require(im.size == (grid["width"],grid["height"]), "grid mismatch")
    return np.asarray(im) == 255


def validity_support(grid):
    w,h = grid["a_size"]
    return forward_mask(np.ones((h,w),bool),grid)


def forward_keypoints(points, grid):
    """Affine coordinates, discard outside points; preserves extra columns."""
    points = np.asarray(points,dtype=float)
    require(points.ndim == 2 and points.shape[1] >= 2 and np.isfinite(points).all(), "invalid keypoints")
    result = points.copy()
    sx,_,tx,_,sy,ty = grid["affine_A_to_grid"]
    result[:,0] = points[:,0]*sx+tx
    result[:,1] = points[:,1]*sy+ty
    inside = ((result[:,0]>=0)&(result[:,0]<grid["width"])&
              (result[:,1]>=0)&(result[:,1]<grid["height"]))
    return result[inside], int((~inside).sum())
