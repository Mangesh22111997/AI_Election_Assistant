"""
backend/models/safety_rules.py
────────────────────────────────
Python representation of the safety policy rules.
Loads and validates data/safety_rules.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class RateLimits(BaseModel):
    anonymous: str = "10 requests/minute"
    authenticated: str = "30 requests/minute"


class HallucinationPrevention(BaseModel):
    require_source_for_deadlines: bool = True
    max_retrieval_contexts: int = 5
    similarity_threshold: float = 0.75


class PolicyRules(BaseModel):
    prohibited_topics: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    rate_limits: RateLimits = Field(default_factory=RateLimits)
    hallucination_prevention: HallucinationPrevention = Field(
        default_factory=HallucinationPrevention
    )


class SafetyRulesConfig(BaseModel):
    policy_rules: PolicyRules = Field(default_factory=PolicyRules)

    @classmethod
    def load(cls, yaml_path: str | Path | None = None) -> "SafetyRulesConfig":
        """Load from a YAML file, falling back to safe defaults."""
        if yaml_path is None:
            yaml_path = Path(__file__).parent / "safety_rules.yaml"

        path = Path(yaml_path)
        if not path.exists():
            return cls()

        with path.open("r", encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        return cls(**raw)
