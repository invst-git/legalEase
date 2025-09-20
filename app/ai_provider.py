import os
import json
from dotenv import load_dotenv

load_dotenv()


def generate_oracle_json(prompt: str) -> dict:
    """Generate a JSON response for Clause Oracle via Vertex AI.

    Expects env vars:
      - VERTEX_PROJECT
      - VERTEX_LOCATION
      - VERTEX_MODEL (default: gemini-1.5-pro)

    Returns a dict with keys: "answer", "citation".
    Raises on initialization errors; caller should handle fallbacks.
    """
    # Lazy imports to avoid hard dependency when not enabled
    import vertexai
    from vertexai.generative_models import GenerativeModel, GenerationConfig

    project = os.getenv("VERTEX_PROJECT")
    location = os.getenv("VERTEX_LOCATION", "us-central1")
    model_name = os.getenv("VERTEX_MODEL", "gemini-1.5-pro")

    if not project:
        raise RuntimeError("VERTEX_PROJECT env var is required for Vertex AI provider")

    vertexai.init(project=project, location=location)
    model = GenerativeModel(model_name)

    gen_cfg = GenerationConfig(response_mime_type="application/json")
    response = model.generate_content(prompt, generation_config=gen_cfg)

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        # Fallback: try candidates -> content -> parts
        try:
            candidates = getattr(response, "candidates", []) or []
            for c in candidates:
                parts = getattr(getattr(c, "content", None), "parts", []) or []
                for p in parts:
                    t = getattr(p, "text", "")
                    if t:
                        text = t.strip()
                        break
                if text:
                    break
        except Exception:
            pass

    # Ensure JSON object contract
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Non-object JSON")
    except Exception:
        data = {"answer": text or "", "citation": ""}

    # Guarantee keys
    data.setdefault("answer", "")
    data.setdefault("citation", "")
    return data
