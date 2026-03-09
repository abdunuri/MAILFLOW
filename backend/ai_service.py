"""Google Gemini AI service for MailFlow.

Handles:
- Email categorization when no rule matches
- AI-generated reply bodies for categories with use_ai_reply=True
"""
import config
import logging
# add a logg to every function in the file
logging.basicConfig(level=logging.INFO)
def log_function(func):
    def wrapper(*args, **kwargs):
        logging.info(f"Calling {func.__name__} with args: {args} and kwargs: {kwargs}")
        return func(*args, **kwargs)
    return wrapper

import os
import dotenv

dotenv.load_dotenv()
# If run from project root, also try backend/.env
dotenv.load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))

from google import genai
def _get_client():
    API_KEY = os.getenv("GEMINI_API_KEY")
    if not API_KEY:
        logging.error("GEMINI_API_KEY not set; cannot run ai_service.py. Set it in .env or the environment.")
        raise RuntimeError("GEMINI_API_KEY")
    return genai.Client(api_key=API_KEY)

def sample_response():
    genai = _get_client()
    
    if not genai:
        logging.error("genai not set; cannot run sample_response()")
        return None
    response = genai.models.generate_content(
        model="gemini-3-flash-preview",
        contents="Hello, how are you?"
    )
    logging.info(response.text)
    return response.text
    pass

def ai_categorize(email_data: dict, category_names: list[str]) -> str | None:
    """Use Gemini to assign one of the categories to an email.

    Returns the category name if found, else None.
    """
    genai = _get_client()
    if not genai:
        logging.error("GEMINI_API_KEY not set; cannot run ai_service.py. Set it in .env or the environment.")
        logging.error("genai not set; cannot run ai_categorize()")
        raise RuntimeError("genai not set; cannot run ai_categorize()")
    if not category_names:
        logging.error("category_names not set; cannot run ai_categorize()")
        raise RuntimeError("category_names not set; cannot run ai_categorize()")
    prompt = (
        "You are an email categorisation assistant.\n"
        f"Available categories: {', '.join(category_names)}\n"
        f"Email subject: {email_data.get('subject', '')}\n"
        f"Email sender: {email_data.get('sender', '')}\n"
        f"Email snippet: {email_data.get('snippet', '')[:300]}\n\n"
        "Respond with ONLY the category name that best fits this email, "
        "or 'None' if none apply."
    )
    response = genai.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )
    return response.text.strip()

def ai_generate_reply(email_data: dict, category_name: str) -> tuple[str, str] | None:
    """Use Gemini to generate a reply subject and body for an email in a category.

    Returns (subject, body) or None on failure.
    Uses placeholders {sender} and {subject} in the prompt so the model knows
    the context. Returns plain text suitable for direct use (placeholders
    will be substituted by the caller if needed - we'll return the actual
    values filled in for simplicity).
    """
    genai = _get_client()
    if not genai:
        logging.error("GEMINI_API_KEY not set; cannot run ai_service.py. Set it in .env or the environment.")
        logging.error("genai not set; cannot run ai_generate_reply()")
        raise RuntimeError("genai not set; cannot run ai_generate_reply()")
    if not category_name:
        logging.error("category_name not set; cannot run ai_generate_reply()")
        raise RuntimeError("category_name not set; cannot run ai_generate_reply()")
    prompt = (
        "You are a professional email reply assistant.\n"
        f"The email is in category: {category_name}\n"
        f"Original sender: {email_data.get('sender', '')}\n"
        f"Original subject: {email_data.get('subject', '')}\n"
        f"Original email content: {email_data.get('body', '') or email_data.get('snippet', '')[:500]}\n\n"
        "Generate a concise, professional reply. "
        "Output format exactly:\n"
        "SUBJECT: <reply subject line, e.g. Re: Original subject>\n"
        "\n<reply body text>\n"
        "Keep the reply brief (2-4 sentences) and appropriate for the category."
    )
    # 'Client' object has no attribute 'types
    response = genai.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt
    )
    # split the response into subject and body
    subject = response.text.strip().split("\n")[0]
    body = response.text.strip().split("\n")[1:]
    return subject, body

