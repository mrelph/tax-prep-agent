# Tax Prep Agent

A Python CLI agent for tax document collection, OCR/vision extraction, deduction analysis, and return
review, built on Anthropic's Claude Agent SDK with specialized tax subagents. Handles real, sensitive
personal tax data — treat all taxpayer documents and stored data as confidential (see Gotchas).

## Commands

Editable install with dev tools:
```bash
pip install -e ".[dev]"            # runtime + pytest/ruff/mypy
pip install -e ".[encrypted]"      # adds sqlcipher3-binary for DB encryption (see Gotchas)
```
Test / lint / type-check (verified from README + pyproject.toml):
```bash
pytest                             # run tests (testpaths = tests/)
pytest --cov=tax_agent --cov-report=html
pytest tests/test_analyzers.py     # single file
ruff check .                       # lint (line-length 100, py311)
ruff check --fix .
mypy src/tax_agent                 # strict mode
```
Entry points (from `[project.scripts]`):
- `tax-agent` -> `tax_agent.cli:app` (Typer CLI; run `tax-agent init` first)
- `tax-agent-mcp` -> `tax_agent.mcp_server:main` (MCP stdio server for Claude Desktop)

## Architecture

- **CLI** (`cli.py`, Typer): top-level app plus sub-apps `documents`, `config`, `research`, `drive`,
  `ai`, `context`, `source`. `chat.py` / `slash_commands.py` provide interactive mode.
- **Agent layer**: `agent_sdk.py` (`TaxAgentSDK`, primary, uses `claude-code-sdk` / `query`) is the
  default; `agent.py` (`TaxAgent`, direct `anthropic` SDK) is the backward-compat path. `agent_compat.py`
  bridges when `claude-code-sdk` is absent. `config.use_agent_sdk` (default True) selects the path.
- **Subagents** (`subagents.py`): `SubagentDefinition` registry `TAX_SUBAGENTS` — stock-compensation-analyst,
  deduction-finder, compliance-auditor, investment-tax-analyst, retirement-tax-planner,
  self-employment-specialist. `get_subagent_for_task()` routes by task text.
- **Tools** (`tools/tax_calculations.py`): pure functions (brackets, standard deduction, federal tax,
  contribution limits, wash-sale detection, FICA) exposed via `MCP_TOOL_DEFINITIONS`.
- **Hooks** (`hooks.py`): `audit_log_hook`, `sensitive_data_guard` (file-access control),
  `ssn_redaction_hook` (regex SSN redaction on tool outputs) — wired in when `use_hooks=True`.
- **Data flow**: collectors (`collectors/`: OCR, pdf_parser, document_classifier, google_drive) ->
  analyzers (`analyzers/`) / reviewers (`reviewers/`) -> encrypted DB (`storage/database.py`) ->
  reports/exporters. Tax rules loaded from `data/tax_rules/*.yaml` (federal_2024, states/ca_2024).
- **Config/state**: lives under `~/.tax-agent/` (config.json + `data/tax_data.db`). Secrets in OS keyring.

## Conventions

- Python >=3.11, `src/` layout, Pydantic models (`models/`), ruff (E,F,I,N,W,UP) + mypy strict.
- Access config via `get_config()` / the registry singleton (`registry.py`), not by constructing `Config`.
- Model aliases map to dated IDs in `agent.py` / `agent_sdk.py`. Default is `claude-sonnet-4-5`
  (-> `claude-sonnet-4-5-20250929`). These IDs are the project's own — do not "correct" them.
  Bedrock variants use `anthropic.<model>-...-v1:0` ARNs.

## Gotchas

- **Sensitive tax data**: taxpayer documents, extracted values, and the SQLite DB contain SSNs/EINs and
  financial data. NEVER commit real tax documents, `*.db`, `tax_data/`, or `.tax-agent/` — `.gitignore`
  already excludes them; keep it that way. Test fixtures with real data go in
  `tests/fixtures/real_documents/` (git-ignored).
- **Encryption is opt-in**: `storage/database.py` only encrypts if `sqlcipher3` is installed. Without the
  `[encrypted]` extra it silently falls back to **plaintext** SQLite (logs a warning only). Install
  `sqlcipher3-binary` for real encryption.
- **Required setup**: run `tax-agent init` (stores DB password + provider creds in the OS keyring) before
  DB operations, or `TaxDatabase` raises "Database password not found".
- **Credentials/env vars** (checked env-first, then keyring service `tax-prep-agent`): `ANTHROPIC_API_KEY`
  (default provider), `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` + `aws_region` (Bedrock provider),
  `BRAVE_API_KEY` (web/tax research), plus Google Drive OAuth creds in keyring. None are committed.
- **System deps**: Tesseract OCR and Poppler must be installed for PDF/image processing.
- **SSN redaction** (`auto_redact_ssn`, default True) strips SSNs before AI calls — keep enabled when
  handling real data.
