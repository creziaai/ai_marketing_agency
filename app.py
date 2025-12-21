from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import requests, os, random, re, json, datetime
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

# Firebase
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
MODEL = "meta-llama/llama-3.3-70b-instruct:free"


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
    Include hashtags if it's a caption.
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

        output_text = result["choices"][0]["message"]["content"]

        record_usage(uid)
        usage_info = get_usage(uid)

        return jsonify({
            "output": output_text,
            "usage": usage_info
        })

    except Exception as e:
        return jsonify({"error": f"❌ API request failed: {str(e)}"}), 500


# -------------------
# Analyze Image
# -------------------
@app.route("/api/analyze_image", methods=["POST"])
def analyze_image():
    uid = None
    token = request.headers.get("Authorization")

    if token:
        try:
            decoded = auth.verify_id_token(token)
            uid = decoded["uid"]
        except Exception:
            return jsonify({"error": "Invalid token"}), 401

    if uid and not can_use_tool(uid):
        return jsonify({"error": "Usage limit reached"}), 403

    try:
        if "image" not in request.files:
            return jsonify({"error": "No image uploaded"}), 400

        image = request.files["image"]
        caption = request.form.get("caption", "")
        platform = request.form.get("platform", "General")

        filename = secure_filename(image.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        image.save(filepath)

        prompt = f"""
        Analyze this image for {platform}.
        Caption: "{caption}"
        """

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400
        }

        response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
        result = response.json()

        text = result["choices"][0]["message"]["content"]

        visual = random.randint(60,95)
        emotional = random.randint(60,95)
        engagement = random.randint(60,95)
        branding = random.randint(60,95)

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
                "analysis": text
            },
            "usage": usage_info
        })
    except Exception as e:
        return jsonify({"error": str(e)})


# -------------------
# Get Usage
# -------------------
@app.route("/api/usage")
def usage():
    uid, error_resp, status = verify_user_token()
    if error_resp:
        return error_resp, status
    return jsonify(get_usage(uid))


# -------------------
# Auth Pages
# -------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")

        try:
            auth.get_user_by_email(email)
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


# -------------------
# Run App
# -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
