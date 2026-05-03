"""
Multi-Agent Pipeline Coordinator
Responsible for orchestrating the flow between Guide, Simplifier, and Safety agents
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import re

class AgentState(Enum):
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass
class PipelineContext:
    user_query: str
    sanitized_query: str
    detected_language: str
    intent: Optional[str]
    retrieved_context: Optional[str]
    guide_response: Optional[str]
    simplified_response: Optional[str]
    safety_checks_passed: bool
    final_response: Optional[str]
    sources: list
    latency_ms: int

class OrchestratorAgent:
    """
    Coordinates the multi-agent pipeline:
    1. Input validation & PII Scrubbing
    2. Safety check (inbound)
    3. Guide agent (RAG)
    4. Simplifier agent (accessibility)
    5. Safety check (outbound)
    6. Response delivery
    """
    
    def __init__(self, guide_agent, simplifier_agent, safety_monitor):
        self.guide_agent = guide_agent
        self.simplifier_agent = simplifier_agent
        self.safety_monitor = safety_monitor
        self.state = AgentState.INITIALIZED
    
    async def process(self, user_query: str, language: str = "en") -> Dict[str, Any]:
        """Main orchestration pipeline"""
        start_time = time.time()
        
        context = PipelineContext(
            user_query=user_query,
            sanitized_query=self._sanitize_input(user_query),
            detected_language=language,
            intent=None,
            retrieved_context=None,
            guide_response=None,
            simplified_response=None,
            safety_checks_passed=False,
            final_response=None,
            sources=[],
            latency_ms=0
        )
        
        # Step 1: Inbound Safety Check
        self.state = AgentState.PROCESSING
        is_safe, violation = self.safety_monitor.check_query_safety(context.sanitized_query)
        
        if not is_safe:
            return {
                "response": f"I cannot answer that question. {violation}",
                "sources": [],
                "safety_blocked": True,
                "violation_type": violation
            }
        
        # Step 2: Guide Agent (RAG + Intent)
        guide_result = await self.guide_agent.process(context.sanitized_query)
        context.intent = guide_result.get("intent")
        context.retrieved_context = guide_result.get("context")
        context.guide_response = guide_result.get("response")
        context.sources = guide_result.get("sources", [])
        
        # Step 3: Simplifier Agent (if needed)
        if self._needs_simplification(context.guide_response):
            context.simplified_response = await self.simplifier_agent.simplify(
                context.guide_response,
                target_language=language
            )
        else:
            context.simplified_response = context.guide_response
        
        # Step 4: Outbound Safety Check
        is_safe_outbound, outbound_violation = self.safety_monitor.check_response_safety(
            context.simplified_response
        )
        
        if not is_safe_outbound:
            return {
                "response": "I apologize, but my response was blocked by safety filters. Please rephrase your question.",
                "sources": [],
                "safety_blocked": True,
                "violation_type": outbound_violation
            }
        
        # Step 5: Final Assembly
        context.final_response = self._add_disclaimer(context.simplified_response)
        context.safety_checks_passed = True
        context.latency_ms = int((time.time() - start_time) * 1000)
        
        return {
            "response": context.final_response,
            "sources": context.sources,
            "intent": context.intent,
            "latency_ms": context.latency_ms,
            "safety_blocked": False,
            "language": language
        }
    
    def _sanitize_input(self, query: str) -> str:
        """Remove PII and dangerous patterns"""
        # Remove potential PII patterns
        patterns = [
            (r'\b\d{12}\b', '[REDACTED-AADHAAR]'),  # Aadhaar
            (r'\b\d{10}\b', '[REDACTED-PHONE]'),     # Phone number
            (r'[A-Z]{3}[A-Z0-9]{4}[A-Z]{1}', '[REDACTED-VOTER-ID]'),  # Voter ID
        ]
        sanitized = query
        for pattern, replacement in patterns:
            sanitized = re.sub(pattern, replacement, sanitized)
        return sanitized[:500]  # Length limit
    
    def _needs_simplification(self, text: str) -> bool:
        """Check reading level - simplify if complex or long"""
        words_per_sentence = len(text.split()) / max(text.count('.'), 1)
        return words_per_sentence > 20 or len(text) > 300
    
    def _add_disclaimer(self, response: str) -> str:
        """Add mandatory policy disclaimer"""
        disclaimer = "\n\n---\n🤖 *AI-generated educational content. Always verify with your local election office.*"
        return response + disclaimer
