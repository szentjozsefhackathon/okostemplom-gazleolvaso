from detection import detection
from flask import Flask, render_template

app = Flask(__name__)

last_result = ['?'] * 5

@app.route('/')
def result():
    result = detection()

    for idx, c in enumerate(result):
        if c != '?': last_result[idx] = c
        else: result[idx] = last_result[idx]
    result = ''.join(result)
    print(result)

    return render_template('index.html', number=result)

if __name__ == '__main__':
    app.run()
