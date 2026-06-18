import hashlib
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class OpportunityCard(BaseModel):
    headline: str = Field(max_length=240)
    business_problem: str = Field(max_length=1200)
    evidence_summary: str = Field(max_length=1600)
    interpretation: str = Field(max_length=1600)
    recommended_action: str = Field(max_length=1200)
    alternative_actions: list[str] = Field(default_factory=list, max_length=5)
    experiment_suggestion: Optional[str] = Field(default=None, max_length=1200)
    risks: list[str] = Field(default_factory=list, max_length=8)
    confidence_explanation: str = Field(max_length=1000)
    required_human_checks: list[str] = Field(default_factory=list, max_length=8)


class GenerationResult(BaseModel):
    card: Optional[OpportunityCard] = None
    provider: str
    model: Optional[str] = None
    prompt_version: str
    evidence_hash: str
    validation_result: str
    latency_ms: int = 0
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None


class AIProvider(ABC):
    @abstractmethod
    def generate_opportunity_card(self, evidence: dict) -> GenerationResult:
        raise NotImplementedError


class DisabledAIProvider(AIProvider):
    def generate_opportunity_card(self, evidence: dict) -> GenerationResult:
        evidence_hash = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        return GenerationResult(
            provider="disabled",
            prompt_version="opportunity-card-v1",
            evidence_hash=evidence_hash,
            validation_result="skipped",
            error="OPENAI_API_KEY is not configured",
        )


class OpenAIProvider(AIProvider):
    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        self.model = os.getenv("OPENAI_OPPORTUNITY_MODEL", "gpt-4o-mini")

    def generate_opportunity_card(self, evidence: dict) -> GenerationResult:
        prompt_version = "opportunity-card-v1"
        serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        evidence_hash = hashlib.sha256(serialized.encode()).hexdigest()
        started = time.monotonic()
        try:
            completion = self.client.chat.completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Explain a restaurant revenue opportunity using only the supplied verified evidence. "
                            "Do not calculate or invent revenue, rates, prices, margins, significance, eligibility, "
                            "or order totals. Preserve the evidence values exactly and require human review for actions."
                        ),
                    },
                    {"role": "user", "content": serialized},
                ],
                response_format=OpportunityCard,
            )
            message = completion.choices[0].message
            if message.refusal:
                raise ValueError(message.refusal)
            card = message.parsed
            if card is None:
                raise ValueError("OpenAI returned no validated opportunity card")
            usage = completion.usage
            return GenerationResult(
                card=card,
                provider="openai",
                model=self.model,
                prompt_version=prompt_version,
                evidence_hash=evidence_hash,
                validation_result="valid",
                latency_ms=int((time.monotonic() - started) * 1000),
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
            )
        except Exception as exc:
            return GenerationResult(
                provider="openai",
                model=self.model,
                prompt_version=prompt_version,
                evidence_hash=evidence_hash,
                validation_result="error",
                latency_ms=int((time.monotonic() - started) * 1000),
                error=str(exc)[:2000],
            )


def get_ai_provider() -> AIProvider:
    if not os.getenv("OPENAI_API_KEY"):
        return DisabledAIProvider()
    try:
        return OpenAIProvider()
    except Exception:
        return DisabledAIProvider()
