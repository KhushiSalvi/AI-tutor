import os

PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")  # "gemini" or "ollama"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")


def llm_ready():
    if PROVIDER == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY"))
    return True


def llm_help():
    if PROVIDER == "gemini":
        return "Set GEMINI_API_KEY in this terminal, then restart the app."
    return "Make sure Ollama is running and the model is pulled."


def generate(system, user):
    if PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=1500),
        )
        return resp.text
    import ollama

    r = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return r["message"]["content"]
