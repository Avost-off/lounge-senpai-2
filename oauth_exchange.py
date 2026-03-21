import os
import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")


@app.route("/healthz")
def healthz():
    return {"ok": True}, 200


@app.route("/oauth-exchange", methods=["POST"])
def oauth_exchange():
    if not CLIENT_ID or not CLIENT_SECRET:
        return jsonify({"error": "OAuth non configure sur le service OAuth"}), 500

    body = request.get_json(silent=True) or {}
    code = body.get("code")
    redirect_uri = body.get("redirect_uri")

    if not code or not redirect_uri:
        return jsonify({"error": "code ou redirect_uri manquant"}), 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    try:
        resp = requests.post(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers=headers,
            timeout=20,
        )
        return (resp.text, resp.status_code, {"Content-Type": "application/json"})
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
