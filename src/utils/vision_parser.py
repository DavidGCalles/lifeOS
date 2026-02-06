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
    dpi: int = 300
) -> List[str]:
    """
    Convert PDF pages into high-resolution Base64-encoded JPEG images.
    
    Args:
        file_stream: Binary PDF content (bytes)
        max_pages: Maximum number of pages to convert (default: 5)
        dpi: Resolution in dots per inch (default: 300 for high-res)
    
    Returns:
        List of Base64-encoded JPEG strings, one per page.
        
    Raises:
        ValueError: If file_stream is empty or not a valid PDF
        RuntimeError: If PDF rendering fails
    
    Example:
        >>> with open("document.pdf", "rb") as f:
        >>>     images = render_document_to_images(f.read(), max_pages=3)
        >>> print(f"Extracted {len(images)} images")
    """
    if not file_stream:
        raise ValueError("file_stream cannot be empty")
    
    try:
        # Open PDF from binary stream
        pdf_document = fitz.open(stream=file_stream, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {str(e)}") from e
    
    images = []
    num_pages = min(len(pdf_document), max_pages)
    
    # Convert zoom factor to match DPI (standard is 72 DPI)
    zoom_factor = dpi / 72.0
    mat = fitz.Matrix(zoom_factor, zoom_factor)
    
    for page_num in range(num_pages):
        try:
            page = pdf_document[page_num]
            
            # Render page to high-resolution image (JPEG)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert pixmap to JPEG bytes
            image_bytes = pix.tobytes(output="jpeg", jpg_quality=95)
            
            # Encode to Base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            images.append(base64_image)
            
            logger.debug(f"Successfully rendered page {page_num + 1}/{num_pages}")
            
        except Exception as e:
            logger.error(f"Failed to render page {page_num + 1}: {str(e)}")
            raise RuntimeError(f"Failed to render page {page_num + 1}: {str(e)}") from e
    
    pdf_document.close()
    
    if not images:
        raise RuntimeError("No images were extracted from the PDF")
    
    logger.info(f"Successfully extracted {len(images)} images from PDF")
    return images


def vision_extract_text(images: List[str], model: str = "crewai-proxy") -> str:
    """
    Perform LLM-based visual analysis on images to extract structured text.
    
    Converts images to Markdown format with preserved tables, bold text, and headers.
    Uses LiteLLMRouter for consistent LLM orchestration.
    
    Args:
        images: List of Base64-encoded image strings
        model: LLM model identifier (default: crewai-proxy)
    
    Returns:
        Extracted text in Markdown format with preserved structure.
    
    Raises:
        ValueError: If images list is empty
        RuntimeError: If LLM call fails
    
    Example:
        >>> images = render_document_to_images(pdf_bytes)
        >>> markdown_text = vision_extract_text(images)
        >>> print(markdown_text)
    """
    if not images:
        raise ValueError("images list cannot be empty")
    
    # System prompt to ensure Markdown-formatted output
    system_prompt = """You are a document analysis expert. Your task is to carefully analyze the provided image(s) and extract all content in Markdown format.

IMPORTANT FORMATTING RULES:
- Preserve all tables using Markdown table syntax (| column1 | column2 |)
- Use **bold** for emphasized or important text
- Use # for headers, ## for subheaders, ### for sub-subheaders
- Use - or * for bullet points
- Use 1. 2. 3. for numbered lists
- Preserve line breaks and paragraph structure
- Include all numbers, amounts, dates, and special characters exactly as shown

Output ONLY the Markdown content. Do not include introductions or explanations."""

    # Prepare image content for vision-capable LLM
    content = [
        {
            "type": "text",
            "text": "Please analyze this document image and extract all content in Markdown format, preserving tables, bold text, headers, and structure."
        }
    ]
    
    # Add each image as a vision message
    for image_data in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{image_data}"
            }
        })
    
    try:
        # Use LiteLLMRouter for consistent orchestration
        router = LiteLLMRouter()
        response = router.completion(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=0.2,  # Lower temperature for consistent, accurate extraction
            max_tokens=4096
        )
        
        extracted_text = response.choices[0].message.content
        logger.info(f"Successfully extracted text from {len(images)} image(s) using model '{model}'")
        return extracted_text
        
    except Exception as e:
        logger.error(f"LLM vision call failed: {str(e)}")
        raise RuntimeError(f"Failed to extract text from images: {str(e)}") from e
