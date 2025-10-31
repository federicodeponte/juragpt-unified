"""
ABOUTME: Gemini 2.5 Flash API client for legal document analysis
ABOUTME: Implements cite-first prompting and structured output generation
"""

import time
from typing import Dict, Optional

import google.generativeai as genai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.utils.logging import logger


class GeminiClient:
    """
    Gemini 2.5 Flash client optimized for German legal documents
    Uses cite-first prompting to ensure accurate citations
    """

    # System prompt for legal analysis
    LEGAL_ANALYSIS_PROMPT = """You are a precise German legal document analyst.

**CRITICAL RULES:**
1. **ONLY use information from the provided sections below**
2. **ALWAYS cite section numbers (§X, Absatz Y, etc.) BEFORE making ANY claim**
3. **If information is NOT in provided sections, explicitly state: "Not found in provided sections"**
4. **Format every statement as: "According to [§X.Y / Absatz Z]: [your statement]"**
5. **Never paraphrase legal text - quote directly when possible**
6. **Never invent or assume information not explicitly stated**
7. **Wenn mehrere Abschnitte relevant sind, zitiere alle**

**RESPONSE FORMAT:**
- Start each point with a citation
- Be concise but complete
- Use bullet points for clarity
- Flag any ambiguities or missing information

---

**PROVIDED SECTIONS:**

{context}

---

**USER QUESTION:**

{query}

**YOUR ANALYSIS:**
"""

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """Initialize Gemini client with optional EU endpoint"""
        api_key = api_key or settings.gemini_api_key
        endpoint = endpoint or settings.gemini_endpoint

        # Configure with regional endpoint support
        if endpoint != "https://generativelanguage.googleapis.com":
            # Custom endpoint (e.g., EU region)
            import os

            os.environ["GOOGLE_API_ENDPOINT"] = endpoint

        genai.configure(api_key=api_key)

        # Configure model
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config={  # type: ignore[arg-type]
                "temperature": settings.gemini_temperature,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            },
            safety_settings={  # type: ignore[arg-type]
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            },
        )

        logger.info(
            f"Initialized Gemini client with model: {settings.gemini_model}, endpoint: {endpoint}"
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def analyze(self, query: str, context: str, request_id: Optional[str] = None) -> Dict:
        """Analyze query with retry logic"""
        prompt = self.LEGAL_ANALYSIS_PROMPT.format(context=context, query=query)
        start_time = time.time()

        try:
            response = self.model.generate_content(prompt)
            latency_ms = int((time.time() - start_time) * 1000)
            answer = response.text or ""

            tokens_used = None
            if hasattr(response, "usage_metadata"):
                tokens_used = (
                    response.usage_metadata.prompt_token_count
                    + response.usage_metadata.candidates_token_count
                )

            logger.info(
                "Gemini analysis completed",
                extra={
                    "request_id": request_id,
                    "latency_ms": latency_ms,
                    "tokens_used": tokens_used,
                },
            )

            return {
                "answer": answer,
                "latency_ms": latency_ms,
                "tokens_used": tokens_used,
                "model_version": settings.gemini_model,
            }
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}", extra={"request_id": request_id})
            raise GeminiAPIError(f"Failed to generate response: {str(e)}")

    def verify_answer(self, answer: str, context: str, request_id: Optional[str] = None) -> Dict:
        """Verify answer is supported by context"""
        verification_prompt = f"""Fact-check: Identify unsupported claims in ANSWER vs CONTEXT.

CONTEXT: {context}

ANSWER: {answer}

If all supported: "✓ All statements supported"
Else list: "- Unsupported claim: [quote]"
"""
        try:
            response = self.model.generate_content(verification_prompt)
            result = response.text or ""
            is_supported = "✓ All statements supported" in result

            logger.info(
                f"Verification: {'PASS' if is_supported else 'FAIL'}",
                extra={"request_id": request_id},
            )

            return {"is_supported": is_supported, "verification_details": result}
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            return {"is_supported": False, "verification_details": f"Error: {str(e)}"}


class GeminiAPIError(Exception):
    """Custom exception for Gemini API errors"""

    pass


# Global instance
gemini_client = GeminiClient()
