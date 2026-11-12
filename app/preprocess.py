"""Image restoration: CLAHE, Sauvola binarization (integral images), deskew."""
import cv2
import numpy as np


def sauvola(gray: np.ndarray, window: int = 31, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """Sauvola local thresholding using summed-area (integral) images.

    T(x, y) = m(x, y) * (1 + k * (s(x, y) / R - 1)), where m and s are the mean
    and standard deviation in a window around the pixel. Local thresholds cope
    with uneven ink fading and stains better than one global threshold.
    """
    if window % 2 == 0:
        window += 1
    g = gray.astype(np.float64)
    pad = window // 2
    gp = cv2.copyMakeBorder(g, pad, pad, pad, pad, cv2.BORDER_REFLECT)
    s1, s2 = cv2.integral2(gp)
    h, w = g.shape
    n = window * window

    def win(a):
        return a[window:window + h, window:window + w] - a[0:h, window:window + w] \
            - a[window:window + h, 0:w] + a[0:h, 0:w]

    mean = win(s1) / n
    var = np.maximum(win(s2) / n - mean ** 2, 0)
    std = np.sqrt(var)
    thresh = mean * (1 + k * (std / r - 1))
    return np.where(g > thresh, 255, 0).astype(np.uint8)


def estimate_skew(binary: np.ndarray, max_angle: float = 6.0, step: float = 0.25) -> float:
    """Skew angle in degrees (positive = text rotated counter-clockwise).

    Projection-profile search: the correct angle maximizes the variance of the
    row sums, because text lines then align with image rows.
    """
    scale = 700.0 / max(binary.shape[1], 1)
    small = cv2.resize(255 - binary, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = small.shape
    centre = (w / 2, h / 2)
    best_angle, best_score = 0.0, -1.0
    for a in np.arange(-max_angle, max_angle + step, step):
        m = cv2.getRotationMatrix2D(centre, float(a), 1.0)
        rot = cv2.warpAffine(small, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        score = float(np.var(rot.sum(axis=1)))
        if score > best_score:
            best_angle, best_score = float(a), score
    return best_angle


def rotate(img: np.ndarray, angle: float, border) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def remove_rulings(binary: np.ndarray, min_len: int = 70):
    """Erase long horizontal/vertical table rules so OCR sees text, not grid lines.

    Rules are found by morphological opening with long 1-pixel kernels. Text
    strokes are far shorter than min_len, so they survive. Returns the cleaned
    binary image and the fraction of ink pixels removed.
    """
    ink = 255 - binary
    horiz = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (min_len, 1)))
    vert = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, min_len)))
    lines = cv2.dilate(cv2.bitwise_or(horiz, vert), np.ones((3, 3), np.uint8))
    total = max(int((ink > 0).sum()), 1)
    cleaned = ink.copy()
    cleaned[lines > 0] = 0
    removed = float(((ink > 0) & (lines > 0)).sum()) / total
    return 255 - cleaned, removed


def preprocess(bgr: np.ndarray, min_width: int = 1400):
    """Return (processed_binary_bgr, deskewed_original_bgr, metrics)."""
    h, w = bgr.shape[:2]
    if w < min_width:
        f = min_width / w
        bgr = cv2.resize(bgr, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    background = cv2.medianBlur(gray, 3)
    contrast = float(gray.std())
    noise = float(np.abs(gray.astype(np.float32) - background.astype(np.float32)).mean())

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)
    binary = sauvola(enhanced, window=31, k=0.2)

    angle = estimate_skew(binary)
    if abs(angle) >= 0.2:
        binary = rotate(binary, angle, 255)
        bgr = rotate(bgr, angle, (255, 255, 255))

    binary, ruling_share = remove_rulings(binary)

    # light speckle removal (opening on the ink mask)
    ink = 255 - binary
    ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    binary = 255 - ink

    metrics = {
        "ruling_ink_removed": round(ruling_share, 3),
        "width": int(bgr.shape[1]),
        "height": int(bgr.shape[0]),
        "skew_deg": round(angle, 2),
        "contrast_std": round(contrast, 1),
        "noise_level": round(noise, 2),
    }
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR), bgr, metrics
