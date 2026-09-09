Python
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "<h1>Nova AI - Site Online</h1><p>Flask backend is working!</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
