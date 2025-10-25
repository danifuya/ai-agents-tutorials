#!/usr/bin/env python3
"""
Advanced Embedding Generator for RAG Pipeline

Supports multiple embedding providers with unified interface:
- OpenAI embeddings (text-embedding-3-small, text-embedding-3-large)
- Jina embeddings (jina-embeddings-v2-base-en)
- Local models (sentence-transformers)

Features:
- Batch processing for multiple inputs
- Automatic retry logic with exponential backoff
- Token counting and cost estimation
- Caching for duplicate inputs
- Comprehensive error handling
"""

import time
import hashlib
from typing import List, Union, Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging
import os

# Optional imports - providers will be disabled if not available
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import requests

    JINA_AVAILABLE = True
except ImportError:
    JINA_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


@dataclass
class EmbeddingResult:
    """Result container for embedding operations"""

    embedding: List[float]
    tokens_used: int
    input_text: str
    model: str
    provider: str
    processing_time: float


@dataclass
class BatchEmbeddingResult:
    """Result container for batch embedding operations"""

    embeddings: List[List[float]]
    total_tokens: int
    inputs: List[str]
    model: str
    provider: str
    processing_time: float
    individual_results: List[EmbeddingResult]


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers"""

    @abstractmethod
    def embed_single(self, text: str, model: str) -> EmbeddingResult:
        """Generate embedding for single text"""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str], model: str) -> BatchEmbeddingResult:
        """Generate embeddings for multiple texts"""
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        pass


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider"""

    def __init__(self, api_key: Optional[str] = None):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        # Use environment variable if no api_key provided
        self.client = OpenAI(
            api_key=api_key
        )  # OpenAI() automatically uses OPENAI_API_KEY if api_key is None
        self.name = "openai"

        # Model configurations
        self.models = {
            "text-embedding-3-small": {"dimensions": 1536, "cost_per_1k": 0.00002},
            "text-embedding-3-large": {"dimensions": 3072, "cost_per_1k": 0.00013},
            "text-embedding-ada-002": {"dimensions": 1536, "cost_per_1k": 0.0001},
        }

    def embed_single(
        self, text: str, model: str = "text-embedding-3-small"
    ) -> EmbeddingResult:
        """Generate embedding for single text"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(input=text, model=model)

            processing_time = time.time() - start_time

            return EmbeddingResult(
                embedding=response.data[0].embedding,
                tokens_used=response.usage.total_tokens,
                input_text=text,
                model=model,
                provider=self.name,
                processing_time=processing_time,
            )

        except Exception as e:
            raise Exception(f"OpenAI embedding failed: {str(e)}")

    def embed_batch(
        self, texts: List[str], model: str = "text-embedding-3-small"
    ) -> BatchEmbeddingResult:
        """Generate embeddings for multiple texts"""
        start_time = time.time()

        try:
            response = self.client.embeddings.create(input=texts, model=model)

            processing_time = time.time() - start_time

            embeddings = [item.embedding for item in response.data]

            # Create individual results
            individual_results = []
            for i, text in enumerate(texts):
                individual_results.append(
                    EmbeddingResult(
                        embedding=embeddings[i],
                        tokens_used=response.usage.total_tokens
                        // len(texts),  # Approximate
                        input_text=text,
                        model=model,
                        provider=self.name,
                        processing_time=processing_time / len(texts),  # Approximate
                    )
                )

            return BatchEmbeddingResult(
                embeddings=embeddings,
                total_tokens=response.usage.total_tokens,
                inputs=texts,
                model=model,
                provider=self.name,
                processing_time=processing_time,
                individual_results=individual_results,
            )

        except Exception as e:
            raise Exception(f"OpenAI batch embedding failed: {str(e)}")

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token for English)"""
        return len(text) // 4

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return list(self.models.keys())


class JinaEmbeddingProvider(EmbeddingProvider):
    """Jina embedding provider"""

    def __init__(self, api_key: Optional[str] = None):
        if not JINA_AVAILABLE:
            raise ImportError(
                "requests package not installed. Run: pip install requests"
            )

        self.api_key = api_key or os.getenv("JINA_API_KEY")
        self.name = "jina"
        self.base_url = "https://api.jina.ai/v1/embeddings"

        # Model configurations
        self.models = {
            "jina-embeddings-v2-base-en": {"dimensions": 768, "max_length": 8192},
            "jina-embeddings-v2-small-en": {"dimensions": 512, "max_length": 8192},
        }

    def embed_single(
        self, text: str, model: str = "jina-embeddings-v2-base-en"
    ) -> EmbeddingResult:
        """Generate embedding for single text"""
        start_time = time.time()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {"input": [text], "model": model}

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            processing_time = time.time() - start_time

            return EmbeddingResult(
                embedding=data["data"][0]["embedding"],
                tokens_used=data["usage"]["total_tokens"],
                input_text=text,
                model=model,
                provider=self.name,
                processing_time=processing_time,
            )

        except Exception as e:
            raise Exception(f"Jina embedding failed: {str(e)}")

    def embed_batch(
        self, texts: List[str], model: str = "jina-embeddings-v2-base-en"
    ) -> BatchEmbeddingResult:
        """Generate embeddings for multiple texts"""
        start_time = time.time()

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {"input": texts, "model": model}

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()

            data = response.json()
            processing_time = time.time() - start_time

            embeddings = [item["embedding"] for item in data["data"]]

            # Create individual results
            individual_results = []
            for i, text in enumerate(texts):
                individual_results.append(
                    EmbeddingResult(
                        embedding=embeddings[i],
                        tokens_used=data["usage"]["total_tokens"]
                        // len(texts),  # Approximate
                        input_text=text,
                        model=model,
                        provider=self.name,
                        processing_time=processing_time / len(texts),  # Approximate
                    )
                )

            return BatchEmbeddingResult(
                embeddings=embeddings,
                total_tokens=data["usage"]["total_tokens"],
                inputs=texts,
                model=model,
                provider=self.name,
                processing_time=processing_time,
                individual_results=individual_results,
            )

        except Exception as e:
            raise Exception(f"Jina batch embedding failed: {str(e)}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count - Jina uses similar tokenization to OpenAI"""
        return len(text) // 4

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return list(self.models.keys())


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers provider"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. Run: pip install sentence-transformers"
            )

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.name = "local"

    def embed_single(self, text: str, model: str = None) -> EmbeddingResult:
        """Generate embedding for single text"""
        start_time = time.time()

        try:
            embedding = self.model.encode(text).tolist()
            processing_time = time.time() - start_time

            return EmbeddingResult(
                embedding=embedding,
                tokens_used=self.estimate_tokens(text),
                input_text=text,
                model=self.model_name,
                provider=self.name,
                processing_time=processing_time,
            )

        except Exception as e:
            raise Exception(f"Local embedding failed: {str(e)}")

    def embed_batch(self, texts: List[str], model: str = None) -> BatchEmbeddingResult:
        """Generate embeddings for multiple texts"""
        start_time = time.time()

        try:
            embeddings = self.model.encode(texts).tolist()
            processing_time = time.time() - start_time

            total_tokens = sum(self.estimate_tokens(text) for text in texts)

            # Create individual results
            individual_results = []
            for i, text in enumerate(texts):
                individual_results.append(
                    EmbeddingResult(
                        embedding=embeddings[i],
                        tokens_used=self.estimate_tokens(text),
                        input_text=text,
                        model=self.model_name,
                        provider=self.name,
                        processing_time=processing_time / len(texts),  # Approximate
                    )
                )

            return BatchEmbeddingResult(
                embeddings=embeddings,
                total_tokens=total_tokens,
                inputs=texts,
                model=self.model_name,
                provider=self.name,
                processing_time=processing_time,
                individual_results=individual_results,
            )

        except Exception as e:
            raise Exception(f"Local batch embedding failed: {str(e)}")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count"""
        return len(text) // 4

    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        return [self.model_name]


class EmbeddingGenerator:
    """
    Unified embedding generator with support for multiple providers

    Usage:
        # OpenAI
        generator = EmbeddingGenerator(provider="openai", api_key="sk-...")
        result = generator.embed("Hello world")

        # Jina
        generator = EmbeddingGenerator(provider="jina", api_key="jina_...")
        result = generator.embed("Hello world")

        # Local
        generator = EmbeddingGenerator(provider="local")
        result = generator.embed("Hello world")
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        enable_caching: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        self.provider_name = provider
        self.enable_caching = enable_caching
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cache: Dict[str, EmbeddingResult] = {}

        # Initialize provider
        if provider == "openai":
            self.provider = OpenAIEmbeddingProvider(api_key)
            self.default_model = model or "text-embedding-3-small"
        elif provider == "jina":
            self.provider = JinaEmbeddingProvider(api_key)
            self.default_model = model or "jina-embeddings-v2-base-en"
        elif provider == "local":
            model_name = model or "all-MiniLM-L6-v2"
            self.provider = LocalEmbeddingProvider(model_name)
            self.default_model = model_name
        else:
            raise ValueError(
                f"Unknown provider: {provider}. Supported: openai, jina, local"
            )

    def embed(self, text: str, model: Optional[str] = None) -> EmbeddingResult:
        """
        Generate embedding for single text with retry logic and caching

        Args:
            text: Input text to embed
            model: Model to use (optional, uses default if not specified)

        Returns:
            EmbeddingResult with embedding and metadata
        """
        model = model or self.default_model

        # Check cache
        if self.enable_caching:
            cache_key = self._get_cache_key(text, model)
            if cache_key in self.cache:
                return self.cache[cache_key]

        # Generate embedding with retries
        for attempt in range(self.max_retries):
            try:
                result = self.provider.embed_single(text, model)

                # Cache result
                if self.enable_caching:
                    self.cache[cache_key] = result

                return result

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                # Exponential backoff
                wait_time = self.retry_delay * (2**attempt)
                logging.warning(
                    f"Embedding attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}"
                )
                time.sleep(wait_time)

    def embed_batch(
        self, texts: List[str], model: Optional[str] = None, batch_size: int = 100
    ) -> BatchEmbeddingResult:
        """
        Generate embeddings for multiple texts with batching

        Args:
            texts: List of input texts
            model: Model to use (optional)
            batch_size: Maximum batch size for API calls

        Returns:
            BatchEmbeddingResult with embeddings and metadata
        """
        model = model or self.default_model

        if len(texts) <= batch_size:
            # Single batch
            return self._embed_batch_with_retry(texts, model)
        else:
            # Multiple batches
            all_embeddings = []
            all_individual_results = []
            total_tokens = 0
            total_time = 0

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                batch_result = self._embed_batch_with_retry(batch, model)

                all_embeddings.extend(batch_result.embeddings)
                all_individual_results.extend(batch_result.individual_results)
                total_tokens += batch_result.total_tokens
                total_time += batch_result.processing_time

            return BatchEmbeddingResult(
                embeddings=all_embeddings,
                total_tokens=total_tokens,
                inputs=texts,
                model=model,
                provider=self.provider_name,
                processing_time=total_time,
                individual_results=all_individual_results,
            )

    def _embed_batch_with_retry(
        self, texts: List[str], model: str
    ) -> BatchEmbeddingResult:
        """Generate batch embeddings with retry logic"""
        for attempt in range(self.max_retries):
            try:
                return self.provider.embed_batch(texts, model)

            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e

                # Exponential backoff
                wait_time = self.retry_delay * (2**attempt)
                logging.warning(
                    f"Batch embedding attempt {attempt + 1} failed, retrying in {wait_time}s: {str(e)}"
                )
                time.sleep(wait_time)

    def _get_cache_key(self, text: str, model: str) -> str:
        """Generate cache key for text and model"""
        content = f"{text}_{model}_{self.provider_name}"
        return hashlib.md5(content.encode()).hexdigest()

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        return self.provider.estimate_tokens(text)

    def estimate_cost(
        self, texts: Union[str, List[str]], model: Optional[str] = None
    ) -> float:
        """Estimate cost for embedding generation (OpenAI only)"""
        if self.provider_name != "openai":
            return 0.0

        model = model or self.default_model
        if model not in self.provider.models:
            return 0.0

        if isinstance(texts, str):
            texts = [texts]

        total_tokens = sum(self.estimate_tokens(text) for text in texts)
        cost_per_1k = self.provider.models[model]["cost_per_1k"]

        return (total_tokens / 1000) * cost_per_1k

    def get_available_models(self) -> List[str]:
        """Get list of available models for current provider"""
        return self.provider.get_available_models()

    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about current provider"""
        return {
            "provider": self.provider_name,
            "default_model": self.default_model,
            "available_models": self.get_available_models(),
            "caching_enabled": self.enable_caching,
            "max_retries": self.max_retries,
        }
