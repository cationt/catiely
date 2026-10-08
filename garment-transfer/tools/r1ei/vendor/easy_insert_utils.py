
import random

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter



def binarize_mask(mask, threshold=0):
    return mask.point(lambda p: 255 if p > threshold else 0).convert("L")


def square_crop_by_mask(image, mask, scale=1.2):
    W, H = image.size
    bbox = mask.getbbox()
    if bbox is None:
        cx, cy = W / 2.0, H / 2.0
        side = float(min(W, H))
    else:
        l, u, r, lo = bbox
        cx = (l + r) / 2.0
        cy = (u + lo) / 2.0
        side = max(r - l, lo - u) * scale
    side_i = max(1, int(round(side)))
    left = int(round(cx - side_i / 2.0))
    top = int(round(cy - side_i / 2.0))
    box = (left, top, left + side_i, top + side_i)
    # PIL fills out-of-bounds crop regions with 0: black for the RGB image and
    # "unmasked" (0) for the L mask - exactly the black padding we want.
    return image.crop(box), mask.crop(box), box



def process_source(source_image, source_mask, image_size=1024, crop_scale=1.2, binarize_threshold=0):
    source_mask = binarize_mask(source_mask, binarize_threshold)
    source_image_c, source_mask_c, crop_box = square_crop_by_mask(source_image, source_mask, crop_scale)
    size = (image_size, image_size)
    image = source_image_c.resize(size, Image.LANCZOS)        # GT crop
    mask = source_mask_c.resize(size, Image.NEAREST)
    white = Image.new("RGB", size, (255, 255, 255))
    # composite(white, image, mask): mask==255 -> white, mask==0 -> image
    background_image = Image.composite(white, image, mask)
    return background_image, image, crop_box, source_mask_c


def process_reference(ref_image, ref_mask, image_size=1024, crop_scale=1.2,
                      binarize_threshold=0, augment=False, p_aug=0.8):
    ref_mask = binarize_mask(ref_mask, binarize_threshold)
    ref_image_c, ref_mask_c, _ = square_crop_by_mask(ref_image, ref_mask, crop_scale)
    size = (image_size, image_size)
    ref_image_r = ref_image_c.resize(size, Image.LANCZOS)
    ref_mask_r = ref_mask_c.resize(size, Image.NEAREST)
    white = Image.new("RGB", size, (255, 255, 255))
    # composite(ref_image, white, mask): mask==255 -> object, mask==0 -> white
    ref_image_out = Image.composite(ref_image_r, white, ref_mask_r)
    if augment:
        ref_image_out = augment_ref_image(ref_image_out, ref_mask_r, p_aug=p_aug)
    return ref_image_out


def paste_back(generated_crop, source_image, crop_box, source_mask_cropped, feather=0):
    left, top, right, bottom = crop_box
    crop_side = right - left
    generated_crop = generated_crop.resize((crop_side, crop_side), Image.LANCZOS)
    original_crop = source_image.crop(crop_box)
    if feather > 0:
        source_mask_cropped = source_mask_cropped.filter(ImageFilter.GaussianBlur(feather))
    edited_crop = Image.composite(generated_crop, original_crop, source_mask_cropped)
    final_image = source_image.copy()
    final_image.paste(edited_crop, (left, top))
    return final_image


def _adjust_hue(img, shift):
    """Shift the hue of an RGB image by ``shift`` (in 0..255 units)."""
    hsv = img.convert("HSV")
    h, s, v = hsv.split()
    h_arr = (np.asarray(h).astype(np.int16) + int(round(shift))) % 256
    h = Image.fromarray(h_arr.astype(np.uint8), "L")
    return Image.merge("HSV", (h, s, v)).convert("RGB")


def augment_ref_image(ref_image, mask, p_aug=0.8):
    img = ref_image.convert("RGB").copy()
    m = mask.convert("L")

    # Horizontal flip is safe: the object sits on a uniform white background.
    if random.random() < 0.5:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        m = m.transpose(Image.FLIP_LEFT_RIGHT)

    # Colour jitter on the whole image; background is re-whitened below.
    if random.random() < p_aug:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.85, 1.15))
    if random.random() < p_aug:
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.85, 1.15))
    if random.random() < p_aug:
        img = ImageEnhance.Color(img).enhance(random.uniform(0.85, 1.15))
    if random.random() < p_aug:
        img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.9, 1.1))
    if random.random() < p_aug:
        img = _adjust_hue(img, random.uniform(-0.06, 0.06) * 255.0)

    # Keep the (jittered) object, reset everything outside the mask to white.
    white = Image.new("RGB", img.size, (255, 255, 255))
    return Image.composite(img, white, m)
