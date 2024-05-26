from collections import deque
from statistics import mode
from detection import detection
from time import sleep

x = deque(maxlen=50)

while True:
    x.append(detection())
    most_common = [mode([i[j] for i in x]) for j in range(len(x[0]))]
    print(f"The most common element is: {most_common} Latest: {x[-1]}")
    sleep(1)