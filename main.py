from crop import CropOutNumbers
from liveFeed import GetFeed
from detect import detectNumbers
import cv2

feed = GetFeed("rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1")

frame = feed.get_feed()
cropped = CropOutNumbers(frame, 105, 662, 150, 1054, 45, 15)
cropped.show_img()
for i in range(8):
    print(detectNumbers(cropped.splitted[i], 512))

feed.close_feed()
cv2.destroyAllWindows()