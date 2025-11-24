from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import requests, os, random, re, json, datetime
from werkzeug.utils import secure_filename
from firebase_admin import auth, credentials, initialize_app
from usage_tracker import can_use_tool, record_usage, get_usage
from dotenv import load_dotenv  # ✅ Step 1: import dotenv

# -------------------
# Load environment variables
# -------------------
load_dotenv()  # ✅ Step 2: load .env file automatically

# -------------------
# App Configuration
# -------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
app.secret_key = "supersecretkey"

# ✅ Firebase Admin Setup
cred = credentials.Certificate("serviceAccountKey.json")
initialize_app(cred)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ✅ OpenRouter API Configuration (secured)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # read from .env
if not OPENROUTER_API_KEY:
    raise ValueError("Missing OPENROUTER_API_KEY. Add it in your .env file.")

BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_URL = f"{BASE_URL}/chat/completions"

# ✅ Updated working FREE model
MODEL = "deepseek/deepseek-r1-0528-qwen3-8b:free"





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
# 🔹 Generate Content
# -------------------
# -------------------
# 🔹 Generate Content (Updated with 5-uses-per-3-hour limit)
# -------------------
@app.route("/api/generate_content", methods=["POST"])
def generate_content():
    # Use guest user if no login
    uid = "guest_user"

    usage_info = get_usage(uid)
    now = datetime.datetime.now()
    reset_time = usage_info.get("reset_time")
    count = usage_info.get("count", 0)

    # Calculate reset logic (3-hour reset)
    if reset_time:
        reset_time = datetime.datetime.fromisoformat(reset_time)
        if now >= reset_time:
            # Reset usage after 3 hours
            usage_info["count"] = 0
            usage_info["reset_time"] = (now + datetime.timedelta(hours=3)).isoformat()
            count = 0
        else:
            # Still within cooldown
            time_left = reset_time - now
            seconds_left = int(time_left.total_seconds())
            hours = seconds_left // 3600
            minutes = (seconds_left % 3600) // 60
            seconds = seconds_left % 60
            time_text = f"{hours}h {minutes}m {seconds}s"

            if count >= 5:
                return jsonify({
                    "error": f"🚫 Usage limit reached. Please wait {time_text} for reset.",
                    "locked": True,
                    "reset_in": seconds_left
                }), 403
    else:
        usage_info["reset_time"] = (now + datetime.timedelta(hours=3)).isoformat()

    # If allowed, continue generation
    data = request.get_json()
    business = data.get("business", "").strip()
    content_type = data.get("content_type", "Caption")
    tone = data.get("tone", "Friendly")
    platform = data.get("platform", "Instagram")

    if not business:
        return jsonify({"error": "Please provide a business niche."}), 400

    prompt = f"""
    Create a {content_type} for a {business} business.
    Tone: {tone}
    Platform: {platform}.
    Requirements:
    - Make it engaging and suitable for {platform}.
    - Include hashtags if it's a caption.
    - Format clearly for copy-pasting.
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        result = response.json()

        if "choices" not in result or not result["choices"]:
            return jsonify({"error": "⚠️ No content generated."}), 500

        output_text = result["choices"][0]["message"]["content"]

        # Record usage + update next reset
        record_usage(uid)
        usage_info = get_usage(uid)

        return jsonify({
            "output": output_text,
            "usage": usage_info,
            "message": f"✅ Generation successful ({usage_info['count']}/5 used, resets in 3h)"
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"❌ API request failed: {str(e)}"}), 500

# 🔹 Analyze Image
# -------------------
@app.route("/api/analyze_image", methods=["POST"])
def analyze_image():
    # Try to verify user token
    uid = None
    token = request.headers.get("Authorization")
    if token:
        try:
            decoded = auth.verify_id_token(token)
            uid = decoded["uid"]
        except Exception:
            return jsonify({"error": "Invalid token"}), 401

    # If logged in, check usage limits
    if uid and not can_use_tool(uid):
        return jsonify({"error": "Usage limit reached. Try again later."}), 403

    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded."}), 400

        image = request.files["image"]
        caption = request.form.get("caption", "")
        platform = request.form.get("platform", "General")

        if image.filename == "":
            return jsonify({"error": "No file selected."}), 400

        filename = secure_filename(image.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(filepath)

        prompt = f"""
        Analyze this {platform} post image and caption.
        Caption: "{caption}"
        Provide:
        - Visual Appeal (%)
        - Emotional Tone (%)
        - Engagement Potential (%)
        - Branding Effectiveness (%)
        - 2-3 improvement suggestions.
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
            "HTTP-Referer": "https://crezia-ai.onrender.com",
            "X-Title": "Crezia AI"
        }

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }

        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()

        try:
            result = response.json()
        except json.JSONDecodeError:
            return jsonify({
                "error": f"❌ OpenRouter returned non-JSON: {response.text[:200]}"
            }), 500

        text = result["choices"][0]["message"]["content"]

        # Extract scores
        visual = int(re.search(r"Visual Appeal:\s*(\d+)", text).group(1)) if re.search(r"Visual Appeal:\s*(\d+)", text) else random.randint(60, 95)
        emotional = int(re.search(r"Emotional Tone:\s*(\d+)", text).group(1)) if re.search(r"Emotional Tone:\s*(\d+)", text) else random.randint(60, 95)
        engagement = int(re.search(r"Engagement Potential:\s*(\d+)", text).group(1)) if re.search(r"Engagement Potential:\s*(\d+)", text) else random.randint(60, 95)
        branding = int(re.search(r"Branding Effectiveness:\s*(\d+)", text).group(1)) if re.search(r"Branding Effectiveness:\s*(\d+)", text) else random.randint(60, 95)
        suggestions_match = re.search(r"Suggestions:(.*)", text, re.S)
        suggestions = suggestions_match.group(1).strip() if suggestions_match else "No suggestions provided."

        # Record usage only for logged-in users
        if uid:
            record_usage(uid)
            usage_info = get_usage(uid)
        else:
            usage_info = {"guest": True}

        return jsonify({
            "scores": {
                "visual": visual,
                "emotional": emotional,
                "engagement": engagement,
                "branding": branding,
                "suggestions": suggestions
            },
            "usage": usage_info
        })
    except Exception as e:
        return jsonify({"error": str(e)})
# -------------------
# 🔹 Get Current Usage (for dropdown)
# -------------------
@app.route("/api/usage")
def usage():
    uid, error_resp, status = verify_user_token()
    if error_resp:
        return error_resp, status

    usage_info = get_usage(uid)
    return jsonify(usage_info)

# -------------------
# 🧪 Test OpenRouter API (Quick Check)
# -------------------
@app.route("/test_api")
def test_api():
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Say hello from OpenRouter!"}],
        "max_tokens": 50
    }
    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)})

# -------------------
# Auth Pages
# -------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        try:
            user = auth.get_user_by_email(email)
            session["user"] = email
            return redirect(url_for("home"))
        except Exception:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("home"))

@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("profile.html", user=session["user"])

@app.route("/register")
def register():
    return render_template("register.html")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
