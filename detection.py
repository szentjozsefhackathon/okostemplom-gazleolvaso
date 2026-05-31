import cv2
import numpy as np
import pytesseract
import imutils
import os

MASK_PATH = "mask.png"
MAGIC_NUMBER = 65

# Default fallback values (used only when a config key is missing)
_DEFAULTS = {
    'rtsp_url': '',
    'angle': 0,
    'roi_y_start': 0,
    'roi_y_end': 100,
    'x_start': 0,
    'x_end': 100,
    'num_segments': 5,
}


def fetch_image(rtsp_url: str, grayscale: bool = True):
    """Fetch a single frame from an RTSP stream.
    Returns a numpy image or None on failure.
    grayscale=True  → returns single-channel gray image
    grayscale=False → returns BGR color image
    """
    try:
        cap = cv2.VideoCapture(rtsp_url)
        _, frame = cap.read()
        cap.release()
        if frame is None:
            print(f"[detection] Failed to fetch frame from {rtsp_url}")
            return None
        if grayscale:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame
    except Exception as e:
        print(f"[detection] Error fetching image from {rtsp_url}: {e}")
        return None


def save_image(image, path: str):
    """Save a numpy image to the given path, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    cv2.imwrite(path, image)


def apply_roi(image, angle: float, roi_y_start: int, roi_y_end: int,
              x_start: int, x_end: int):
    """Rotate the image by *angle* degrees and crop to the ROI rectangle.
    Returns the cropped region.
    """
    image = imutils.rotate(image, angle=angle)

    h, w = image.shape[:2]
    y1 = max(0, min(roi_y_start, h))
    y2 = max(0, min(roi_y_end, h))
    x1 = max(0, min(x_start, w))
    x2 = max(0, min(x_end, w))

    print(f"[detection] apply_roi y1={y1} y2={y2} x1={x1} x2={x2} angle={angle}")
    return image[y1:y2, x1:x2]


def transform_image(image):
    """Threshold + morphological cleanup for digit recognition."""
    _, thresh = cv2.threshold(image, MAGIC_NUMBER, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(thresh, contours, -1, 255, 1)
    kernel = np.ones((2, 2), np.uint8)
    return cv2.erode(thresh, kernel, iterations=1)


def detect_digit(image) -> str:
    """Run Tesseract on a single digit strip and return the best character."""
    return pytesseract.image_to_string(
        image, config="--psm 10 -c tessedit_char_whitelist=0123456789"
    )


def split_and_detect(image, num_segments: int):
    """Split the ROI horizontally into *num_segments* equal strips and OCR each."""
    print("[detection] full-row OCR attempt:")
    print(pytesseract.image_to_string(
        image, config="--psm 12 -c tessedit_char_whitelist=0123456789"
    ))

    img_width = image.shape[1]
    width = img_width // num_segments
    strips = [image[:, i * width:(i + 1) * width] for i in range(num_segments)]
    result = [detect_digit(s) or "?" for s in strips]
    # Take only the first character from each OCR result
    result = [c[0] if c and c[0] != '\n' else '?' for c in result]
    return result


def detection(reader_id: str, config: dict) -> list:
    """Run the full detection pipeline for one reader.

    Parameters
    ----------
    reader_id : str
        Unique identifier used for output file names.
    config : dict
        Must contain: rtsp_url, angle, roi_y_start, roi_y_end, x_start, x_end, num_segments.
        Missing keys fall back to _DEFAULTS.

    Returns
    -------
    list of str
        Detected characters, one per segment. '!' means capture failure, '?' means OCR failure.
    """
    cfg = {**_DEFAULTS, **config}

    rtsp_url: str = cfg['rtsp_url']
    angle: float = float(cfg['angle'])
    roi_y_start: int = int(cfg['roi_y_start'])
    roi_y_end: int = int(cfg['roi_y_end'])
    x_start: int = int(cfg['x_start'])
    x_end: int = int(cfg['x_end'])
    num_segments: int = max(1, int(cfg['num_segments']))

    # --- Fetch ---
    img = fetch_image(rtsp_url, grayscale=True)
    if img is None:
        return ['!'] * num_segments

    # --- Save snapshot ---
    snapshot_path = f"/media/{reader_id}_snapshot.png"
    save_image(img, snapshot_path)

    # --- ROI crop ---
    img = apply_roi(img, angle, roi_y_start, roi_y_end, x_start, x_end)

    # --- Transform ---
    img = transform_image(img)

    # --- Save processed ---
    processed_path = f"/media/{reader_id}_processed.png"
    save_image(img, processed_path)

    # --- OCR ---
    digits = split_and_detect(img, num_segments)

    # --- Save text result ---
    result_str = ''.join(digits)
    result_path = f"/media/{reader_id}_result.txt"
    try:
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(result_str + '\n')
    except Exception as e:
        print(f"[detection] Failed to write result file {result_path}: {e}")

    print(f"[detection] reader={reader_id} result={result_str}")
    return digits
