"""Encrypted SQLite database for tax data storage."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from tax_agent.config import get_config
from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.models.memory import Memory, MemoryCategory, MemoryType
from tax_agent.models.taxpayer import TaxpayerProfile


class TaxDatabase:
    """Encrypted SQLite database for storing tax documents and data."""

    def __init__(self, db_path: Path | None = None, password: str | None = None):
        """
        Initialize the database connection.

        Args:
            db_path: Path to the database file. Defaults to config path.
            password: Encryption password. Defaults to keyring-stored password.
        """
        config = get_config()
        self.db_path = db_path or config.db_path
        self._password = password or config.get_db_password()

        if not self._password:
            raise ValueError("Database password not found. Run 'tax-agent init' first.")

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new database connection with encryption."""
        # Use sqlcipher for encryption
        try:
            import sqlcipher3 as sqlite3_encrypted

            conn = sqlite3_encrypted.connect(str(self.db_path))
            conn.execute(f"PRAGMA key = '{self._password}'")
            # Use sqlcipher3's Row class for compatibility
            conn.row_factory = sqlite3_encrypted.Row
        except ImportError:
            # Fall back to regular sqlite (unencrypted) for development
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row

        return conn

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    tax_year INTEGER NOT NULL,
                    document_type TEXT NOT NULL,
                    issuer_name TEXT NOT NULL,
                    issuer_ein TEXT,
                    recipient_ssn_last4 TEXT,
                    raw_text TEXT NOT NULL,
                    extracted_data TEXT NOT NULL,
                    file_path TEXT,
                    file_hash TEXT NOT NULL,
                    confidence_score REAL DEFAULT 0.0,
                    needs_review INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_tax_year ON documents(tax_year);
                CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);

                CREATE TABLE IF NOT EXISTS taxpayer_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tax_year INTEGER NOT NULL UNIQUE,
                    profile_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_results (
                    id TEXT PRIMARY KEY,
                    tax_year INTEGER NOT NULL,
                    analysis_type TEXT NOT NULL,
                    result_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_results (
                    id TEXT PRIMARY KEY,
                    tax_year INTEGER NOT NULL,
                    return_type TEXT NOT NULL,
                    summary_data TEXT NOT NULL,
                    findings TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tax_year INTEGER,
                    confidence REAL DEFAULT 1.0,
                    source TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_year ON memories(tax_year);
            """)

    # Document operations
    def save_document(self, doc: TaxDocument) -> None:
        """Save a tax document to the database."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, tax_year, document_type, issuer_name, issuer_ein, recipient_ssn_last4,
                 raw_text, extracted_data, file_path, file_hash, confidence_score, needs_review,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    doc.tax_year,
                    doc.document_type,
                    doc.issuer_name,
                    doc.issuer_ein,
                    doc.recipient_ssn_last4,
                    doc.raw_text,
                    json.dumps(doc.extracted_data),
                    doc.file_path,
                    doc.file_hash,
                    doc.confidence_score,
                    1 if doc.needs_review else 0,
                    doc.created_at.isoformat(),
                    doc.updated_at.isoformat(),
                ),
            )

    def get_document(self, doc_id: str) -> TaxDocument | None:
        """Get a document by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()

            if row is None:
                return None

            return self._row_to_document(row)

    def get_documents(
        self,
        tax_year: int | None = None,
        document_type: DocumentType | None = None,
    ) -> list[TaxDocument]:
        """Get documents with optional filtering."""
        query = "SELECT * FROM documents WHERE 1=1"
        params: list[Any] = []

        if tax_year is not None:
            query += " AND tax_year = ?"
            params.append(tax_year)

        if document_type is not None:
            query += " AND document_type = ?"
            params.append(document_type.value if isinstance(document_type, DocumentType) else document_type)

        query += " ORDER BY created_at DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_document(row) for row in rows]

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0

    def _row_to_document(self, row: Any) -> TaxDocument:
        """Convert a database row to a TaxDocument."""
        return TaxDocument(
            id=row["id"],
            tax_year=row["tax_year"],
            document_type=DocumentType(row["document_type"]),
            issuer_name=row["issuer_name"],
            issuer_ein=row["issuer_ein"],
            recipient_ssn_last4=row["recipient_ssn_last4"],
            raw_text=row["raw_text"],
            extracted_data=json.loads(row["extracted_data"]),
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            confidence_score=row["confidence_score"],
            needs_review=bool(row["needs_review"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Taxpayer profile operations
    def save_taxpayer_profile(self, profile: TaxpayerProfile) -> None:
        """Save a taxpayer profile."""
        with self._connection() as conn:
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT OR REPLACE INTO taxpayer_profiles
                (tax_year, profile_data, created_at, updated_at)
                VALUES (?, ?, COALESCE(
                    (SELECT created_at FROM taxpayer_profiles WHERE tax_year = ?),
                    ?
                ), ?)
                """,
                (
                    profile.tax_year,
                    profile.model_dump_json(),
                    profile.tax_year,
                    now,
                    now,
                ),
            )

    def get_taxpayer_profile(self, tax_year: int) -> TaxpayerProfile | None:
        """Get taxpayer profile for a tax year."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT profile_data FROM taxpayer_profiles WHERE tax_year = ?",
                (tax_year,)
            ).fetchone()

            if row is None:
                return None

            return TaxpayerProfile.model_validate_json(row["profile_data"])

    # Summary operations
    def get_document_summary(self, tax_year: int) -> dict[str, Any]:
        """Get a summary of documents for a tax year."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT document_type, COUNT(*) as count
                FROM documents
                WHERE tax_year = ?
                GROUP BY document_type
                """,
                (tax_year,)
            ).fetchall()

            return {row["document_type"]: row["count"] for row in rows}

    # Review operations
    def save_review(self, review: "TaxReturnReview") -> None:
        """Save a tax return review to the database."""
        from tax_agent.models.returns import TaxReturnReview

        # Include overall_assessment and counts in summary data
        summary_data = review.return_summary.model_dump()
        summary_data["overall_assessment"] = review.overall_assessment
        summary_data["errors_count"] = review.errors_count
        summary_data["warnings_count"] = review.warnings_count
        summary_data["suggestions_count"] = review.suggestions_count
        summary_data["estimated_additional_refund"] = review.estimated_additional_refund

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_results
                (id, tax_year, return_type, summary_data, findings, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    review.id,
                    review.return_summary.tax_year,
                    review.return_summary.return_type,
                    json.dumps(summary_data, default=str),
                    json.dumps([f.model_dump() for f in review.findings], default=str),
                    review.reviewed_at.isoformat(),
                ),
            )

    def get_reviews(self, tax_year: int | None = None) -> list[dict]:
        """Get saved reviews, optionally filtered by tax year."""
        with self._connection() as conn:
            if tax_year:
                rows = conn.execute(
                    "SELECT * FROM review_results WHERE tax_year = ? ORDER BY created_at DESC",
                    (tax_year,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_results ORDER BY created_at DESC"
                ).fetchall()

            return [
                {
                    "id": row["id"],
                    "tax_year": row["tax_year"],
                    "return_type": row["return_type"],
                    "summary": json.loads(row["summary_data"]),
                    "findings": json.loads(row["findings"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def get_review(self, review_id: str) -> dict | None:
        """Get a specific review by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM review_results WHERE id = ? OR id LIKE ?",
                (review_id, f"{review_id}%")
            ).fetchone()

            if row is None:
                return None

            return {
                "id": row["id"],
                "tax_year": row["tax_year"],
                "return_type": row["return_type"],
                "summary": json.loads(row["summary_data"]),
                "findings": json.loads(row["findings"]),
                "created_at": row["created_at"],
            }

    def delete_review(self, review_id: str) -> bool:
        """Delete a review by ID."""
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM review_results WHERE id = ?", (review_id,))
            return cursor.rowcount > 0

    # Memory operations
    def save_memory(self, memory: Memory) -> str:
        """Save a memory to the database. Returns the memory ID."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, memory_type, category, content, tax_year, confidence, source,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.memory_type,
                    memory.category,
                    memory.content,
                    memory.tax_year,
                    memory.confidence,
                    memory.source,
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                ),
            )
        return memory.id

    def get_memory(self, memory_id: str) -> Memory | None:
        """Get a memory by ID."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ? OR id LIKE ?",
                (memory_id, f"{memory_id}%")
            ).fetchone()

            if row is None:
                return None

            return self._row_to_memory(row)

    def get_memories(
        self,
        memory_type: MemoryType | str | None = None,
        category: MemoryCategory | str | None = None,
        tax_year: int | None = None,
    ) -> list[Memory]:
        """Get memories with optional filtering."""
        query = "SELECT * FROM memories WHERE 1=1"
        params: list[Any] = []

        if memory_type is not None:
            query += " AND memory_type = ?"
            params.append(memory_type.value if isinstance(memory_type, MemoryType) else memory_type)

        if category is not None:
            query += " AND category = ?"
            params.append(category.value if isinstance(category, MemoryCategory) else category)

        if tax_year is not None:
            # Include year-agnostic memories (tax_year IS NULL) along with specific year
            query += " AND (tax_year = ? OR tax_year IS NULL)"
            params.append(tax_year)

        query += " ORDER BY created_at DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def get_all_memories(self) -> list[Memory]:
        """Get all memories."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY memory_type, category, created_at DESC"
            ).fetchall()
            return [self._row_to_memory(row) for row in rows]

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID (supports partial ID match)."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE id = ? OR id LIKE ?",
                (memory_id, f"{memory_id}%")
            )
            return cursor.rowcount > 0

    def clear_memories(self) -> int:
        """Delete all memories. Returns count of deleted memories."""
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM memories")
            return cursor.rowcount

    def _row_to_memory(self, row: Any) -> Memory:
        """Convert a database row to a Memory."""
        return Memory(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            category=MemoryCategory(row["category"]),
            content=row["content"],
            tax_year=row["tax_year"],
            confidence=row["confidence"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# Global database instance
_db: TaxDatabase | None = None


def get_database() -> TaxDatabase:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = TaxDatabase()
    return _db
