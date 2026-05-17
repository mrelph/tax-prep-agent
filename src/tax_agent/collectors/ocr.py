"""OCR processing for scanned tax documents.

This module provides high-accuracy text extraction from tax documents using:
1. Image preprocessing (deskew, contrast, noise removal)
2. Tesseract OCR with optimized settings for tax forms
3. Claude Vision as fallback for low-confidence extractions
"""

import io
import logging
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from tax_agent.collectors.pdf_parser import PDFParser

logger = logging.getLogger(__name__)


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for optimal OCR accuracy.

    Applies:
    - Grayscale conversion
    - Contrast enhancement
    - Sharpening
    - Noise reduction
    - Deskewing (if significant skew detected)

    Args:
        image: PIL Image to preprocess

    Returns:
        Preprocessed PIL Image
    """
    # Convert to grayscale if not already
    if image.mode != "L":
        image = image.convert("L")

    # Enhance contrast (tax forms often have light printing)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(1.5)

    # Sharpen to improve text clarity
    image = image.filter(ImageFilter.SHARPEN)

    # Apply slight denoise
    image = image.filter(ImageFilter.MedianFilter(size=1))

    # Resize if too small (OCR works better on larger images)
    min_dimension = 1500
    width, height = image.size
    if width < min_dimension or height < min_dimension:
        scale = max(min_dimension / width, min_dimension / height)
        new_size = (int(width * scale), int(height * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)

    return image


def detect_and_fix_skew(image: Image.Image) -> Image.Image:
    """
    Detect and correct image skew for better OCR.

    Args:
        image: PIL Image

    Returns:
        Deskewed image
    """
    try:
        import numpy as np

        # Convert to numpy array
        img_array = np.array(image)

        # Use Tesseract's OSD (Orientation and Script Detection)
        if TESSERACT_AVAILABLE:
            try:
                osd = pytesseract.image_to_osd(image, output_type=pytesseract.Output.DICT)
                angle = osd.get("rotate", 0)
                if abs(angle) > 0.5:  # Only rotate if skew is significant
                    logger.debug(f"Detected skew of {angle} degrees, correcting...")
                    image = image.rotate(-angle, expand=True, fillcolor=255)
            except Exception:
                pass  # OSD can fail on some images

        return image
    except ImportError:
        return image  # numpy not available


class OCRProcessor:
    """Process images and scanned PDFs using OCR with preprocessing."""

    def __init__(
        self,
        engine: Literal["pytesseract"] = "pytesseract",
        preprocess: bool = True,
        use_vision_fallback: bool = True,
    ):
        """
        Initialize the OCR processor.

        Args:
            engine: OCR engine to use (currently only pytesseract supported)
            preprocess: Whether to apply image preprocessing
            use_vision_fallback: Use Claude Vision for low-confidence results
        """
        self.engine = engine
        self.preprocess = preprocess
        self.use_vision_fallback = use_vision_fallback

        if engine == "pytesseract" and not TESSERACT_AVAILABLE:
            raise ImportError(
                "pytesseract is not installed. Install it with: pip install pytesseract\n"
                "You also need to install Tesseract OCR: https://github.com/tesseract-ocr/tesseract"
            )

    def process_image(self, image_path: str | Path) -> str:
        """
        Extract text from an image file.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text
        """
        image = Image.open(image_path)
        text, confidence = self._ocr_image(image)

        # Use Claude Vision fallback for low confidence
        if confidence < 0.6 and self.use_vision_fallback:
            vision_text = self._extract_with_vision(image_path)
            if vision_text and len(vision_text) > len(text) * 0.5:
                logger.info(f"Using Vision API result (OCR confidence: {confidence:.0%})")
                return vision_text

        return text

    def process_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extract text from image bytes.

        Args:
            image_bytes: Image data as bytes

        Returns:
            Extracted text
        """
        image = Image.open(io.BytesIO(image_bytes))
        text, confidence = self._ocr_image(image)

        # For bytes, we can't easily use Vision API fallback
        # Just return with a warning if low confidence
        if confidence < 0.6:
            logger.warning(f"Low OCR confidence ({confidence:.0%}) for image")

        return text

    def _extract_with_vision(self, image_path: str | Path) -> str | None:
        """
        Use Claude Vision API to extract text from an image.

        This is a fallback for when OCR confidence is low.

        Args:
            image_path: Path to the image file

        Returns:
            Extracted text or None if Vision API unavailable
        """
        try:
            from tax_agent.agent import get_agent
            import base64

            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.standard_b64encode(f.read()).decode("utf-8")

            # Determine media type
            suffix = Path(image_path).suffix.lower()
            media_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            media_type = media_types.get(suffix, "image/png")

            agent = get_agent()

            # Use Claude's vision capability
            response = agent.client.messages.create(
                model=agent.model,
                max_tokens=4000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Extract ALL text from this tax document. Preserve the layout and structure as much as possible. Include all numbers, names, addresses, and form field labels. Return only the extracted text, no commentary.",
                            },
                        ],
                    }
                ],
            )

            return response.content[0].text

        except Exception as e:
            logger.debug(f"Vision API extraction failed: {e}")
            return None

    def process_pdf(self, pdf_path: str | Path) -> str:
        """
        Extract text from a scanned PDF using OCR.

        Uses higher DPI for better accuracy and processes each page
        with preprocessing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text from all pages
        """
        parser = PDFParser(pdf_path)
        # Use 400 DPI for better accuracy (higher than default 300)
        page_images = parser.render_all_pages_as_images(dpi=400)

        text_parts: list[str] = []
        total_confidence = 0.0
        page_count = 0

        for page_num, image_bytes in enumerate(page_images):
            image = Image.open(io.BytesIO(image_bytes))
            page_text, confidence = self._ocr_image(image)

            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                total_confidence += confidence
                page_count += 1

        avg_confidence = total_confidence / page_count if page_count > 0 else 0.0

        # Log overall confidence
        if avg_confidence < 0.7:
            logger.warning(
                f"Low overall OCR confidence ({avg_confidence:.0%}) for {pdf_path}. "
                "Consider using a higher quality scan."
            )

        return "\n\n".join(text_parts)

    def _ocr_image(self, image: Image.Image) -> tuple[str, float]:
        """
        Run OCR on a PIL Image with preprocessing.

        Args:
            image: PIL Image object

        Returns:
            Tuple of (extracted text, confidence score 0-1)
        """
        # Apply preprocessing if enabled
        if self.preprocess:
            image = preprocess_image(image)
            image = detect_and_fix_skew(image)

        if self.engine == "pytesseract":
            # Optimized config for tax documents:
            # --oem 3: Use LSTM neural net (most accurate)
            # --psm 6: Assume uniform block of text (good for forms)
            # -c preserve_interword_spaces=1: Keep spacing for tabular data
            config = r"--oem 3 --psm 6 -c preserve_interword_spaces=1"

            # Get text with confidence data
            try:
                data = pytesseract.image_to_data(
                    image, config=config, output_type=pytesseract.Output.DICT
                )

                # Calculate average confidence (excluding -1 which means no text)
                confidences = [c for c in data["conf"] if c > 0]
                avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

                # Get the text
                text = pytesseract.image_to_string(image, config=config)

                return text, avg_confidence

            except Exception as e:
                logger.warning(f"OCR with confidence failed, falling back: {e}")
                text = pytesseract.image_to_string(image, config=config)
                return text, 0.5  # Unknown confidence
        else:
            raise ValueError(f"Unknown OCR engine: {self.engine}")

    def _ocr_image_legacy(self, image: Image.Image) -> str:
        """Legacy OCR method for backward compatibility."""
        text, _ = self._ocr_image(image)
        return text

    def process_file(self, file_path: str | Path) -> str:
        """
        Process any supported file type (PDF or image).

        Args:
            file_path: Path to the file

        Returns:
            Extracted text
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            # Check if PDF is scanned or has extractable text
            parser = PDFParser(file_path)
            if parser.is_scanned():
                return self.process_pdf(file_path)
            else:
                # Try native extraction first
                text = parser.extract_text()
                if len(text.strip()) > 100:
                    return text
                # Fall back to OCR if native extraction yielded little text
                return self.process_pdf(file_path)

        elif suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"):
            return self.process_image(file_path)

        else:
            raise ValueError(f"Unsupported file type: {suffix}")


def extract_text_with_ocr(file_path: str | Path) -> str:
    """
    Convenience function to extract text from any supported file.

    Uses native PDF extraction when possible, falls back to OCR.

    Args:
        file_path: Path to PDF or image file

    Returns:
        Extracted text
    """
    processor = OCRProcessor()
    return processor.process_file(file_path)
