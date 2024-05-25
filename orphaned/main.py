from orphaned.crop import CropOutNumbers
from orphaned.liveFeed import GetFeed
from orphaned.detect import detectNumbers
import cv2

feed = GetFeed("rtsp://szentjozsef:KonyorogjErtunk@10.5.10.39/stream1")

frame = feed.get_feed()
cropped = CropOutNumbers(frame, 105, 662, 150, 1054, 45, 15)

for i in range(8):
    print(detectNumbers(cropped.splitted[i]))

feed.close_feed()
cv2.destroyAllWindows()