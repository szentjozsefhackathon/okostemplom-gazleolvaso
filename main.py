from detection import detection
from time import sleep
from datetime import datetime

while True:
    datas = detection()
    print(f"{datetime.now()}: {datas}")
    sleep(1)