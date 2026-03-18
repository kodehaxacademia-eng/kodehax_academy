from __future__ import annotations

from functools import lru_cache

from google import genai

from django.conf import settings


@lru_cache(maxsize=1)
def get_gemini_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_text(model: str, prompt: str, config=None) -> str:
    response = get_gemini_client().models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return getattr(response, "text", "") or ""


def generate_multimodal(model: str, contents, config=None) -> str:
    response = get_gemini_client().models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return getattr(response, "text", "") or ""


def list_model_names() -> list[str]:
    names = []
    for model in get_gemini_client().models.list():
        model_name = getattr(model, "name", "")
        if model_name:
            names.append(model_name)
    return names


def list_generate_content_models() -> list[str]:
    names = []
    for model in get_gemini_client().models.list():
        model_name = getattr(model, "name", "")
        supported = set(getattr(model, "supported_actions", []) or [])
        methods = set(getattr(model, "supported_generation_methods", []) or [])
        if model_name and ("generateContent" in methods or "generateContent" in supported):
            names.append(model_name)
    return names
