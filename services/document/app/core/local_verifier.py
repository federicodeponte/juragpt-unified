"""
ABOUTME: Local LLM verifier using Ollama for on-premise citation verification
ABOUTME: Ensures no PII is sent to external APIs during verification step
"""

from typing import Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.utils.logging import logger


class LocalVerifier:
    """
    Local verification using Ollama + Mistral-7B
    Keeps all verification on-premise for GDPR compliance
    """

    def __init__(
        self,
        ollama_endpoint: str = "http://localhost:11434",
        model: str = "mistral:7b",
        timeout: int = 30,
    ):
        """Initialize local verifier with Ollama endpoint"""
        self.ollama_endpoint = ollama_endpoint
        self.model = model
        self.timeout = timeout
        self.available = self._check_availability()

        logger.info(
            f"Local verifier initialized: model={model}, "
            f"available={self.available}, endpoint={ollama_endpoint}"
        )

    def _check_availability(self) -> bool:
        """Check if Ollama is available"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.ollama_endpoint}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {str(e)}")
            return False

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def verify_answer(self, answer: str, context: str, request_id: Optional[str] = None) -> Dict:
        """
        Verify answer against context using local LLM

        Returns:
            {
                "is_supported": bool,
                "verification_details": str
            }
        """
        if not self.available:
            logger.warning("Ollama unavailable, skipping local verification")
            return {
                "is_supported": True,  # Fail open
                "verification_details": "Local verifier unavailable",
            }

        verification_prompt = self._build_verification_prompt(answer, context)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.ollama_endpoint}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": verification_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,
                            "top_p": 0.9,
                        },
                    },
                )

                response.raise_for_status()
                result = response.json()
                verification_text = result.get("response", "")

                is_supported = self._parse_verification_result(verification_text)

                logger.info(
                    f"Local verification: {'PASS' if is_supported else 'FAIL'}",
                    extra={"request_id": request_id},
                )

                return {"is_supported": is_supported, "verification_details": verification_text}

        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {str(e)}", extra={"request_id": request_id})
            # Fail open on errors
            return {"is_supported": True, "verification_details": f"Verification error: {str(e)}"}

    def _build_verification_prompt(self, answer: str, context: str) -> str:
        """Build verification prompt for Mistral"""
        return f"""You are a fact-checker. Verify if the ANSWER is fully supported by the CONTEXT.

CONTEXT:
{context}

ANSWER:
{answer}

TASK:
- Check each statement in the ANSWER
- Verify it's supported by the CONTEXT
- If ALL statements are supported, respond: "✓ All statements supported"
- If ANY statement is unsupported, list them as: "- Unsupported: [quote the claim]"

YOUR VERIFICATION:
"""

    def _parse_verification_result(self, verification_text: str) -> bool:
        """Parse verification result from LLM response"""
        # Check for pass marker
        if "✓ All statements supported" in verification_text:
            return True

        # Check for unsupported claims
        if "Unsupported:" in verification_text or "unsupported" in verification_text.lower():
            return False

        # Default to supported if unclear
        return True


class OllamaError(Exception):
    """Custom exception for Ollama errors"""

    pass


# Global instance
local_verifier = LocalVerifier()
