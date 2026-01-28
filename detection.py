import cv2
import numpy as np
import pytesseract
import imutils

RTSP_URL = "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1"
MASK_PATH = "mask.png"
OUTPUT_PATH = "output.png"
MAGIC_NUMBER = 65
SPLIT_WIDTH = 48

# Rotation angle and ROI bounds (y_start:y_end, x_start:x_end)
ANGLE = -3
ROI_Y_START = 450
ROI_Y_END = 500
ROI_X_START = 647
ROI_X_END = 887

# Fetches an image from the given RTSP URL and returns it as a grayscale image.
def fetch_image(rtsp_url):
    try:
        cap = cv2.VideoCapture(rtsp_url)
        _, frame = cap.read()
        cap.release()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return gray
    except Exception as e:
        print(e)
        return None

# Saves the given image to the specified path.
def save_image(image, path):
    cv2.imwrite(path, image)

# Applies a mask to the given image and returns the masked image.
def apply_mask(image, mask_path, roi=None):
    # mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    # image[mask == 0] = 0
    image = imutils.rotate(image, angle=ANGLE)

    # roi can be a tuple/list: (y_start, y_end, x_start, x_end)
    if roi is None:
        y1, y2, x1, x2 = ROI_Y_START, ROI_Y_END, ROI_X_START, ROI_X_END
    else:
        try:
            y1, y2, x1, x2 = roi
        except Exception:
            # invalid roi, fall back to defaults
            y1, y2, x1, x2 = ROI_Y_START, ROI_Y_END, ROI_X_START, ROI_X_END

    # Ensure indices are within image bounds
    h, w = image.shape[:2]
    y1 = max(0, min(y1, h))
    y2 = max(0, min(y2, h))
    x1 = max(0, min(x1, w))
    x2 = max(0, min(x2, w))

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
def detection(rtsp_url=RTSP_URL, roi=None, save_prefix=None):
    """Run detection for a given RTSP URL and optional ROI.
    - rtsp_url: RTSP string to fetch the image from
    - roi: tuple (y_start, y_end, x_start, x_end) or None to use defaults
    - save_prefix: optional prefix for saved snapshot/processed filenames
    Returns a list of 5 detected characters (strings).
    """
    img = fetch_image(rtsp_url)
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
