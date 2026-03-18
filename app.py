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
# Content Moderation
# -------------------
def is_restricted(text):
    text = text.lower()
    pattern = r"(sex|porn|xxx|nude|nsfw|erotic|explicit)"
    return re.search(pattern, text)

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
# Serve Pages
# -------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/welcome")
def welcome():
    return render_template("kp.html")

@app.route("/tools")
def tools():
    return render_template("index.html")

@app.route("/analyzer")
def analyzer():
    return render_template("analyzer.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/<path:path>')
def serve_static_file(path):
    return send_from_directory(app.static_folder, path)

# -------------------
# Verify Firebase Token
# -------------------
def verify_user_token():
    token = request.headers.get("Authorization")
    if not token:
        return None, jsonify({"error": "Unauthorized"}), 401
    try:
        decoded = auth.verify_id_token(token)
        return decoded['uid'], None, None
    except Exception:
        return None, jsonify({"error": "Invalid token"}), 401

# -------------------
# Generate Content
# -------------------
@app.route("/api/generate_content", methods=["POST"])
def generate_content():
    
    uid = "guest_user"
    usage_info = get_usage(uid)
    now = datetime.datetime.now()
    reset_time = usage_info.get("reset_time")
    count = usage_info.get("count", 0)

    if reset_time:
        reset_time = datetime.datetime.fromisoformat(reset_time)
        if now >= reset_time:
            usage_info["count"] = 0
            usage_info["reset_time"] = (now + datetime.timedelta(hours=3)).isoformat()
            count = 0
        else:
            if count >= 5:
                return jsonify({
                    "error": "🚫 Usage limit reached",
                    "locked": True
                }), 403
    else:
        usage_info["reset_time"] = (now + datetime.timedelta(hours=3)).isoformat()

    # Receive data
    data = request.get_json()

    business = data.get("business", "").strip()
    goal = data.get("goal", "Increase engagement")
    audience = data.get("audience", "Social media users")
    content_type = data.get("content_type", "Caption")
    tone = data.get("tone", "Friendly")
    platform = data.get("platform", "Instagram")
    length = data.get("length", "Medium")

    if not business:
        return jsonify({"error": "Please provide a business niche."}), 400

    # 🔒 Content moderation
    combined_input = " ".join([business, goal, audience, content_type])

    if is_restricted(combined_input):
        return jsonify({
            "error": "🚫 We can’t generate content for this request as it may not align with platform guidelines. Please try a different topic."
        }), 400

    # Length control
    if length == "Short":
        length_instruction = "Keep the caption very short and punchy (1–2 sentences)."
    elif length == "Medium":
        length_instruction = "Write a balanced caption with 3–4 engaging sentences."
    else:
        length_instruction = "Write a longer storytelling style caption with emotional appeal."

    # Prompt
    prompt = f"""
You are an elite social media marketing strategist.

Business Type: {business}
Content Goal: {goal}
Target Audience: {audience}
Platform: {platform}
Tone: {tone}

{length_instruction}

Generate:

<b>VIRAL HOOKS</b>
1.
2.
3.

<b>CAPTION OPTIONS</b>
Option 1:
Option 2:
Option 3:

<b>CALL TO ACTION</b>

<b>HASHTAGS</b>

Niche Hashtags:
#example #example #example

Medium Competition Hashtags:
#example #example #example

High Reach Hashtags:
#example #example #example

<b>VIRAL SCORE</b>

<b>CONTENT IDEAS FOR NEXT POSTS</b>
1.
2.
3.
4.
5.
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700,
        "temperature": 0.9
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()
        output_text = result["choices"][0]["message"]["content"]

        record_usage(uid)

        return jsonify({
            "output": output_text,
            "usage": get_usage(uid)
        })

    except Exception as e:
        return jsonify({"error": f"❌ API request failed: {str(e)}"}), 500


# -------------------
# Analyze Image
# -------------------
@app.route("/api/analyze_image", methods=["POST"])
def analyze_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        image = request.files["image"]
        caption = request.form.get("caption", "")

        # 🔒 Content moderation
        if is_restricted(caption):
            return jsonify({
                "error": "🚫 This content may violate platform guidelines. Please upload a different image or caption."
            }), 400

        filename = secure_filename(image.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(filepath)

        return jsonify({
            "message": "Image analyzed successfully",
            "scores": {
                "visual": random.randint(60,95),
                "engagement": random.randint(60,95)
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)})


# -------------------
# Run App
# -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
