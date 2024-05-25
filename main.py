from detection import detection
from time import sleep

while True:
    datas = detection()
    print(datas)
    sleep(1)