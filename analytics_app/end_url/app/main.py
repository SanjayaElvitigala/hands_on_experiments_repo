import os
from flask import Flask, jsonify, request, abort
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi

from discord_interactions import verify_key_decorator
from dotenv import load_dotenv

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app)

load_dotenv()
DISCORD_PUBLIC_KEY = os.getenv("DISCORD_PUBLIC_KEY")

@app.route("/interactions", methods=["POST"])
async def interactions():
    print(f"👉 Request: {request.json}")
    raw_request = request.json
    return interact(raw_request)

@verify_key_decorator(DISCORD_PUBLIC_KEY)
def interact(raw_request):

    if raw_request["type"] == 1:  # PING
        print("BLOCK 1 : ____", raw_request)
        response_data = {"type": 1}  # PONG
    else:
        print("BLOCK 2 : ____", raw_request)
        data = raw_request["data"]
        command_name = data["last_month"]
        message_content = "Hello there!"

        response_data = {
            "type": 4,
            "data": {"content": message_content},
        }

    return jsonify(response_data)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)