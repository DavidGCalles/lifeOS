import io
import base64
import time

import pytest
from PIL import Image
import fitz  # pymupdf

from src.utils.vision_parser import render_document_to_images


def _create_simple_pdf(width_pt: float = 595, height_pt: float = 842) -> bytes:
    """Return binary content of a one-page PDF with a bit of text."""
    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    page.insert_text((72, 72), "Hello PDF")
    return doc.write()


def test_render_document_respects_max_side_and_quality():
    pdf_bytes = _create_simple_pdf()

    # render with a relatively small max_side so we can assert on the image dimensions
    images = render_document_to_images(pdf_bytes, max_pages=1, max_side=800, quality=85)
    assert len(images) == 1

    img_bytes = base64.b64decode(images[0])
    with Image.open(io.BytesIO(img_bytes)) as img:
        assert max(img.size) <= 800, f"Longest side should be <=800 but was {img.size}"

    # higher quality should produce a larger byte size
    images_high = render_document_to_images(pdf_bytes, max_pages=1, max_side=800, quality=95)
    low_size = len(img_bytes)
    high_size = len(base64.b64decode(images_high[0]))
    assert high_size > low_size, "Expected higher quality images to be larger in bytes"


def test_render_document_latency_is_reasonable():
    pdf_bytes = _create_simple_pdf()
    start = time.time()
    _ = render_document_to_images(pdf_bytes, max_pages=2, max_side=1024, quality=85)
    elapsed = time.time() - start
    # should complete well under 5 seconds for a small PDF
    assert elapsed < 5, f"Rendering took too long: {elapsed:.2f}s"


def test_render_document_invalid_stream_raises():
    with pytest.raises(ValueError):
        render_document_to_images(b"", max_pages=1)

