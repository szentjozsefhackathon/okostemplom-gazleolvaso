import cv2
import numpy as np
import pytesseract

def fetch_image(rtsp_url):
    cap = cv2.VideoCapture(rtsp_url)
    ret, frame = cap.read()
    cap.release()
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame

def save_image(image, path):
    cv2.imwrite(path, image)

def apply_mask(image, mask):
    mask = cv2.imread(mask, cv2.IMREAD_GRAYSCALE)
    # The white areas of the mask are the areas we want to keep
    image[mask == 0] = 0
    image = image[20:90, 780:1050]
    return image

def transform_image(image, magic_number):
    # add treshold
    _, image = cv2.threshold(image, magic_number, 255, cv2.THRESH_BINARY)
    return image

def show_image(image):
    cv2.imshow("Image", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def split_image(image, width):
    # Split the image into 8 parts
    images = []
    for i in range(5):
        images.append(image[:, i*width:(i+1)*width])
        show_image(images[-1])
        print(detect_a_digit(images[-1]))
    return images

def detect_a_digit(image):
    return pytesseract.image_to_string(image, config="--psm 10 -c tessedit_char_whitelist=0123456789")

img = fetch_image("rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1")
img = apply_mask(img, "mask.png")
img = transform_image(img, 49)
imgs = split_image(img, 55)

save_image(img, "output.png")