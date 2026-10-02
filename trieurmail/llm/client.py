"""Client minimaliste pour toute API compatible OpenAI (Ollama, LM Studio, vLLM,
llama.cpp server, LocalAI, Jan, OpenAI...).

Optimisations :
- une seule connexion HTTP keep-alive partagée ;
- sémaphore pour borner le parallélisme (le GPU local ne sert à rien s'il sature) ;
- cache disque des réponses (même prompt + même modèle = aucun nouvel appel) ;
- retries avec backoff sur 429 / 5xx / erreurs réseau ;
- repli automatique si le serveur ne supporte pas response_format=json_object ;
- compteurs d'usage (appels, tokens, cache) affichés dans l'interface.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import httpx

from ..config import LLMSettings
from ..db import Database


class LLMError(Exception):
    pass


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    errors: int = 0
    seconds: float = 0.0
    last_error: str = ""
    started: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


def strip_reasoning(text: str) -> str:
    """Retire les blocs de raisonnement des modèles type DeepSeek-R1 / Qwen3."""
    text = _THINK_RE.sub("", text)
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def extract_json(text: str) -> Any:
    text = strip_reasoning(text)
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # premier objet / tableau équilibré
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            # virgules finales tolérées
                            try:
                                return json.loads(re.sub(r",\s*([}\]])", r"\1", candidate))
                            except json.JSONDecodeError:
                                break
            start = text.find(opener, start + 1)
    raise LLMError("Réponse IA non exploitable (JSON invalide)")


class LLMClient:
    def __init__(self, settings: LLMSettings, db: Optional[Database] = None,
                 transport: Optional[httpx.AsyncBaseTransport] = None):
        self.settings = settings
        self.db = db
        self.usage = Usage()
        self._sem = asyncio.Semaphore(settings.concurrency)
        self._json_supported = settings.json_mode
        headers = {"Content-Type": "application/json"}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        self._http = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(settings.timeout, connect=10.0),
            limits=httpx.Limits(max_connections=settings.concurrency + 2, max_keepalive_connections=settings.concurrency + 2),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- utilitaires --------------------------------------------------------
    def _model(self, model: Optional[str]) -> str:
        chosen = model or self.settings.model
        if not chosen:
            raise LLMError("Aucun modèle configuré (Réglages → IA)")
        return chosen

    def _payload(self, messages, model, temperature, max_tokens, json_mode, stream=False) -> dict:
        payload: dict[str, Any] = {
            "model": self._model(model),
            "messages": messages,
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.settings.max_tokens,
            "stream": stream,
        }
        if json_mode and self._json_supported:
            payload["response_format"] = {"type": "json_object"}
        return payload

    @staticmethod
    def _hash(payload: dict) -> str:
        key = {k: v for k, v in payload.items() if k != "stream"}
        return hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    async def _post(self, payload: dict) -> dict:
        delay = 1.5
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                resp = await self._http.post("/chat/completions", json=payload)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.WriteError) as exc:
                last_exc = exc
            else:
                if resp.status_code == 400 and "response_format" in payload:
                    # serveur ne supportant pas le mode JSON : on retente sans
                    self._json_supported = False
                    payload = {k: v for k, v in payload.items() if k != "response_format"}
                    continue
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_exc = LLMError(f"HTTP {resp.status_code} : {resp.text[:200]}")
                elif resp.status_code >= 400:
                    raise LLMError(f"HTTP {resp.status_code} : {resp.text[:300]}")
                else:
                    return resp.json()
            await asyncio.sleep(delay)
            delay *= 2
        raise LLMError(f"Serveur IA injoignable : {last_exc}")

    # -- API publique -------------------------------------------------------
    async def chat(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        use_cache: bool = True,
    ) -> str:
        payload = self._payload(messages, model, temperature, max_tokens, json_mode)
        h = self._hash(payload)
        if use_cache and self.db is not None:
            cached = self.db.llm_get(h)
            if cached is not None:
                self.usage.cache_hits += 1
                return cached
        async with self._sem:
            started = time.perf_counter()
            try:
                data = await self._post(payload)
            except Exception as exc:
                self.usage.errors += 1
                self.usage.last_error = str(exc)
                raise
            finally:
                self.usage.seconds += time.perf_counter() - started
        self.usage.calls += 1
        usage = data.get("usage") or {}
        self.usage.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.usage.completion_tokens += int(usage.get("completion_tokens") or 0)
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Réponse inattendue du serveur : {str(data)[:200]}") from exc
        content = strip_reasoning(content)
        if use_cache and self.db is not None and content:
            self.db.llm_put(h, content)
        return content

    async def chat_json(self, messages: list[dict], **kwargs) -> Any:
        text = await self.chat(messages, json_mode=True, **kwargs)
        try:
            return extract_json(text)
        except LLMError:
            # une seule relance, sans cache, en rappelant le format attendu
            retry = messages + [
                {"role": "assistant", "content": text[:2000]},
                {"role": "user", "content": "Ta réponse n'était pas un JSON valide. Renvoie UNIQUEMENT le JSON demandé."},
            ]
            text = await self.chat(retry, json_mode=True, use_cache=False, **kwargs)
            return extract_json(text)

    async def stream(
        self,
        messages: list[dict],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, model, temperature, max_tokens, json_mode=False, stream=True)
        async with self._sem:
            self.usage.calls += 1
            in_think = False
            async with self._http.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode(errors="replace")
                    self.usage.errors += 1
                    raise LLMError(f"HTTP {resp.status_code} : {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    if data.get("usage"):
                        self.usage.prompt_tokens += int(data["usage"].get("prompt_tokens") or 0)
                        self.usage.completion_tokens += int(data["usage"].get("completion_tokens") or 0)
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0].get("delta") or {}).get("content") or ""
                    if not delta:
                        continue
                    # masque le raisonnement <think> en streaming
                    if "<think>" in delta:
                        in_think = True
                        delta = delta.split("<think>", 1)[0]
                    if in_think:
                        if "</think>" in delta:
                            in_think = False
                            delta = delta.split("</think>", 1)[1]
                        else:
                            continue
                    if delta:
                        yield delta

    async def list_models(self) -> list[str]:
        resp = await self._http.get("/models")
        if resp.status_code >= 400:
            raise LLMError(f"HTTP {resp.status_code} : {resp.text[:200]}")
        data = resp.json()
        items = data.get("data", data if isinstance(data, list) else [])
        return sorted(str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id"))
