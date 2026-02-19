"""Document classification and data extraction orchestration."""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from tax_agent.agent import get_agent
from tax_agent.collectors.ocr import extract_text_with_ocr
from tax_agent.config import get_config
from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.storage.database import get_database
from tax_agent.storage.encryption import hash_file, redact_sensitive_data
from tax_agent.utils import get_enum_value


class DocumentCollector:
    """Collects and processes tax documents."""

    def __init__(self):
        """Initialize the document collector."""
        self.config = get_config()
        self._agent = None
        self._sdk_agent = None

    @property
    def agent(self):
        """Get the legacy agent (lazy initialization)."""
        if self._agent is None:
            self._agent = get_agent()
        return self._agent

    @property
    def sdk_agent(self):
        """Get the SDK agent if enabled (lazy initialization)."""
        if self._sdk_agent is None and self.config.use_agent_sdk:
            from tax_agent.agent_sdk import get_sdk_agent, sdk_available
            if sdk_available():
                self._sdk_agent = get_sdk_agent()
        return self._sdk_agent

    def _use_sdk(self) -> bool:
        """Check if we should use the Agent SDK."""
        return self.config.use_agent_sdk and self.sdk_agent is not None

    def _classify_with_sdk(self, text: str, file_path: Path) -> dict:
        """
        Classify document using Agent SDK with agentic verification.

        The SDK agent can use tools to verify uncertain classifications
        by searching for specific markers in the document.

        Args:
            text: Document text
            file_path: Path to source file for tool access

        Returns:
            Classification dictionary
        """
        try:
            return self.sdk_agent.classify_document(text, file_path)
        except Exception as e:
            # Fall back to legacy agent on SDK error
            import logging
            logging.warning(f"SDK classification failed, falling back to legacy: {e}")
            return self.agent.classify_document(text)

    def _extract_data_with_sdk(self, doc_type: DocumentType, text: str, file_path: Path) -> dict:
        """
        Extract data using Agent SDK with verification capabilities.

        Args:
            doc_type: Document type
            text: Document text
            file_path: Path to source file

        Returns:
            Extracted data dictionary
        """
        # For now, use the legacy extraction but run through SDK for verification
        # In future, this can use agentic extraction with tool verification
        extracted = self._extract_data(doc_type, text)

        # If SDK is available and doc needs verification, use interactive query
        if extracted and self.sdk_agent:
            try:
                # Run a quick verification pass with the SDK
                verification_prompt = f"""Verify this {get_enum_value(doc_type)} extraction is accurate.
Check that the amounts and names match the source document.

Extracted data:
{extracted}

If you find discrepancies, return corrected JSON. Otherwise confirm the data is accurate."""

                result = self.sdk_agent.interactive_query(
                    verification_prompt,
                    context={"document_type": get_enum_value(doc_type)},
                    source_dir=file_path.parent if file_path else None,
                )
                # If the SDK returns corrected data, parse and use it
                if "corrected" in result.lower() or "{" in result:
                    import json
                    try:
                        # Try to extract JSON from the response
                        json_start = result.find("{")
                        json_end = result.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            corrected = json.loads(result[json_start:json_end])
                            if corrected:
                                extracted.update(corrected)
                    except json.JSONDecodeError:
                        pass  # Keep original extraction
            except Exception:
                pass  # Keep original extraction on error

        return extracted

    def process_file(
        self, file_path: str | Path, tax_year: int | None = None, replace: bool = False
    ) -> TaxDocument:
        """
        Process a tax document file.

        Args:
            file_path: Path to the PDF or image file
            tax_year: Tax year (defaults to config)
            replace: If True, replace existing document with same file hash

        Returns:
            Processed TaxDocument
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        tax_year = tax_year or self.config.tax_year

        # Compute file hash for deduplication
        file_hash = hash_file(str(file_path))

        # Check for duplicate
        db = get_database()
        existing = db.get_documents(tax_year=tax_year)
        for doc in existing:
            if doc.file_hash == file_hash:
                if replace:
                    # Delete existing document to replace it
                    db.delete_document(doc.id)
                else:
                    raise ValueError(
                        f"Document already exists: {doc.issuer_name} ({get_enum_value(doc.document_type)}). "
                        f"Use --replace to update it."
                    )

        # Check if we should use Vision API (default) or OCR
        use_vision = self.config.get("use_vision", True)

        if use_vision:
            # Note: Vision mode sends the full document image to the API.
            # SSN redaction cannot be applied to images before sending.
            if self.config.get("auto_redact_ssn", True):
                import logging
                logging.getLogger("tax_agent").info(
                    "Vision mode sends document images directly to the API. "
                    "SSN redaction only applies to stored text, not the image itself. "
                    "Set use_vision=false for full pre-API redaction."
                )

            # Use Claude Vision for classification and extraction
            classification = self.agent.classify_document_with_vision(str(file_path))

            doc_type_str = classification.get("document_type", "UNKNOWN")
            try:
                doc_type = DocumentType(doc_type_str)
            except ValueError:
                doc_type = DocumentType.UNKNOWN

            # Check if this is a tax return - suggest /review instead
            from tax_agent.models.documents import TAX_RETURNS
            if doc_type in TAX_RETURNS:
                doc_type_display = get_enum_value(doc_type)
                tax_year_hint = classification.get("tax_year", "")
                year_str = f" ({tax_year_hint})" if tax_year_hint else ""
                raise ValueError(
                    f"This looks like a completed tax return ({doc_type_display}{year_str}).\n\n"
                    f"Use `/review {file_path}` to check it for errors instead.\n\n"
                    f"The `/collect` command is for source documents like W2s and 1099s."
                )

            # Extract data using vision if it's a known type
            if doc_type != DocumentType.UNKNOWN:
                extracted_data = self.agent.extract_data_with_vision(
                    get_enum_value(doc_type), str(file_path)
                )
            else:
                extracted_data = {}

            # Also get raw text for storage (using OCR as fallback)
            try:
                raw_text = extract_text_with_ocr(file_path)
            except Exception:
                raw_text = f"[Vision-processed document: {doc_type_str}]"

            # Vision-based confidence
            confidence = classification.get("confidence", 0.0)
            needs_review = confidence < 0.8 or doc_type == DocumentType.UNKNOWN

        else:
            # Legacy OCR-based processing
            raw_text = extract_text_with_ocr(file_path)

            # Optionally redact sensitive data before sending to AI
            text_for_analysis = raw_text
            if self.config.get("auto_redact_ssn", True):
                text_for_analysis = redact_sensitive_data(raw_text)

            # Classify the document using Claude (SDK or legacy)
            if self._use_sdk():
                classification = self._classify_with_sdk(text_for_analysis, file_path)
            else:
                classification = self.agent.classify_document(text_for_analysis)

            doc_type_str = classification.get("document_type", "UNKNOWN")
            try:
                doc_type = DocumentType(doc_type_str)
            except ValueError:
                doc_type = DocumentType.UNKNOWN

            # Check if this is a tax return - suggest /review instead
            from tax_agent.models.documents import TAX_RETURNS
            if doc_type in TAX_RETURNS:
                doc_type_display = get_enum_value(doc_type)
                tax_year_hint = classification.get("tax_year", "")
                year_str = f" ({tax_year_hint})" if tax_year_hint else ""
                raise ValueError(
                    f"This looks like a completed tax return ({doc_type_display}{year_str}).\n\n"
                    f"Use `/review {file_path}` to check it for errors instead.\n\n"
                    f"The `/collect` command is for source documents like W2s and 1099s."
                )

            # Extract structured data based on document type
            extracted_data = self._extract_data(doc_type, text_for_analysis)

            # Verify extracted data against source document
            from tax_agent.verification import verify_extraction
            verification = verify_extraction(get_enum_value(doc_type), extracted_data, raw_text)

            # Combine confidence scores
            classification_conf = classification.get("confidence", 0.0)
            verification_conf = verification.get("confidence", 1.0)
            confidence = (classification_conf + verification_conf) / 2

            needs_review = (
                classification.get("confidence", 0.0) < 0.8
                or doc_type == DocumentType.UNKNOWN
                or not verification.get("verified", True)
                or verification.get("confidence", 1.0) < 0.7
            )

        # Use tax year from classification if available
        classified_year = classification.get("tax_year")
        if classified_year and isinstance(classified_year, int):
            tax_year = classified_year

        # Redact sensitive data from raw_text before storing in DB
        if self.config.get("auto_redact_ssn", True):
            raw_text = redact_sensitive_data(raw_text)

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
            confidence_score=confidence,
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
        elif doc_type == DocumentType.FORM_1099_NEC:
            return self.agent.extract_1099_nec_data(text)
        elif doc_type == DocumentType.FORM_1099_R:
            return self.agent.extract_1099_r_data(text)
        elif doc_type == DocumentType.FORM_1098:
            return self.agent.extract_1098_data(text)
        else:
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
