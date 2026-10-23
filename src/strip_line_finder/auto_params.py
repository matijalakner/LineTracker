"""Choose detection parameters from the lightness and contrast of an image.

Measurements (both on a 0-255 scale, using the channel-mean luminance that the
line detector itself works with):

    lightness L = mean luminance of the image
    contrast  C = P95 - P5 of the luminance (robust to a few hot/dead pixels)

Formulas (REF = 128 is the "mid" level the default parameters were tuned for):

    min_contrast   = 7.0 * sqrt(C / REF) * sqrt(L / REF)      clipped to [3, 20]
    min_brightness = 0.2 * L                                  clipped to [5, 60]

At L = C = 128 these give 7.0 and 25.6, i.e. the library defaults. The
constants below are starting points and can be tuned for your footage.
"""
import numpy as np

REF_LEVEL = 128.0

BASE_MIN_CONTRAST = 7.0
MIN_CONTRAST_RANGE = (3.0, 20.0)

BRIGHTNESS_FRACTION = 0.2
MIN_BRIGHTNESS_RANGE = (5.0, 60.0)


def measure_image(img):
    """Return (lightness, contrast) of an HxWx3 or HxW array with values 0-255.

    Works for RGB or BGR, because the luminance is the plain channel mean.
    """
    arr = np.asarray(img, dtype=np.float32)
    lum = arr.mean(axis=2) if arr.ndim == 3 else arr
    lum = lum[::4, ::4]  # subsample: plenty for global statistics, much faster
    lightness = float(lum.mean())
    p5, p95 = np.percentile(lum, [5, 95])
    contrast = float(p95 - p5)
    return lightness, contrast


def auto_parameters(img):
    """Return (params, measurements) for an image.

    params        -> {"min_contrast": ..., "min_brightness": ...}
    measurements  -> {"lightness": ..., "contrast": ...}
    """
    lightness, contrast = measure_image(img)
    c = max(contrast, 1.0)
    l = max(lightness, 1.0)

    min_contrast = BASE_MIN_CONTRAST * np.sqrt(c / REF_LEVEL) * np.sqrt(l / REF_LEVEL)
    min_contrast = float(np.clip(min_contrast, *MIN_CONTRAST_RANGE))

    min_brightness = float(np.clip(BRIGHTNESS_FRACTION * lightness, *MIN_BRIGHTNESS_RANGE))

    params = {
        "min_contrast": round(min_contrast, 2),
        "min_brightness": round(min_brightness, 2),
    }
    measurements = {
        "lightness": round(lightness, 2),
        "contrast": round(contrast, 2),
    }
    return params, measurements