"""
Vision Parser: Core imaging infrastructure for PDF-to-image conversion and LLM visual analysis.

This module provides centralized utilities to:
1. Convert PDF binary streams into high-resolution Base64-encoded images
2. Perform LLM-based visual analysis to extract structured text/Markdown

Uses the streamlined LiteLLMRouter for all LLM calls, maintaining consistency
with the existing CrewAI orchestration infrastructure.
"""

import base64
import logging
from typing import List

import fitz  # pymupdf
from src.utils.llm_router import LiteLLMRouter

logger = logging.getLogger(__name__)


def render_document_to_images(
    file_stream: bytes,
    max_pages: int = 5,
    max_side: int = 1024,
    quality: int = 85,
) -> List[str]:
    """
    Convert PDF pages into Base64-encoded JPEG images suitable for LLM vision parsing.

    The previous implementation used a fixed DPI which produced extremely large
    images (e.g. A4 @ 300dpi -> ~8.7MP) and caused VRAM/RAM exhaustion when used
    with local models.  To avoid this we calculate a zoom factor per page such that
    *no* page exceeds ``max_side`` pixels on its longest dimension.  By default the
    limit is 1024 pixels (800 is recommended for very lightweight models).

    Images are also aggressively compressed with JPEG quality controlled by the
    ``quality`` parameter (default 85) to reduce payload size.

    Args:
        file_stream: Binary PDF content (bytes).
        max_pages: Maximum number of pages to convert (default: 5).
        max_side: Maximum number of pixels on the longest side of the output image.
        quality: JPEG quality level (1-100, higher is better quality but larger size).

    Returns:
        List of Base64-encoded JPEG strings, one per page.

    Raises:
        ValueError: If ``file_stream`` is empty.
        RuntimeError: If PDF opening or rendering fails, or if no images are generated.
    """
    if not file_stream:
        raise ValueError("file_stream cannot be empty")

    try:
        pdf_document = fitz.open(stream=file_stream, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {str(e)}") from e

    images: List[str] = []
    num_pages = min(len(pdf_document), max_pages)

    for page_num in range(num_pages):
        try:
            page = pdf_document[page_num]

            # Determine scaling such that the longest side is <= max_side
            rect = page.rect
            longest_pt = max(rect.width, rect.height)  # points at 72 dpi
            if longest_pt <= 0:
                raise RuntimeError("Invalid page dimensions encountered")

            # Compute DPI required to hit the target pixel size: pixels = pts * dpi / 72
            target_dpi = max_side * 72.0 / longest_pt
            zoom = target_dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Compress to JPEG with specified quality
            image_bytes = pix.tobytes(output="jpeg", jpg_quality=quality)

            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            images.append(base64_image)

            logger.debug(f"Rendered page {page_num + 1}/{num_pages} with zoom {zoom:.2f}")

        except Exception as e:
            logger.error(f"Failed to render page {page_num + 1}: {str(e)}")
            raise RuntimeError(f"Failed to render page {page_num + 1}: {str(e)}") from e

    pdf_document.close()

    if not images:
        raise RuntimeError("No images were extracted from the PDF")

    logger.info(f"Successfully extracted {len(images)} images from PDF")
    return images


async def vision_extract_text(images: List[str], model: str = "crewai-proxy") -> str:
    """
    Perform LLM-based visual analysis on images to extract structured text (Async).
    """
    if not images:
        raise ValueError("images list cannot be empty")
    
    system_prompt = _get_vision_system_prompt()
    content = _prepare_vision_content(images)
    
    try:
        router = LiteLLMRouter()
        response = await router.acompletion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            temperature=0.2,
            max_tokens=4096
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Successfully extracted text from {len(images)} image(s) using model '{model}' (Async)")
        return extracted_text or ""
        
    except Exception as e:
        logger.error(f"LLM vision call failed: {str(e)}")
        raise RuntimeError(f"Failed to extract text from images: {str(e)}") from e


def vision_extract_text_sync(images: List[str], model: str = "crewai-proxy") -> str:
    """
    Perform LLM-based visual analysis on images to extract structured text (Sync).
    Used by tools that are not yet async-compatible.
    """
    if not images:
        raise ValueError("images list cannot be empty")
    
    system_prompt = _get_vision_system_prompt()
    content = _prepare_vision_content(images)
    
    try:
        router = LiteLLMRouter()
        # Note: LiteLLMRouter should provide a sync completion if needed, 
        # or we use litellm.completion directly if it's initialized.
        import litellm
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            temperature=0.2,
            max_tokens=4096
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Successfully extracted text from {len(images)} image(s) using model '{model}' (Sync)")
        return extracted_text or ""
        
    except Exception as e:
        logger.error(f"LLM vision sync call failed: {str(e)}")
        raise RuntimeError(f"Failed to extract text from images (sync): {str(e)}") from e


def _get_vision_system_prompt() -> str:
    return """You are a document analysis expert. Your task is to carefully analyze the provided image(s) and extract all content in Markdown format.

IMPORTANT FORMATTING RULES:
- Preserve all tables using Markdown table syntax (| column1 | column2 |)
- Use **bold** for emphasized or important text
- Use # for headers, ## for subheaders, ### for sub-subheaders
- Use - or * for bullet points
- Use 1. 2. 3. for numbered lists
- Preserve line breaks and paragraph structure
- Include all numbers, amounts, dates, and special characters exactly as shown

Output ONLY the Markdown content. Do not include introductions or explanations."""


def _prepare_vision_content(images: List[str]) -> List[dict]:
    content = [
        {
            "type": "text",
            "text": "Please analyze this document image and extract all content in Markdown format, preserving tables, bold text, headers, and structure."
        }
    ]
    for image_data in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_data}"
            }
        })
    return content
