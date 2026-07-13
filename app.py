from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)
API_KEY = os.environ.get("TERMII_KEY") # Mun ɓoye shi

@app.route("/api/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    data["api_key"] = API_KEY
    r = requests.post("https://api.ng.termii.com/api/sms/otp/send", json=data)
    return jsonify(r.json())

@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    data["api_key"] = API_KEY
    r = requests.post("https://api.ng.termii.com/api/sms/otp/verify", json=data)
    return jsonify(r.json())

if __name__ == "__main__":
    app.run()