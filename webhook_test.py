from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    print("Headers:", dict(request.headers))
    print("Raw data:", request.data)
    print("JSON:", request.json)
    return '', 200

if __name__ == '__main__':
    app.run(port=5001)