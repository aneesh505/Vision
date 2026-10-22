import os
import openai
from dotenv import load_dotenv

load_dotenv()

class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openai").lower()
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "8192"))
        self.timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))

        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = os.getenv("LLM_MODEL", "auto")

        if self.provider in ("modal", "omniroute"):
            if self.base_url and not self.base_url.rstrip("/").endswith("/v1"):
                self.base_url = f"{self.base_url.rstrip('/')}/v1"
        elif self.provider == "openai":
            if not self.base_url:
                self.base_url = None

        if self.api_key:
            client_options = {"api_key": self.api_key}
            if self.base_url:
                client_options["base_url"] = self.base_url.rstrip("/")
            self.client = openai.OpenAI(**client_options, timeout=self.timeout_seconds, max_retries=0)
        else:
            self.client = None

    def query(self, prompt: str, system_prompt: str = "You are an expert DevSecOps and security engineering AI.") -> str:
        if not self.client:
            raise ValueError("LLM_API_KEY is not configured.")
        model_name = self.model if self.model else "auto"

        try:
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"LLM generation failed: {e}")