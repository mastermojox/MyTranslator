from __future__ import annotations
import asyncio
import os
import random
import httpx

RETRYABLE_STATUS = {429, 502, 503, 504}
DEFAULT_BASE_URL = 'https://positionapi.top/v1'
DEFAULT_MODEL = 'deepseek-v4.1-flash-1017'

class LLMClientError(RuntimeError):
    pass

class EmptyResponseError(LLMClientError):
    pass

class LLMClient:
    def __init__(self, api_base_url=None, api_key=None, model=None, timeout=60.0, max_retries=4, backoff_base=1.0, client=None):
        self.api_base_url = (api_base_url or os.getenv('API_BASE_URL', DEFAULT_BASE_URL)).rstrip('/')
        self.api_key = api_key or os.getenv('API_KEY', '')
        self.model = model or os.getenv('MODEL_TRANSLATE', DEFAULT_MODEL)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._client = client

    @property
    def endpoint(self):
        suffix = '/chat/completions' if self.api_base_url.endswith('/v1') else '/v1/chat/completions'
        return self.api_base_url + suffix

    async def _post(self, payload, headers):
        if self._client is not None:
            return await self._client.post(self.endpoint, json=payload, headers=headers)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(self.endpoint, json=payload, headers=headers)

    async def generate(self, system_prompt, user_prompt, temperature=0.3, model=None):
        if not self.api_key:
            raise LLMClientError('API_KEY is not set')
        payload = {'model': model or self.model, 'temperature': temperature, 'messages': [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}]}
        headers = {'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'}
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._post(payload, headers)
            except httpx.HTTPError as exc:
                if attempt >= self.max_retries:
                    raise LLMClientError(f'LLM request failed after {attempt + 1} attempts: {exc}') from exc
                await asyncio.sleep(self.backoff_base * (2 ** attempt) + random.uniform(0, 0.25))
                continue
            if response.status_code in RETRYABLE_STATUS:
                if attempt >= self.max_retries:
                    raise LLMClientError(f'LLM API error {response.status_code} after {attempt + 1} attempts: {response.text[:200]}')
                await asyncio.sleep(self.backoff_base * (2 ** attempt) + random.uniform(0, 0.25))
                continue
            if response.status_code >= 400:
                raise LLMClientError(f'LLM API error {response.status_code}: {response.text[:200]}')
            try:
                data = response.json()
            except ValueError as exc:
                raise EmptyResponseError('LLM response is not valid JSON') from exc
            choices = data.get('choices') or []
            content = ((choices[0].get('message') or {}).get('content') if choices else None)
            if content is None or not str(content).strip():
                raise EmptyResponseError('LLM response has no content')
            return content
        raise LLMClientError('LLM request failed')
