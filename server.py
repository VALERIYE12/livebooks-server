from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import edge_tts, asyncio, io, os

app = Flask(__name__)
CORS(app)

PERSONAS = {
    "aria":   {"voices": ["en-US-AriaNeural", "en-US-JennyNeural", "en-US-EmmaNeural"]},
    "marcus": {"voices": ["en-US-GuyNeural", "en-US-BrianNeural", "en-US-ChristopherNeural"]},
    "elena":  {"voices": ["en-GB-SoniaNeural", "en-GB-LibbyNeural", "en-US-AriaNeural"]},
    "rael":   {"voices": ["en-US-RogerNeural", "en-US-EricNeural", "en-US-DavisNeural"]},
}

@app.route("/")
def root(): return jsonify({"ok": True, "service": "LiveBooks Voice Server"})

@app.route("/health")
def health(): return jsonify({"ok": True})

async def synthesize(text, voice, rate_pct, pitch_pct):
    c = edge_tts.Communicate(text, voice, rate=rate_pct, pitch=pitch_pct)
    buf = io.BytesIO()
    async for chunk in c.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()

async def synthesize_with_fallback(text, voices, rate_pct, pitch_pct):
    last_err = None
    for voice in voices:
        try:
            audio = await synthesize(text, voice, rate_pct, pitch_pct)
            if audio and len(audio) > 100:
                return audio, voice
        except Exception as e:
            last_err = e
            print(f"[VOICE FAILED] {voice}: {e}")
            continue
    raise last_err or Exception("All voices failed")

@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    persona = data.get("persona", "aria")
    rate = int(data.get("rate", 0))
    pitch = int(data.get("pitch", 0))
    if not text: return jsonify({"error": "No text"}), 400
    if persona not in PERSONAS: persona = "aria"
    voices = PERSONAS[persona]["voices"]
    rate_s = f"{'+' if rate >= 0 else ''}{rate}%"
    pitch_s = f"{'+' if pitch >= 0 else ''}{pitch}Hz"
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio, used = loop.run_until_complete(
            synthesize_with_fallback(text, voices, rate_s, pitch_s)
        )
        loop.close()
        resp = Response(audio, mimetype="audio/mpeg")
        resp.headers["X-Voice-Used"] = used
        return resp
    except Exception as e:
        print(f"[ERROR] {persona}: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    app.run(host="0.0.0.0", port=port, debug=False)
