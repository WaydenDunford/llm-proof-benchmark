"""Optional standard-library client for a chat-completions endpoint."""
import json
import os
from urllib.request import Request, urlopen
from .base import Adapter
from ..schemas import Generation, GenerationOutput


class OpenAICompatibleAdapter(Adapter):
    def generate(self, prompt: str, settings: Generation) -> GenerationOutput:
        payload = {"model": self.config.model_id, "messages": [{"role": "user", "content": prompt}],
                   "temperature": settings.temperature if settings.do_sample else 0,
                   "top_p": settings.top_p if settings.do_sample and settings.temperature > 0 else 1,
                   "max_tokens": settings.max_new_tokens, "seed": settings.seed}
        if set(payload).intersection(self.config.backend_options):
            raise ValueError("backend_options cannot override standardized generation fields")
        payload.update(self.config.backend_options)
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.config.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = Request(self.config.base_url.rstrip("/") + "/chat/completions",
                          data=json.dumps(payload).encode(), headers=headers)
        with urlopen(request, timeout=self.config.timeout_seconds) as response:
            data = json.load(response)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return GenerationOutput(text=text, token_count_input=usage.get("prompt_tokens"),
                                token_count_output=usage.get("completion_tokens"),
                                metadata={"system_fingerprint": data.get("system_fingerprint"),
                                          "resolved_revision": None, "effective_generation": settings.model_dump()})
