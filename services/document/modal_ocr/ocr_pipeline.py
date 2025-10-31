"""
ABOUTME: Modal GPU function for OCR processing using docTR + TrOCR
ABOUTME: Handles typed text (docTR) and handwritten text (TrOCR) with confidence scoring
"""

import modal
import base64
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import numpy as np
from PIL import Image
import io

# Modal app definition (Modal SDK v0.56+ uses App instead of Stub)
app = modal.App("juragpt-ocr")

# GPU image with OCR dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "python-doctr[torch]==0.7.0",  # docTR for typed text
        "transformers==4.36.2",  # TrOCR for handwritten
        "torch==2.1.2",
        "torchvision==0.16.2",
        "pillow==10.2.0",
        "numpy==1.26.3",
    )
)


@dataclass
class OCRRegion:
    """Single OCR region (word/line) with bbox and confidence"""
    text: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2) normalized 0-1
    region_type: str  # 'typed' or 'handwritten'


@dataclass
class PageOCRResult:
    """OCR result for a single page"""
    page_num: int
    regions: List[OCRRegion]
    full_text: str
    avg_confidence: float
    typed_text_pct: float  # % of regions classified as typed
    handwritten_text_pct: float  # % of regions classified as handwritten
    processing_time_ms: int


class OCRPipeline:
    """
    Dual OCR pipeline: docTR for typed text + TrOCR for handwritten text

    Strategy:
    1. Use docTR for layout detection and typed text extraction
    2. Classify regions as typed/handwritten based on confidence
    3. Re-process low-confidence regions with TrOCR (handwriting specialist)
    4. Merge results with per-region confidence scores
    """

    def __init__(self):
        """Initialize OCR models"""
        from doctr.models import ocr_predictor
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        # docTR for typed text (fast, accurate for printed)
        self.doctr_model = ocr_predictor(
            det_arch='db_resnet50',
            reco_arch='crnn_vgg16_bn',
            pretrained=True
        )

        # TrOCR for handwritten text (slower, specialized)
        self.trocr_processor = TrOCRProcessor.from_pretrained(
            'microsoft/trocr-base-handwritten'
        )
        self.trocr_model = VisionEncoderDecoderModel.from_pretrained(
            'microsoft/trocr-base-handwritten'
        )

        # Confidence threshold to trigger handwriting model
        self.typed_confidence_threshold = 0.7

    def process_page(
        self,
        page_image_base64: str,
        page_num: int,
        enable_handwriting: bool = True
    ) -> PageOCRResult:
        """
        Process a single page with dual OCR pipeline

        Args:
            page_image_base64: Base64-encoded PNG image
            page_num: Page number (0-indexed)
            enable_handwriting: Whether to use TrOCR for low-confidence regions

        Returns:
            PageOCRResult with all OCR data
        """
        import time
        start_time = time.time()

        # Decode image
        image_bytes = base64.b64decode(page_image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        image_np = np.array(image)

        # Step 1: Run docTR for initial OCR + layout detection
        doctr_result = self.doctr_model([image_np])

        # Step 2: Extract regions with confidence scores
        regions = []
        typed_count = 0
        handwritten_count = 0

        for page in doctr_result.pages:
            for block in page.blocks:
                for line in block.lines:
                    for word in line.words:
                        text = word.value
                        confidence = word.confidence
                        bbox = word.geometry  # ((x1, y1), (x2, y2)) normalized

                        # Flatten bbox to (x1, y1, x2, y2)
                        bbox_flat = (bbox[0][0], bbox[0][1], bbox[1][0], bbox[1][1])

                        # Classify region type based on confidence
                        if confidence >= self.typed_confidence_threshold:
                            # High confidence = typed text
                            region_type = 'typed'
                            typed_count += 1

                            regions.append(OCRRegion(
                                text=text,
                                confidence=confidence,
                                bbox=bbox_flat,
                                region_type=region_type
                            ))

                        elif enable_handwriting:
                            # Low confidence = try handwriting model
                            handwritten_count += 1

                            # Extract region image for TrOCR
                            x1, y1, x2, y2 = bbox_flat
                            img_w, img_h = image.size

                            crop_box = (
                                int(x1 * img_w),
                                int(y1 * img_h),
                                int(x2 * img_w),
                                int(y2 * img_h)
                            )

                            region_img = image.crop(crop_box)

                            # Run TrOCR on region
                            trocr_text, trocr_conf = self._run_trocr(region_img)

                            # Use better result (TrOCR vs docTR)
                            if trocr_conf > confidence:
                                regions.append(OCRRegion(
                                    text=trocr_text,
                                    confidence=trocr_conf,
                                    bbox=bbox_flat,
                                    region_type='handwritten'
                                ))
                            else:
                                # TrOCR didn't improve, keep docTR result
                                regions.append(OCRRegion(
                                    text=text,
                                    confidence=confidence,
                                    bbox=bbox_flat,
                                    region_type='typed'  # Fallback to typed
                                ))

                        else:
                            # Handwriting disabled, use docTR result
                            typed_count += 1
                            regions.append(OCRRegion(
                                text=text,
                                confidence=confidence,
                                bbox=bbox_flat,
                                region_type='typed'
                            ))

        # Step 3: Combine text and calculate stats
        full_text = ' '.join(r.text for r in regions)
        avg_confidence = np.mean([r.confidence for r in regions]) if regions else 0.0

        total_regions = len(regions)
        typed_pct = (typed_count / total_regions * 100) if total_regions > 0 else 0
        handwritten_pct = (handwritten_count / total_regions * 100) if total_regions > 0 else 0

        processing_time_ms = int((time.time() - start_time) * 1000)

        return PageOCRResult(
            page_num=page_num,
            regions=[asdict(r) for r in regions],  # Serialize for JSON
            full_text=full_text,
            avg_confidence=float(avg_confidence),
            typed_text_pct=typed_pct,
            handwritten_text_pct=handwritten_pct,
            processing_time_ms=processing_time_ms
        )

    def _run_trocr(self, region_image: Image.Image) -> tuple:
        """
        Run TrOCR on a single region

        Args:
            region_image: PIL Image of text region

        Returns:
            (text, confidence) tuple
        """
        import torch

        # Preprocess for TrOCR
        pixel_values = self.trocr_processor(
            region_image,
            return_tensors="pt"
        ).pixel_values

        # Generate text
        with torch.no_grad():
            generated_ids = self.trocr_model.generate(pixel_values)

        # Decode
        text = self.trocr_processor.batch_decode(
            generated_ids,
            skip_special_tokens=True
        )[0]

        # TrOCR doesn't return confidence, use heuristic
        # (Longer text = higher confidence for handwriting)
        confidence = min(0.85, 0.5 + len(text) * 0.05)

        return text, confidence


@app.function(
    image=image,
    gpu="T4",  # NVIDIA T4 GPU (good balance of speed/cost)
    timeout=300,  # 5 minutes max per batch
    container_idle_timeout=120,  # Keep warm for 2 minutes
    secrets=[modal.Secret.from_name("juragpt-secrets")]
)
def ocr_batch(
    pages_base64: List[str],
    enable_handwriting: bool = True
) -> List[Dict]:
    """
    Process a batch of pages with OCR

    Args:
        pages_base64: List of base64-encoded page images
        enable_handwriting: Whether to use TrOCR for handwriting

    Returns:
        List of PageOCRResult dicts
    """
    pipeline = OCRPipeline()
    results = []

    for page_num, page_img_b64 in enumerate(pages_base64):
        result = pipeline.process_page(
            page_image_base64=page_img_b64,
            page_num=page_num,
            enable_handwriting=enable_handwriting
        )
        results.append(asdict(result))

    return results


@app.function(
    image=image,
    gpu="T4",
    timeout=300,
    secrets=[modal.Secret.from_name("juragpt-secrets")]
)
def ocr_single_page(
    page_image_base64: str,
    page_num: int,
    enable_handwriting: bool = True
) -> Dict:
    """
    Process a single page with OCR

    Args:
        page_image_base64: Base64-encoded page image
        page_num: Page number (0-indexed)
        enable_handwriting: Whether to use TrOCR for handwriting

    Returns:
        PageOCRResult dict
    """
    pipeline = OCRPipeline()
    result = pipeline.process_page(
        page_image_base64=page_image_base64,
        page_num=page_num,
        enable_handwriting=enable_handwriting
    )
    return asdict(result)


# Local testing function (not deployed)
if __name__ == "__main__":
    # Test with a sample image
    with modal.enable_output():
        # This runs locally, calling the remote function
        test_image_b64 = "..."  # Add test image
        result = ocr_single_page.remote(
            page_image_base64=test_image_b64,
            page_num=0,
            enable_handwriting=True
        )
        print(result)
