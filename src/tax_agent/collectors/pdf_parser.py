"""PDF text extraction using PyMuPDF."""

from pathlib import Path

import fitz  # PyMuPDF


class PDFParser:
    """Extract text from PDF documents."""

    def __init__(self, file_path: str | Path):
        """
        Initialize the PDF parser.

        Args:
            file_path: Path to the PDF file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

    def extract_text(self) -> str:
        """
        Extract all text from the PDF.

        Returns:
            Extracted text from all pages
        """
        text_parts: list[str] = []

        with fitz.open(self.file_path) as doc:
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")

        return "\n\n".join(text_parts)

    def extract_text_by_page(self) -> list[str]:
        """
        Extract text from each page separately.

        Returns:
            List of text content per page
        """
        pages: list[str] = []

        with fitz.open(self.file_path) as doc:
            for page in doc:
                pages.append(page.get_text())

        return pages

    def get_page_count(self) -> int:
        """Get the number of pages in the PDF."""
        with fitz.open(self.file_path) as doc:
            return len(doc)

    def is_scanned(self) -> bool:
        """
        Check if the PDF appears to be a scanned document.

        A PDF is likely scanned if it has images but very little text.

        Returns:
            True if the PDF appears to be scanned
        """
        with fitz.open(self.file_path) as doc:
            total_text_len = 0
            total_images = 0

            for page in doc:
                text = page.get_text()
                total_text_len += len(text.strip())
                total_images += len(page.get_images())

            # If there are images but minimal text, it's likely scanned
            if total_images > 0 and total_text_len < 100:
                return True

            # If there's very little text per page on average
            avg_text_per_page = total_text_len / max(len(doc), 1)
            if avg_text_per_page < 50 and total_images > 0:
                return True

            return False

    def extract_images(self) -> list[tuple[int, bytes, str]]:
        """
        Extract images from the PDF for OCR processing.

        Returns:
            List of tuples: (page_number, image_bytes, image_extension)
        """
        images: list[tuple[int, bytes, str]] = []

        with fitz.open(self.file_path) as doc:
            for page_num, page in enumerate(doc):
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    images.append((page_num, image_bytes, image_ext))

        return images

    def render_page_as_image(self, page_num: int = 0, dpi: int = 300) -> bytes:
        """
        Render a page as a PNG image for OCR.

        Args:
            page_num: Page number (0-indexed)
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        with fitz.open(self.file_path) as doc:
            if page_num >= len(doc):
                raise ValueError(f"Page {page_num} does not exist (document has {len(doc)} pages)")

            page = doc[page_num]
            # Calculate zoom factor for desired DPI (72 is default PDF DPI)
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            return pix.tobytes("png")

    def render_all_pages_as_images(self, dpi: int = 300) -> list[bytes]:
        """
        Render all pages as PNG images.

        Args:
            dpi: Resolution for rendering

        Returns:
            List of PNG image bytes for each page
        """
        images: list[bytes] = []

        with fitz.open(self.file_path) as doc:
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            for page in doc:
                pix = page.get_pixmap(matrix=mat)
                images.append(pix.tobytes("png"))

        return images


def extract_pdf_text(file_path: str | Path) -> str:
    """
    Convenience function to extract text from a PDF.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text
    """
    parser = PDFParser(file_path)
    return parser.extract_text()


def is_pdf_scanned(file_path: str | Path) -> bool:
    """
    Check if a PDF appears to be scanned.

    Args:
        file_path: Path to the PDF file

    Returns:
        True if the PDF appears to be scanned
    """
    parser = PDFParser(file_path)
    return parser.is_scanned()
