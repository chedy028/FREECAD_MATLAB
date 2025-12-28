"""OpenRouter API client with tool-calling support"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel


class ModelInfo(BaseModel):
    """OpenRouter model information"""

    id: str
    name: str
    context_length: int = 0
    pricing: Dict[str, float] = {}
    supports_tools: bool = False
    supports_response_format: bool = False


class OpenRouterClient:
    """Client for OpenRouter API"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        http_referer: Optional[str] = None,
        x_title: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required (OPENROUTER_API_KEY env var)")

        self.base_url = base_url.rstrip("/")
        self.http_referer = http_referer
        self.x_title = x_title
        self.timeout = timeout

        self._models_cache: Optional[List[ModelInfo]] = None
        self._models_cache_time: Optional[datetime] = None
        self._models_cache_ttl = timedelta(minutes=10)

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.http_referer:
            headers["HTTP-Referer"] = self.http_referer
        if self.x_title:
            headers["X-Title"] = self.x_title
        return headers

    async def list_models(self, force_refresh: bool = False) -> List[ModelInfo]:
        """
        List available models from OpenRouter.
        
        Caches results for 10 minutes by default.
        """
        now = datetime.now()

        if not force_refresh and self._models_cache:
            if self._models_cache_time and (now - self._models_cache_time) < self._models_cache_ttl:
                return self._models_cache

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/models",
                headers=self._build_headers(),
            )
            response.raise_for_status()
            data = response.json()

        models = []
        for model_data in data.get("data", []):
            model = ModelInfo(
                id=model_data.get("id", ""),
                name=model_data.get("name", ""),
                context_length=model_data.get("context_length", 0),
                pricing=model_data.get("pricing", {}),
                # OpenRouter models typically support tools if they're OpenAI/Anthropic compatible
                supports_tools=True,  # Assume true for now
                supports_response_format=model_data.get("id", "").startswith(
                    ("openai/", "anthropic/claude-3")
                ),
            )
            models.append(model)

        self._models_cache = models
        self._models_cache_time = now
        return models

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        route: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Call OpenRouter chat completion endpoint.
        
        Args:
            messages: Chat messages
            model: Model ID (e.g., "openai/gpt-4o")
            tools: OpenAI-style tool definitions
            tool_choice: "auto", "none", or {"type": "function", "function": {"name": "..."}}
            response_format: {"type": "json_object"} for structured output
            temperature: Sampling temperature
            max_tokens: Max response tokens
            route: "fallback" to try fallback models automatically
            fallback_models: List of fallback model IDs
        
        Returns:
            OpenRouter response dict
        """
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if tools:
            payload["tools"] = tools
        
        if tool_choice:
            payload["tool_choice"] = tool_choice

        if response_format:
            payload["response_format"] = response_format

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if route:
            payload["route"] = route

        if fallback_models:
            payload["models"] = [model] + fallback_models

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._build_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def chat_completion_with_retry(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Chat completion with automatic retries on failure.
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.chat_completion(messages, model, tools, **kwargs)
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500:
                    # Server error, retry
                    continue
                elif e.response.status_code == 429:
                    # Rate limit, could implement backoff here
                    continue
                else:
                    # Client error, don't retry
                    raise
            except httpx.TimeoutException as e:
                last_error = e
                continue

        raise last_error or Exception("Max retries exceeded")

    def extract_tool_calls(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract tool calls from OpenRouter response.
        
        Returns list of tool calls in format:
        [{"id": "call_...", "name": "tool_name", "arguments": {...}}]
        """
        tool_calls = []
        
        choices = response.get("choices", [])
        if not choices:
            return tool_calls

        message = choices[0].get("message", {})
        raw_tool_calls = message.get("tool_calls", [])

        for tc in raw_tool_calls:
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "arguments": tc.get("function", {}).get("arguments", "{}"),
            })

        return tool_calls

    def get_assistant_message(self, response: Dict[str, Any]) -> Optional[str]:
        """Extract assistant message content from response"""
        choices = response.get("choices", [])
        if not choices:
            return None
        return choices[0].get("message", {}).get("content")

