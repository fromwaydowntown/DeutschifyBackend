from flask import Flask
import logging

app = Flask(__name__)

@app.route('/')
def health():
    return 'OK', 200

def run_health_server():
    app.run(host='0.0.0.0', port=8080)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_health_server()