"""
Career Tracker — Universal Multi-Provider LLM Engine

Supports:
1. Google Gemini API (gemini-2.5-flash / gemini-1.5-flash)
2. Groq Cloud API (llama-3.3-70b / deepseek-r1-distill)
3. DeepSeek API (deepseek-chat / deepseek-reasoner)
4. OpenRouter API (Universal multi-model gateway)
5. Together AI API (Llama, Mistral, Qwen)
6. Anthropic Claude API (claude-3-5-sonnet)
7. OpenAI API (gpt-4o-mini)
8. HuggingFace Serverless Inference API
9. Ollama Local API (http://localhost:11434)
10. Local Rule-Based High-Precision Fallback AI Engine
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import requests

from config.settings import get_settings

logger = logging.getLogger(__name__)


def clean_json_response(raw_text: str) -> dict[str, Any]:
    """Clean and parse JSON from raw LLM output strings safely."""
    if not raw_text:
        return {}

    # Strips markdown code fences
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()
    cleaned = cleaned.strip("`")

    # Match JSON object using regex fallback
    json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Retry with quote replacement if malformed
        try:
            fixed = cleaned.replace("'", '"')
            return json.loads(fixed)
        except Exception:
            logger.debug("Failed to decode JSON from LLM: %s", raw_text[:200])
            return {}


class LLMProviderEngine:
    """Multi-provider LLM orchestrator with automatic fallback cascading."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_json(self, prompt: str, system_prompt: str = "") -> tuple[dict[str, Any], str]:
        """
        Executes prompt across available LLM providers in priority order.
        Returns tuple of (parsed_dict, provider_used_name).
        """

        # 1. Google Gemini API
        gemini_key = os.getenv("GEMINI_API_KEY") or getattr(self.settings, "gemini_api_key", None)
        if gemini_key:
            res = self._call_gemini(prompt, gemini_key)
            if res:
                return res, "Google Gemini AI"

        # 2. Groq Cloud API (Super fast Llama-3.3-70b / DeepSeek R1)
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            res = self._call_groq(prompt, groq_key, system_prompt)
            if res:
                return res, "Groq AI (Llama-3.3-70B)"

        # 3. DeepSeek API
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        if deepseek_key:
            res = self._call_deepseek(prompt, deepseek_key, system_prompt)
            if res:
                return res, "DeepSeek AI (V3/R1)"

        # 4. OpenRouter API
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_key:
            res = self._call_openrouter(prompt, openrouter_key, system_prompt)
            if res:
                return res, "OpenRouter AI"

        # 5. Together AI API
        together_key = os.getenv("TOGETHER_API_KEY")
        if together_key:
            res = self._call_together(prompt, together_key, system_prompt)
            if res:
                return res, "Together AI"

        # 6. Anthropic Claude API
        anthropic_key = os.getenv("CT_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and anthropic_key.startswith("sk-ant-"):
            res = self._call_anthropic(prompt, anthropic_key, system_prompt)
            if res:
                return res, "Anthropic Claude AI"

        # 7. OpenAI API
        openai_key = os.getenv("CT_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if openai_key and openai_key.startswith("sk-"):
            res = self._call_openai(prompt, openai_key, system_prompt)
            if res:
                return res, "OpenAI GPT-4o-mini"

        # 8. HuggingFace Serverless Inference API
        hf_token = os.getenv("HF_API_TOKEN") or os.getenv("HUGGINGFACE_TOKEN")
        if hf_token:
            res = self._call_huggingface(prompt, hf_token)
            if res:
                return res, "HuggingFace AI"

        # 9. Ollama Local Model
        ollama_res = self._call_ollama(prompt, system_prompt)
        if ollama_res:
            return ollama_res, "Ollama Local AI"

        return {}, "Fallback Rule Engine"

    def _call_gemini(self, prompt: str, api_key: str) -> dict[str, Any] | None:
        """Call Google Gemini 1.5/2.5 Flash API."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt + "\n\nRespond ONLY with valid JSON."}]}]
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return clean_json_response(raw_text)
        except Exception as e:
            logger.debug("Gemini provider failed: %s", e)
        return None

    def _call_groq(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call Groq API (Llama 3.3 70B / DeepSeek R1 Distill)."""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt + "\nRespond in pure JSON."})

            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug("Groq provider failed: %s", e)
        return None

    def _call_deepseek(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call DeepSeek API."""
        try:
            url = "https://api.deepseek.com/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt or "You are a JSON assistant."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug("DeepSeek provider failed: %s", e)
        return None

    def _call_openrouter(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call OpenRouter Gateway API."""
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt or "You return JSON only."},
                    {"role": "user", "content": prompt},
                ],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug("OpenRouter provider failed: %s", e)
        return None

    def _call_together(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call Together AI API."""
        try:
            url = "https://api.together.xyz/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "messages": [
                    {"role": "system", "content": system_prompt or "JSON output required."},
                    {"role": "user", "content": prompt},
                ],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug("Together provider failed: %s", e)
        return None

    def _call_anthropic(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call Anthropic Claude API."""
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 1024,
                "system": system_prompt or "Provide response strictly in JSON format.",
                "messages": [{"role": "user", "content": prompt}],
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["content"][0]["text"])
        except Exception as e:
            logger.debug("Anthropic provider failed: %s", e)
        return None

    def _call_openai(self, prompt: str, api_key: str, system_prompt: str) -> dict[str, Any] | None:
        """Call OpenAI API."""
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt or "Return raw JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug("OpenAI provider failed: %s", e)
        return None

    def _call_huggingface(self, prompt: str, token: str) -> dict[str, Any] | None:
        """Call Hugging Face Serverless Inference API."""
        try:
            url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "inputs": f"[INST] {prompt} Respond only in valid JSON. [/INST]",
                "parameters": {"max_new_tokens": 512, "temperature": 0.1},
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and "generated_text" in data[0]:
                    return clean_json_response(data[0]["generated_text"])
        except Exception as e:
            logger.debug("HuggingFace provider failed: %s", e)
        return None

    def _call_ollama(self, prompt: str, system_prompt: str) -> dict[str, Any] | None:
        """Call Local Ollama API if running on localhost:11434."""
        try:
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": "llama3.2",
                "prompt": prompt,
                "system": system_prompt or "Output JSON only.",
                "stream": False,
                "format": "json",
            }
            resp = requests.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return clean_json_response(data.get("response", ""))
        except Exception:
            pass  # Expected if Ollama is not installed locally
        return None


# Global singleton LLM engine instance
llm_engine = LLMProviderEngine()
