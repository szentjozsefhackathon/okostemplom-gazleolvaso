import cv2
import pytesseract
from pytesseract import Output
    
def detectNumbers(image):
    # Convert to grayscale
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply some preprocessing
    # E.g., Gaussian Blur to remove noise, then thresholding
    # blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    # _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Use Tesseract to detect digits
    custom_config = r'--oem 3 --psm 6 outputbase digits'
    details = pytesseract.image_to_data(image, output_type=Output.DICT, config=custom_config)

    # Extract the detected text
    text = details['text']
    digits = [char for char in text if char.isdigit()]

    cv2.imshow("Threshold", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    return digits