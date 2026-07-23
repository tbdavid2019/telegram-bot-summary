"""LLM summarization shared by Bot and FastAPI."""

import re

import requests

from app.config import Settings


def call_gpt_api(prompt, additional_messages, settings: Settings, selected_model=None):
    response = requests.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}", "Content-Type": "application/json"},
        json={
            "model": selected_model or settings.llm_model,
            "messages": additional_messages + [{"role": "user", "content": prompt}],
        },
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


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
