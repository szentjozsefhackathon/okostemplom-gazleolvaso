from collections import deque
from statistics import mode
from detection import detection
from time import sleep
from pathlib import Path

def update_gas_value(value: str, file_path="/media/gas_value.txt"):
    if len(value) != 5:
        raise ValueError("value must be exactly 5 characters long")

    path = Path(file_path)

    # Read existing value
    if path.exists():
        old = path.read_text().strip()
        if len(old) != 5:
            old = "00000"
    else:
        old = "00000"

    # Merge character by character
    new = []
    for v_char, o_char in zip(value, old):
        if v_char.isdigit():
            new.append(v_char)
        else:
            new.append(o_char)

    new_value = "".join(new)

    # Write back
    path.write_text(new_value)

    print(new_value)

    return new_value




x = deque(maxlen=50)

while True:
    x.append(detection())
    most_common = [mode([i[j] for i in x]) for j in range(len(x[0]))]

    print(f"Status: {most_common} ")
    print(f"({x[-1]})")

    value = ''.join(str(d) for d in most_common)
    update_gas_value(value)

    sleep(4)



