import os
from flask import Flask, jsonify, request, abort
from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi
from discord_interactions import verify_key_decorator
from dotenv import load_dotenv
from typing import Final
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


app = Flask(__name__)
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app)


load_dotenv()
DISCORD_PUBLIC_KEY: Final[str] = os.getenv("DISCORD_PUBLIC_KEY")


@app.route("/interactions", methods=["POST"])
async def interactions():
    # print(f"👉 Request: {request.json}")
    raw_request = request.json
    return interact(raw_request)


def verify_request():
    print("\n CALLING VERIFY REQ FUNC")
    verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))

    signature = request.headers["X-Signature-Ed25519"]
    timestamp = request.headers["X-Signature-Timestamp"]

    print("REQUEST_HEADERS: ", request.headers)
    body = request.data.decode("utf-8")

    try:
        print("VERIFY BLOCK 1")
        result = verify_key.verify(
            f"{timestamp}{body}".encode(), bytes.fromhex(signature)
        )
        print("RESULT: ", result)
        return result
    except BadSignatureError as e:
        print("ERROR: _____", e)
        return abort(401, "invalid request signature")


@verify_key_decorator(DISCORD_PUBLIC_KEY)
def interact(raw_request):

    if raw_request["type"] == 1:  # PING
        print("BLOCK 1 : ____", raw_request)
        response_data = {"type": 1}  # PONG
        return jsonify(response_data)
    else:
        print("BLOCK 2 : ____")
    #     print("BLOCK 2 : ____", raw_request)

    # return jsonify(response_data)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
