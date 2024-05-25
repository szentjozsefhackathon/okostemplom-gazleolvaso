import cv2
import pytesseract

RTSP = "rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1"

def get_feed():
    cap = cv2.VideoCapture(RTSP)
    ret, frame = cap.read()
    cap.release()
    return frame

def apply_mask(path, image):
    mask = cv2.imread(path, 0)
    masked = cv2.bitwise_and(image, image, mask=mask)
    return masked

def detect_numbers(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    custom_config = r'--oem 3 --psm 6 outputbase digits'
    details = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, config=custom_config)
    text = details['text']
    digits = [char for char in text if char.isdigit()]
    return digits

image = get_feed()
cv2.imshow("Original", image)
cv2.waitKey(0)
cv2.destroyAllWindows()