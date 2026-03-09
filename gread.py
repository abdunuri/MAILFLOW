import os
import dotenv

dotenv.load_dotenv()
# If run from project root, also try backend/.env
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

from google import genai

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set; cannot run gread.py. Set it in .env or the environment.")

client = genai.Client(api_key=API_KEY)

response = client.models.generate_content(
    model="gemini-3-flash-preview", contents="Explain how AI works in a few words"
)
print(response.text)