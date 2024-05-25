import cv2

class GetFeed:
    def __init__(self, source):
        self.cap = cv2.VideoCapture(source)

    def get_feed(self):
        while(self.cap.isOpened()):
            ret, frame = self.cap.read()
            if not ret:
                break
            else:
                return frame
            
    def close_feed(self):
        self.cap.release()
        cv2.destroyAllWindows()