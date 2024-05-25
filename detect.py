import easyocr
import cv2
import numpy as np
 
def detectNumbers(img, resize_w):
    #resize
    h, w = img.shape[:2]
    ratio = h/w
    img = cv2.resize(img, (resize_w, round(resize_w * ratio)))
 
    # b&w
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
 
    # blur & threshold
    img = cv2.medianBlur(img, 5)
    img = cv2.adaptiveThreshold(img, 199, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY, 199, 5)
 
    reader = easyocr.Reader(['en'])
    result = reader.readtext(img, allowlist='0123456789')
 
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    t = ""
    for (bbox, text, prob) in result:
        t += "".join([c if ord(c) < 128 else "" for c in text]).strip()
    return t