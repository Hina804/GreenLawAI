"""
LLM Manager
Unified interface for multiple LLM providers.
Registry-Compatible (Phase 3)
"""

import os
from typing import Generator, Optional, Literal, Dict, Any
from abc import ABC, abstractmethod
from loguru import logger
from core.contracts import BasePipelineComponent

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass


class OpenAILLM(BaseLLM):
    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None, **kwargs):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")
        self.model = model
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.kwargs = kwargs
    
    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=stream,
            **{k: v for k, v in self.kwargs.items() if k not in ["provider", "api_key", "api_key_env"]}
        )
        if stream:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            yield response.choices[0].message.content
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class AnthropicLLM(BaseLLM):
    def __init__(self, model: str = "claude-3-sonnet-20240229", api_key: Optional[str] = None, **kwargs):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")
        self.model = model
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.kwargs = kwargs
    
    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        if stream:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=self.kwargs.get("max_tokens", 2000),
                messages=[{"role": "user", "content": prompt}],
                **{k: v for k, v in self.kwargs.items() if k not in ["provider", "api_key", "api_key_env", "max_tokens"]}
            ) as stream:
                for text in stream.text_stream:
                    yield text
        else:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.kwargs.get("max_tokens", 2000),
                messages=[{"role": "user", "content": prompt}],
                **{k: v for k, v in self.kwargs.items() if k not in ["provider", "api_key", "api_key_env", "max_tokens"]}
            )
            yield response.content[0].text
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class OllamaLLM(BaseLLM):
    def __init__(self, model: str = "llama2", base_url: str = "http://localhost:11434", **kwargs):
        try:
            import requests
        except ImportError:
            raise ImportError("Install requests: pip install requests")
        self.model = model
        self.base_url = base_url
        self.kwargs = kwargs
        self.session = requests.Session()
    
    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        import json
        response = self.session.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
                **{k: v for k, v in self.kwargs.items() if k not in ["provider", "base_url"]}
            },
            stream=stream
        )
        if stream:
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "response" in data:
                        yield data["response"]
        else:
            yield response.json().get("response", "")
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class ColabLLM(BaseLLM):
    def __init__(self, colab_url: str, timeout: int = 60, **kwargs):
        # Local import to avoid dependency issues if not using Colab
        from data_pipeline.rag.colab_llm_client import ColabLLMClient
        self.client = ColabLLMClient(colab_url, timeout)
        self.kwargs = kwargs
    
    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        context = ""
        question = prompt
        if "Legal Excerpts:" in prompt:
            parts = prompt.split("Legal Excerpts:")
            if len(parts) > 1:
                sub_parts = parts[1].split("Question:")
                if len(sub_parts) > 1:
                    context = sub_parts[0].strip()
                    question = f"{parts[0].strip()}\n\nQuestion: {sub_parts[1].strip()}"
        
        gen_kwargs = {
            'max_tokens': self.kwargs.get('max_tokens', 2000),
            'repetition_penalty': 1.3,
            'stop': ["###", "[PROVENANCE ID]"]
        }
        
        response_text = ""
        stop_tokens = ["###", "[PROVENANCE ID]"]
        chunk_generator = self.client.generate_stream(context, question, **gen_kwargs) if stream else [self.client.generate(context, question, **gen_kwargs)]
        
        for chunk in chunk_generator:
            response_text += chunk
            should_stop = False
            for stop in stop_tokens:
                if stop in response_text[-50:]:
                    should_stop = True
                    break
            if should_stop: break
            yield chunk
    
    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class LLMManager(BasePipelineComponent):
    """
    Unified LLM interface supporting multiple providers.
    Registry-Compatible (Phase 3)
    """
    PROVIDERS = {
        "openai": OpenAILLM,
        "anthropic": AnthropicLLM,
        "ollama": OllamaLLM,
        "colab": ColabLLM
    }
    
    def __init__(self, component_id: str = "llm_manager"):
        super().__init__(component_id)
        self.usage_stats = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0
        }
        self.llm = None

    async def load(self, config: Dict[str, Any]) -> bool:
        """Lifecycle: Load configuration and initialize provider."""
        cfg = config.copy()
        provider = cfg.pop("provider", "openai")
        model = cfg.pop("model", None)
        
        # Support api_key_env lookup
        api_key = cfg.pop("api_key", None)
        api_key_env = cfg.pop("api_key_env", None)
        if not api_key and api_key_env:
            api_key = os.getenv(api_key_env)
        
        if provider not in self.PROVIDERS:
            logger.error(f"[LLMManager] Unsupported provider: {provider}")
            return False
            
        try:
            llm_class = self.PROVIDERS[provider]
            if provider == "colab":
                self.llm = llm_class(**cfg)
            elif provider == "ollama":
                self.llm = llm_class(model=model or "llama2", **cfg)
            else:
                self.llm = llm_class(model=model, api_key=api_key, **cfg)
            
            self._is_loaded = True
            logger.info(f"[LLMManager] {self.component_id} ({provider}) loaded.")
            return True
        except Exception as e:
            logger.error(f"[LLMManager] Failed to load provider {provider}: {e}")
            return False

    async def unload(self) -> bool:
        """Lifecycle: Shutdown."""
        self._is_loaded = False
        return True
    
    async def generate_resilient(self, prompt: str, stream: bool = True, timeout: int = 40) -> Generator[str, None, None]:
        """
        V7: Resilient generation with exponential backoff and retries (Audit Fix #5)
        """
        import asyncio
        import time
        from concurrent.futures import ThreadPoolExecutor

        if not self.llm:
            raise RuntimeError("[LLMManager] LLM not loaded. Call load() first.")

        self.usage_stats["requests"] += 1
        self.usage_stats["prompt_tokens"] += self.count_tokens(prompt)
        
        last_error = None
        for attempt in range(3):
            try:
                # Since self.llm.generate is a sync generator, we need to handle it carefully
                # in an async context, or just do the retries here.
                # For simplicity in this architecture, we wrap the generator access.
                
                completion_text = ""
                # We use a simple retry block for the start of the generation
                # Real streaming retries are harder, but this covers connection issues.
                
                if stream:
                    # Note: Full streaming retries mid-stream are complex.
                    # This primarily catches initial connection/timeout issues.
                    for token in self.llm.generate(prompt, stream=True):
                        completion_text += token
                        yield token
                else:
                    # Non-streaming is easier to retry
                    res_gen = self.llm.generate(prompt, stream=False)
                    completion_text = next(res_gen)
                    yield completion_text
                
                self.usage_stats["completion_tokens"] += self.count_tokens(completion_text)
                self.usage_stats["total_tokens"] = self.usage_stats["prompt_tokens"] + self.usage_stats["completion_tokens"]
                return # Success!

            except (Exception, asyncio.TimeoutError) as e:
                last_error = e
                logger.warning(f"[LLMManager] Attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    wait_time = 2 ** attempt
                    if asyncio.get_event_loop().is_running():
                        await asyncio.sleep(wait_time)
                    else:
                        time.sleep(wait_time)
        
        # Final Fallback
        raise RuntimeError(f"LLM Connection unstable: {last_error}. All retry attempts exhausted.")

    def generate(self, prompt: str, stream: bool = True) -> Generator[str, None, None]:
        """Legacy generator (redirects to the resilient logic if no event loop, or runs sync)"""
        if not self.llm:
            raise RuntimeError("[LLMManager] LLM not loaded. Call load() first.")
            
        # For legacy sync calls, we do a simpler retry
        import time
        for attempt in range(3):
            try:
                completion_text = ""
                for token in self.llm.generate(prompt, stream=stream):
                    completion_text += token
                    yield token
                return
            except Exception as e:
                logger.warning(f"[LLMManager] Sync attempt {attempt+1}/3 failed: {e}")
                if attempt < 2: time.sleep(2 ** attempt)
        
        raise RuntimeError(f"LLM connection failed after 3 attempts for prompt starting with: {prompt[:30]}...")

    def count_tokens(self, text: str) -> int:
        if not self.llm: return len(text) // 4
        return self.llm.count_tokens(text)

    def get_usage_report(self) -> dict:
        return self.usage_stats
