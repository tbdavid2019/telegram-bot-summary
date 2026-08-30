"""LLM summarization shared by Bot and FastAPI."""

import re

from app.config import Settings
from app.services.llm import call_llm_with_fallback


def call_gpt_api(prompt, additional_messages, settings: Settings, selected_model=None):
    return call_llm_with_fallback(
        prompt=prompt,
        additional_messages=additional_messages,
        selected_model=selected_model,
        timeout=settings.llm_timeout_seconds,
    )


def summarize(text_array, system_prompt, settings: Settings, selected_model=None):
    try:
        summary = call_gpt_api(
            "總結 the following text:\n" + "\n".join(text_array),
            [{"role": "system", "content": system_prompt}],
            settings,
            selected_model,
        )
        summary = re.sub(r"(?<!\S)#(?=[^\s#])", r"\\#", summary)
        return summary + "\n\n✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"
    except Exception as error:
        print(f"Error: {error}")
        return "Unknown error! Please contact the owner. ok@vip.david888.com"
