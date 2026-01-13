"""Document classification and data extraction orchestration."""

import uuid
from datetime import datetime
from pathlib import Path

from tax_agent.agent import get_agent
from tax_agent.collectors.ocr import extract_text_with_ocr
from tax_agent.config import get_config
from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.storage.database import get_database
from tax_agent.storage.encryption import hash_file, redact_sensitive_data


class DocumentCollector:
    """Collects and processes tax documents."""

    def __init__(self):
        """Initialize the document collector."""
        self.agent = get_agent()
        self.config = get_config()

    def process_file(self, file_path: str | Path, tax_year: int | None = None) -> TaxDocument:
        """
        Process a tax document file.

        Args:
            file_path: Path to the PDF or image file
            tax_year: Tax year (defaults to config)

        Returns:
            Processed TaxDocument
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        tax_year = tax_year or self.config.tax_year

        # Extract text from the document
        raw_text = extract_text_with_ocr(file_path)

        # Compute file hash for deduplication
        file_hash = hash_file(str(file_path))

        # Check for duplicate
        db = get_database()
        existing = db.get_documents(tax_year=tax_year)
        for doc in existing:
            if doc.file_hash == file_hash:
                raise ValueError(
                    f"Document already exists: {doc.issuer_name} ({doc.document_type.value})"
                )

        # Optionally redact sensitive data before sending to AI
        text_for_analysis = raw_text
        if self.config.get("auto_redact_ssn", True):
            text_for_analysis = redact_sensitive_data(raw_text)

        # Classify the document using Claude
        classification = self.agent.classify_document(text_for_analysis)

        doc_type_str = classification.get("document_type", "UNKNOWN")
        try:
            doc_type = DocumentType(doc_type_str)
        except ValueError:
            doc_type = DocumentType.UNKNOWN

        # Extract structured data based on document type
        extracted_data = self._extract_data(doc_type, text_for_analysis)

        # Verify extracted data against source document
        from tax_agent.verification import verify_extraction
        verification = verify_extraction(doc_type.value, extracted_data, raw_text)

        # Use tax year from classification if available
        classified_year = classification.get("tax_year")
        if classified_year and isinstance(classified_year, int):
            tax_year = classified_year

        # Determine if review is needed based on classification AND verification
        needs_review = (
            classification.get("confidence", 0.0) < 0.8
            or doc_type == DocumentType.UNKNOWN
            or not verification.get("verified", True)
            or verification.get("confidence", 1.0) < 0.7
        )

        # Combine confidence scores
        classification_conf = classification.get("confidence", 0.0)
        verification_conf = verification.get("confidence", 1.0)
        combined_confidence = (classification_conf + verification_conf) / 2

        # Create the document
        document = TaxDocument(
            id=str(uuid.uuid4()),
            tax_year=tax_year,
            document_type=doc_type,
            issuer_name=classification.get("issuer_name", "Unknown"),
            issuer_ein=extracted_data.get("employer_ein") or extracted_data.get("payer_ein"),
            recipient_ssn_last4=extracted_data.get("employee_ssn_last4") or extracted_data.get("recipient_ssn_last4"),
            raw_text=raw_text,
            extracted_data=extracted_data,
            file_path=str(file_path.absolute()),
            file_hash=file_hash,
            confidence_score=combined_confidence,
            needs_review=needs_review,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Save to database
        db.save_document(document)

        return document

    def _extract_data(self, doc_type: DocumentType, text: str) -> dict:
        """
        Extract structured data based on document type.

        Args:
            doc_type: Type of document
            text: Document text

        Returns:
            Extracted data dictionary
        """
        if doc_type == DocumentType.W2:
            return self.agent.extract_w2_data(text)
        elif doc_type == DocumentType.FORM_1099_INT:
            return self.agent.extract_1099_int_data(text)
        elif doc_type == DocumentType.FORM_1099_DIV:
            return self.agent.extract_1099_div_data(text)
        elif doc_type == DocumentType.FORM_1099_B:
            return self.agent.extract_1099_b_data(text)
        else:
            # For other types, just return the classification info
            return {}

    def process_directory(
        self,
        directory: str | Path,
        tax_year: int | None = None,
    ) -> list[tuple[Path, TaxDocument | Exception]]:
        """
        Process all supported files in a directory.

        Args:
            directory: Path to directory
            tax_year: Tax year (defaults to config)

        Returns:
            List of (file_path, result) tuples where result is TaxDocument or Exception
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        results: list[tuple[Path, TaxDocument | Exception]] = []
        supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

        for file_path in directory.iterdir():
            if file_path.suffix.lower() in supported_extensions:
                try:
                    doc = self.process_file(file_path, tax_year)
                    results.append((file_path, doc))
                except Exception as e:
                    results.append((file_path, e))

        return results

    def process_google_drive_folder(
        self,
        folder_id: str,
        tax_year: int | None = None,
        recursive: bool = False,
    ) -> list[tuple[str, TaxDocument | Exception]]:
        """
        Process all supported files from a Google Drive folder.

        Args:
            folder_id: Google Drive folder ID
            tax_year: Tax year (defaults to config)
            recursive: If True, include files from subfolders

        Returns:
            List of (filename, result) tuples where result is TaxDocument or Exception
        """
        from tax_agent.collectors.google_drive import get_google_drive_collector

        tax_year = tax_year or self.config.tax_year
        drive_collector = get_google_drive_collector()

        if not drive_collector.is_authenticated():
            raise ValueError(
                "Not authenticated with Google Drive. "
                "Run 'tax-agent drive-auth' first."
            )

        # Get list of files
        files = drive_collector.list_files(folder_id, recursive=recursive)

        results: list[tuple[str, TaxDocument | Exception]] = []

        for drive_file in files:
            try:
                # Download to temp file
                temp_path = drive_collector.download_to_temp_file(drive_file)

                try:
                    # Process through standard pipeline
                    doc = self.process_file(temp_path, tax_year)
                    results.append((drive_file.name, doc))
                finally:
                    # Clean up temp file
                    temp_path.unlink(missing_ok=True)

            except Exception as e:
                results.append((drive_file.name, e))

        return results


def collect_document(file_path: str | Path, tax_year: int | None = None) -> TaxDocument:
    """
    Convenience function to collect a single document.

    Args:
        file_path: Path to the document
        tax_year: Tax year (optional)

    Returns:
        Processed TaxDocument
    """
    collector = DocumentCollector()
    return collector.process_file(file_path, tax_year)
