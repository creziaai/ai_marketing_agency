from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import requests, os, random, re, datetime
from werkzeug.utils import secure_filename
from firebase_admin import auth, credentials, initialize_app
from usage_tracker import can_use_tool, record_usage, get_usage
from dotenv import load_dotenv

# -------------------
# Load environment variables
# -------------------
load_dotenv()

# -------------------
# App Configuration
# -------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
app.secret_key = "supersecretkey"

# -------------------
# 🔒 STRONG CONTENT MODERATION (ALL-IN-ONE)
# -------------------
def is_restricted(text):
    if not text:
        return False

    text = text.lower()

    banned_keywords = [
        "sex", "porn", "pornography", "xxx", "nude", "nudity",
        "nsfw", "erotic", "explicit", "adult content",
        "18+", "sexual", "fetish", "onlyfans",
        "escort", "hookup", "intimate", "sensual"
    ]

    if any(word in text for word in banned_keywords):
        return True

    patterns = [
        r"s[e3]x",
        r"p[o0]rn",
        r"xxx+",
        r"18\+"
    ]

    for pattern in patterns:
        if re.search(pattern, text):
            return True

    return False


def block_if_restricted(*inputs):
    combined = " ".join([str(i) for i in inputs if i])

    if is_restricted(combined):
        return jsonify({
            "error": "🚫 This request cannot be processed as it may violate platform safety guidelines. Please try a different topic."
        }), 400

    return None


# -------------------
# Firebase
# -------------------
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------------------
# OpenRouter Config
# -------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("Missing OPENROUTER_API_KEY in .env file")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-chat"

# -------------------
# Pages
# -------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/analyzer")
def analyzer():
    return render_template("analyzer.html")

@app.route('/<path:path>')
def serve_static_file(path):
    return send_from_directory(app.static_folder, path)

# -------------------
# Generate Content
# -------------------
@app.route("/api/generate_content", methods=["POST"])
def generate_content():

    uid = "guest_user"
    usage_info = get_usage(uid)
    now = datetime.datetime.now()

    if usage_info.get("count", 0) >= 5:
        return jsonify({"error": "🚫 Usage limit reached"}), 403

    data = request.get_json()

    business = data.get("business", "")
    goal = data.get("goal", "")
    audience = data.get("audience", "")
    content_type = data.get("content_type", "")

    # 🔒 Moderation
    blocked = block_if_restricted(business, goal, audience, content_type)
    if blocked:
        return blocked

    prompt = f"""
You are an elite social media strategist.

STRICT RULE:
Do NOT generate any adult, NSFW, or explicit content.

Business: {business}
Goal: {goal}
Audience: {audience}

Generate:

<b>VIRAL HOOKS</b>
1.
2.
3.

<b>CAPTIONS</b>
Option 1:
Option 2:
Option 3:

<b>CALL TO ACTION</b>

<b>HASHTAGS</b>
Generate 15 hashtags.

<b>RECOMMENDATION</b>
Give one suggestion to improve performance.
"""

    response = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}]}
    )

    result = response.json()
    output = result["choices"][0]["message"]["content"]

    record_usage(uid)

    return jsonify({"output": output})


# -------------------
# Analyze Image
# -------------------
@app.route("/api/analyze_image", methods=["POST"])
def analyze_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        image = request.files["image"]
        caption = request.form.get("caption", "").strip()

if not caption:
    return jsonify({
        "error": "⚠️ Please enter a caption before analyzing the image."
    }), 400
        platform = request.form.get("platform", "Instagram")

        # 🔒 Moderation
        blocked = block_if_restricted(caption)
        if blocked:
            return blocked

        filename = secure_filename(image.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(filepath)

        prompt = f"""
You are a social media expert.

STRICT RULE:
Do NOT generate adult or explicit content.

Analyze this image for {platform}.

Caption: {caption}

Return:

1. Short description
2. Viral Hook
3. Caption
4. Call To Action
5. 10 Hashtags
6. Recommendation to improve engagement
"""

        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model": MODEL, "messages": [{"role": "user", "content": prompt}]}
        )

        result = response.json()
        analysis = result["choices"][0]["message"]["content"]

        return jsonify({
            "analysis": analysis,
            "scores": {
                "visual": random.randint(70, 95),
                "engagement": random.randint(70, 95),
                "branding": random.randint(70, 95)
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# -------------------
# Run
# -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
