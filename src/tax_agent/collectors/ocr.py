"""OCR processing for scanned tax documents."""

import io
from pathlib import Path
from typing import Literal

from PIL import Image

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

from tax_agent.collectors.pdf_parser import PDFParser


class OCRProcessor:
    """Process images and scanned PDFs using OCR."""

    def __init__(self, engine: Literal["pytesseract"] = "pytesseract"):
        """
        Initialize the OCR processor.

        Args:
            engine: OCR engine to use (currently only pytesseract supported)
        """
        self.engine = engine

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
        return self._ocr_image(image)

    def process_image_bytes(self, image_bytes: bytes) -> str:
        """
        Extract text from image bytes.

        Args:
            image_bytes: Image data as bytes

        Returns:
            Extracted text
        """
        image = Image.open(io.BytesIO(image_bytes))
        return self._ocr_image(image)

    def process_pdf(self, pdf_path: str | Path) -> str:
        """
        Extract text from a scanned PDF using OCR.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text from all pages
        """
        parser = PDFParser(pdf_path)
        page_images = parser.render_all_pages_as_images(dpi=300)

        text_parts: list[str] = []
        for page_num, image_bytes in enumerate(page_images):
            page_text = self.process_image_bytes(image_bytes)
            if page_text.strip():
                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        return "\n\n".join(text_parts)

    def _ocr_image(self, image: Image.Image) -> str:
        """
        Run OCR on a PIL Image.

        Args:
            image: PIL Image object

        Returns:
            Extracted text
        """
        if self.engine == "pytesseract":
            # Configure for best accuracy with tax documents
            config = r"--oem 3 --psm 6"
            return pytesseract.image_to_string(image, config=config)
        else:
            raise ValueError(f"Unknown OCR engine: {self.engine}")

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
