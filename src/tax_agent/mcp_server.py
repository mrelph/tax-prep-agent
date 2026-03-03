"""MCP server facade for the tax-prep-agent.

Exposes the agent's capabilities (document collection, analysis, review,
deduction finding, subagents) as MCP tools and resources over stdio transport.
All business logic stays in the existing modules — this is a thin async adapter.

Usage:
    tax-agent-mcp              # entry point registered in pyproject.toml
    uv run tax-agent-mcp       # via uv
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging — all output to stderr (stdout is reserved for MCP stdio protocol)
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tax-agent-mcp")

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "tax-prep-agent",
    instructions="Tax document collection, analysis, and return review agent",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_serializer(obj: Any) -> Any:
    """Handle types that json.dumps can't serialize by default."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _error_response(operation: str, message: str) -> str:
    """Return a structured JSON error string."""
    return json.dumps({"error": True, "operation": operation, "message": message})


async def _collect_stream(async_iter) -> str:
    """Drain an async iterator of string chunks into a single string."""
    chunks: list[str] = []
    async for chunk in async_iter:
        chunks.append(chunk)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Service accessors (lazy imports to avoid circular deps at module load)
# ---------------------------------------------------------------------------

def _get_config():
    from tax_agent.config import get_config
    return get_config()


def _get_database():
    from tax_agent.storage.database import get_database
    return get_database()


def _get_sdk_agent():
    from tax_agent.agent_sdk import get_sdk_agent
    return get_sdk_agent()


def _get_tax_context():
    from tax_agent.context import get_tax_context
    return get_tax_context()


def _get_context_for_prompt() -> str:
    from tax_agent.context import get_context_for_prompt
    return get_context_for_prompt()


def _sdk_available() -> bool:
    from tax_agent.agent_sdk import sdk_available
    return sdk_available()


# ===================================================================
# MCP Tools (7)
# ===================================================================

@mcp.tool()
async def collect_document(
    file_path: str,
    tax_year: int | None = None,
    replace: bool = False,
) -> str:
    """Process and collect a tax document (PDF or image) for analysis.

    Extracts text via OCR/vision, classifies the document type, and stores
    structured data in the encrypted database.

    Args:
        file_path: Absolute path to the PDF or image file.
        tax_year: Tax year this document belongs to (defaults to configured year).
        replace: If True, replace an existing document with the same file hash.
    """
    try:
        from tax_agent.collectors.document_classifier import DocumentCollector

        collector = DocumentCollector()
        doc = collector.process_file(file_path, tax_year=tax_year, replace=replace)
        return json.dumps(doc.model_dump(), default=_json_serializer, indent=2)
    except FileNotFoundError as exc:
        return _error_response("collect_document", str(exc))
    except ValueError as exc:
        return _error_response("collect_document", str(exc))
    except Exception as exc:
        logger.exception("collect_document failed")
        return _error_response("collect_document", f"Unexpected error: {exc}")


@mcp.tool()
async def analyze_documents(
    tax_year: int | None = None,
    taxpayer_info: str | None = None,
) -> str:
    """Analyze all collected tax documents for a given year.

    Uses the Agent SDK to cross-reference documents, verify figures,
    and provide a comprehensive tax analysis.

    Args:
        tax_year: Tax year to analyze (defaults to configured year).
        taxpayer_info: Optional taxpayer profile summary text.
    """
    try:
        config = _get_config()
        db = _get_database()
        year = tax_year or config.tax_year

        docs = db.get_documents(tax_year=year)
        if not docs:
            return _error_response("analyze_documents", f"No documents found for tax year {year}")

        docs_summary = "\n".join(
            f"- {d.document_type} from {d.issuer_name} "
            f"(confidence: {d.confidence_score:.0%})"
            for d in docs
        )

        if not taxpayer_info:
            profile = db.get_taxpayer_profile(year)
            taxpayer_info = json.dumps(profile.model_dump(), default=_json_serializer) if profile else "No profile on file"

        sdk = _get_sdk_agent()
        result = await _collect_stream(
            sdk.analyze_documents_async(docs_summary, taxpayer_info)
        )
        return result
    except Exception as exc:
        logger.exception("analyze_documents failed")
        return _error_response("analyze_documents", f"Unexpected error: {exc}")


@mcp.tool()
async def review_return(
    return_file: str,
    tax_year: int | None = None,
) -> str:
    """Review a completed tax return against source documents.

    Cross-references every amount on the return with collected source
    documents and identifies errors, discrepancies, and optimizations.

    Args:
        return_file: Path to the tax return PDF/image to review.
        tax_year: Tax year for source document lookup (defaults to configured year).
    """
    try:
        config = _get_config()
        db = _get_database()
        year = tax_year or config.tax_year

        path = Path(return_file)
        if not path.exists():
            return _error_response("review_return", f"File not found: {return_file}")

        # Extract text from the return file
        from tax_agent.collectors.ocr import extract_text_with_ocr
        return_text = extract_text_with_ocr(str(path))

        # Gather source document summaries
        docs = db.get_documents(tax_year=year)
        source_summary = "\n".join(
            f"- {d.document_type} from {d.issuer_name}: "
            f"{json.dumps(d.extracted_data, default=_json_serializer)}"
            for d in docs
        )

        sdk = _get_sdk_agent()
        result = await _collect_stream(
            sdk.review_return_async(return_text, source_summary, path.parent)
        )
        return result
    except Exception as exc:
        logger.exception("review_return failed")
        return _error_response("review_return", f"Unexpected error: {exc}")


@mcp.tool()
async def query(
    question: str,
    tax_year: int | None = None,
    include_context: bool = True,
) -> str:
    """Ask a tax-related question with access to collected documents and tools.

    The agent can read source files, search the web for current IRS rules,
    and use tax calculation tools to provide specific, actionable advice.

    Args:
        question: Your tax question or request.
        tax_year: Tax year for context (defaults to configured year).
        include_context: Whether to include taxpayer context from TAX_CONTEXT.md.
    """
    try:
        config = _get_config()
        db = _get_database()
        year = tax_year or config.tax_year

        context: dict[str, Any] = {"tax_year": year}

        if include_context:
            ctx_text = _get_context_for_prompt()
            if ctx_text:
                context["taxpayer_context"] = ctx_text

            docs = db.get_documents(tax_year=year)
            if docs:
                context["documents"] = [
                    {"type": d.document_type, "issuer": d.issuer_name}
                    for d in docs
                ]

            profile = db.get_taxpayer_profile(year)
            if profile:
                context["taxpayer_profile"] = profile.model_dump()

        sdk = _get_sdk_agent()
        result = await _collect_stream(
            sdk.interactive_query_async(question, context=context)
        )
        return result
    except Exception as exc:
        logger.exception("query failed")
        return _error_response("query", f"Unexpected error: {exc}")


@mcp.tool()
async def find_deductions(tax_year: int | None = None) -> str:
    """Find applicable tax deductions and credits based on collected documents.

    Analyzes all collected documents and taxpayer profile to recommend
    deductions, credits, and tax-saving strategies.

    Args:
        tax_year: Tax year to analyze (defaults to configured year).
    """
    try:
        from tax_agent.analyzers.deductions import TaxOptimizer

        config = _get_config()
        year = tax_year or config.tax_year

        optimizer = TaxOptimizer(tax_year=year)
        result = optimizer.find_deductions()
        return json.dumps(result, default=_json_serializer, indent=2)
    except Exception as exc:
        logger.exception("find_deductions failed")
        return _error_response("find_deductions", f"Unexpected error: {exc}")


@mcp.tool()
async def invoke_subagent(subagent_name: str, prompt: str) -> str:
    """Invoke a specialized tax subagent for a focused task.

    Available subagents include deduction-finder, compliance-auditor,
    and others. Use list_subagents to see all options.

    Args:
        subagent_name: Name of the subagent (e.g. 'deduction-finder').
        prompt: Task description or question for the subagent.
    """
    try:
        sdk = _get_sdk_agent()
        result = await _collect_stream(
            sdk.invoke_subagent_async(subagent_name, prompt)
        )
        return result
    except Exception as exc:
        logger.exception("invoke_subagent failed")
        return _error_response("invoke_subagent", f"Unexpected error: {exc}")


@mcp.tool()
async def list_subagents() -> str:
    """List all available specialized tax subagents with descriptions."""
    try:
        sdk = _get_sdk_agent()
        agents = sdk.list_subagents()
        return json.dumps(agents, indent=2)
    except Exception as exc:
        logger.exception("list_subagents failed")
        return _error_response("list_subagents", f"Unexpected error: {exc}")


# ===================================================================
# MCP Resources (5)
# ===================================================================

@mcp.resource("tax://status")
async def get_status() -> str:
    """Current status of the tax agent: initialization state, document counts, model info."""
    try:
        config = _get_config()
        status: dict[str, Any] = {
            "initialized": config.is_initialized,
            "tax_year": config.tax_year,
            "ai_provider": config.ai_provider,
            "model": config.get("model", "claude-sonnet-4-5"),
            "use_agent_sdk": config.use_agent_sdk,
            "sdk_available": _sdk_available(),
        }

        try:
            db = _get_database()
            docs = db.get_documents(tax_year=config.tax_year)
            status["document_count"] = len(docs)
            status["document_types"] = list({d.document_type for d in docs})
        except Exception:
            status["document_count"] = 0
            status["document_types"] = []
            status["database_error"] = "Could not connect to database"

        return json.dumps(status, default=_json_serializer, indent=2)
    except Exception as exc:
        logger.exception("get_status failed")
        return _error_response("status", str(exc))


@mcp.resource("tax://config")
async def get_config_resource() -> str:
    """Current configuration (secrets excluded)."""
    try:
        config = _get_config()
        data = config.to_dict()
        # Strip any sensitive keys that might leak
        for key in ("api_key", "password", "secret", "token", "credentials"):
            data.pop(key, None)
        return json.dumps(data, default=_json_serializer, indent=2)
    except Exception as exc:
        logger.exception("get_config_resource failed")
        return _error_response("config", str(exc))


@mcp.resource("tax://documents/{tax_year}")
async def get_documents(tax_year: int) -> str:
    """List of collected documents for a tax year with extracted data."""
    try:
        db = _get_database()
        docs = db.get_documents(tax_year=tax_year)
        result = [
            {
                "id": d.id,
                "document_type": d.document_type,
                "issuer_name": d.issuer_name,
                "tax_year": d.tax_year,
                "confidence_score": d.confidence_score,
                "needs_review": d.needs_review,
                "extracted_data": d.extracted_data,
                "tags": d.tags,
                "file_path": d.file_path,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
        return json.dumps(result, default=_json_serializer, indent=2)
    except Exception as exc:
        logger.exception("get_documents failed")
        return _error_response("documents", str(exc))


@mcp.resource("tax://profile/{tax_year}")
async def get_profile(tax_year: int) -> str:
    """Taxpayer profile for a given tax year."""
    try:
        db = _get_database()
        profile = db.get_taxpayer_profile(tax_year)
        if not profile:
            return json.dumps({"message": f"No profile found for tax year {tax_year}"})
        return json.dumps(profile.model_dump(), default=_json_serializer, indent=2)
    except Exception as exc:
        logger.exception("get_profile failed")
        return _error_response("profile", str(exc))


@mcp.resource("tax://context")
async def get_context() -> str:
    """Contents of TAX_CONTEXT.md — the user's taxpayer situation summary."""
    try:
        ctx = _get_tax_context()
        content = ctx.load()
        if not content:
            return json.dumps({
                "message": "No TAX_CONTEXT.md found. Run 'tax-agent context' to create one.",
                "path": str(ctx.context_path),
            })
        return content
    except Exception as exc:
        logger.exception("get_context failed")
        return _error_response("context", str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting tax-prep-agent MCP server")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
