# Given a picture, write a function which returns a number which is written on that picture
import cv2
import numpy as np
import pytesseract

def detectNumbers(picture, width):
    # Convert the image to grayscale
    gray = cv2.cvtColor(picture, cv2.COLOR_BGR2GRAY)
    # Apply GaussianBlur to the image
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    # Apply thresholding to the image
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    # Find contours in the image
    contours = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = contours[0] if len(contours) == 2 else contours[1]
    # Create a copy of the image
    result = picture.copy()
    # Iterate through the contours
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Filter out small contours
        if w < 10 or h < 10:
            continue
        # Draw rectangle around contour on original image
        cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 0), 2)
        # Crop the image
        ROI = picture[y:y+h, x:x+w]
        # OCR
        data = pytesseract.image_to_string(ROI, lang='osd', config='--psm 6 outputbase digits')
    # Display the result
    cv2.imshow('thresh', thresh)
    cv2.imshow('result', result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    return data