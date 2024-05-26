import cv2
import numpy as np
import pytesseract

RTSP_URL = "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1"
MASK_PATH = "mask.png"
OUTPUT_PATH = "output.png"
MAGIC_NUMBER = 43
SPLIT_WIDTH = 55

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
def apply_mask(image, mask_path):
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    image[mask == 0] = 0
    roi = image[20:90, 780:1050]
    return roi

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
    images = [image[:, i*width:(i+1)*width] for i in range(5)]
    result = [detect_digit(img) or "?" for img in images]
    return result

# Detects a digit in the given image and returns it as a string.
def detect_digit(image):
    digit = pytesseract.image_to_string(image, config="--psm 10 -c tessedit_char_whitelist=0123456789")
    return digit

# Main function to fetch, process, and save an image, and return detected digits
def detection():
    img = fetch_image(RTSP_URL)
    if img is None:
        return ['!'] * 5
    img = apply_mask(img, MASK_PATH)
    img = transform_image(img, MAGIC_NUMBER)
    save_image(img, OUTPUT_PATH)

    digits = split_image(img, SPLIT_WIDTH)
    digits = [c[0] for c in digits]

    return digits
