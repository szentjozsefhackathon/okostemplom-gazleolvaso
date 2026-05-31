import cv2
import numpy as np
import pytesseract
import imutils

RTSP_URL = "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1"
MASK_PATH = "mask.png"
OUTPUT_PATH = "output.png"
MAGIC_NUMBER = 65
SPLIT_WIDTH = 48

# Rotation angle and ROI bounds (y_start:y_end, x_start:x_end) - defaults can be overridden from settings
ANGLE = -2
ROI_Y_START = 560 # magasság
ROI_Y_END = 600
ROI_X_START = 762 # szélesség
ROI_X_END = 1005

# Settings variables (can be updated from Home Assistant config)
_current_angle = ANGLE
_current_roi = (ROI_Y_START, ROI_Y_END, ROI_X_START, ROI_X_END)

def set_settings(angle=None, roi_y_start=None, roi_y_end=None, x_start=None, x_end=None, rtsp_url=None):
    """Update settings from Home Assistant configuration"""
    global _current_angle, _current_roi
    if angle is not None:
        _current_angle = angle
    if roi_y_start is not None or roi_y_end is not None or x_start is not None or x_end is not None:
        y_start = roi_y_start if roi_y_start is not None else _current_roi[0]
        y_end = roi_y_end if roi_y_end is not None else _current_roi[1]
        x_s = x_start if x_start is not None else _current_roi[2]
        x_e = x_end if x_end is not None else _current_roi[3]
        _current_roi = (y_start, y_end, x_s, x_e)

# Fetches an image from the given RTSP URL and returns it.
# If grayscale=True, returns grayscale image; otherwise returns BGR color image.
def fetch_image(rtsp_url, grayscale=True):
    try:
        cap = cv2.VideoCapture(rtsp_url)
        _, frame = cap.read()
        cap.release()
        if frame is None:
            print(f"Failed to fetch frame from {rtsp_url}")
            return None
        if grayscale:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return gray
        else:
            return frame  # Returns BGR color image
    except Exception as e:
        print(f"Error fetching image from {rtsp_url}: {e}")
        return None

# Saves the given image to the specified path.
def save_image(image, path):
    cv2.imwrite(path, image)

# Applies a mask to the given image and returns the masked image.
def apply_mask(image, mask_path, roi=None, angle=None):
     # mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
     # image[mask == 0] = 0
     
     # Use provided angle or current settings angle
     rotation_angle = angle if angle is not None else _current_angle
     image = imutils.rotate(image, angle=rotation_angle)

     # roi can be a tuple/list: (y_start, y_end, x_start, x_end)
     if roi is None:
         y1, y2, x1, x2 = _current_roi
     else:
         try:
             y1, y2, x1, x2 = roi
         except Exception:
             # invalid roi, fall back to current settings
             y1, y2, x1, x2 = _current_roi

     # Ensure indices are within image bounds
     h, w = image.shape[:2]
     y1 = max(0, min(y1, h))
     y2 = max(0, min(y2, h))
     x1 = max(0, min(x1, w))
     x2 = max(0, min(x2, w))

     print(f"apply_mask - y1: {y1}, y2: {y2}, x1: {x1}, x2: {x2}, angle: {rotation_angle}")

     roi_img = image[y1:y2, x1:x2]
     return roi_img

# Transforms the given image using the specified threshold and returns the transformed image.
def transform_image(image, threshold):
    _, transformed_image = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(transformed_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(transformed_image, contours, -1, 255, 1)
    kernel = np.ones((2, 2), np.uint8)
    erode = cv2.erode(transformed_image, kernel, iterations=1)
    return erode

# Splits the given image into segments of the specified width and returns a list of detected segments.
def split_image(image, width):
    print("nos:")
    sth = pytesseract.image_to_string(image, config="--psm 12 -c tessedit_char_whitelist=0123456789")
    print(sth)

    images = [image[:, i*width:(i+1)*width] for i in range(5)]
    result = [detect_digit(img) or "?" for img in images]
    return result

# Detects a digit in the given image and returns it as a string.
def detect_digit(image):
    digit = pytesseract.image_to_string(image, config="--psm 10 -c tessedit_char_whitelist=0123456789")
    return digit

# Main function to fetch, process, and save an image, and return detected digits
def detection(rtsp_url=None, roi=None, save_prefix=None):
    """Run detection for a given RTSP URL and optional ROI.
    - rtsp_url: RTSP string to fetch the image from (uses RTSP_URL if None)
    - roi: tuple (y_start, y_end, x_start, x_end) or None to use defaults
    - save_prefix: optional prefix for saved snapshot/processed filenames
    Returns a list of 5 detected characters (strings).
    """
    if rtsp_url is None:
        rtsp_url = RTSP_URL
    
    # Fetch grayscale image for detection
    img = fetch_image(rtsp_url, grayscale=True)
    if img is None:
        return ['!'] * 5

    if save_prefix:
        save_image(img, f"/media/{save_prefix}_snapshot.png")
    else:
        save_image(img, "/media/snapshot.png")

    img = apply_mask(img, MASK_PATH, roi=roi)
    img = transform_image(img, MAGIC_NUMBER)

    if save_prefix:
        save_image(img, f"/media/{save_prefix}_processed.png")
    else:
        save_image(img, "/media/processed.png")

    digits = split_image(img, SPLIT_WIDTH)
    digits = [c[0] for c in digits]

    return digits
