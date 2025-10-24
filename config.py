# config.py

import os

# MongoDB URI (local or Atlas)
MONGO_URI = "mongodb://localhost:27017/glassmind_ai"

# OpenAI API Key
# config.py
OPENAI_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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"
)


# JWT Secret Key (for authentication)
JWT_SECRET = "supersecretkey123"
