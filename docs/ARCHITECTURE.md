# Architecture Overview

Technical architecture and design documentation for the Tax Prep Agent.

## Table of Contents

- [System Overview](#system-overview)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Document Processing Pipeline](#document-processing-pipeline)
- [AI Integration](#ai-integration)
- [Security Architecture](#security-architecture)
- [Storage Layer](#storage-layer)
- [Extension Points](#extension-points)

## System Overview

The Tax Prep Agent is a Python-based application built on Anthropic's Claude Agent SDK, combining local document processing with agentic AI capabilities to provide intelligent, conversational tax document management and analysis.

### Primary Interface: Agent SDK

The system operates in two modes:

1. **Interactive Agent Mode** (Default): Conversational interface powered by the Claude Agent SDK
   - Natural language interaction
   - Agentic loops with multi-turn reasoning
   - Tool use for verification and research
   - Specialized subagents for complex domains
   - Safety hooks for audit and control

2. **Direct CLI Mode**: Traditional command-line interface
   - Direct command execution (`tax-agent analyze`, `tax-agent collect`)
   - Backward compatible with legacy workflows
   - Uses compatibility layer to support both Agent SDK and direct API calls

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface                           │
│   Interactive Mode (Agent SDK) | Direct CLI (Typer)         │
└─────────────────────────────────────────────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
┌────────────────────────┐    ┌────────────────────────┐
│   Agent SDK Layer      │    │   Direct CLI Layer     │
│                        │    │                        │
│ • TaxAgentSDK          │    │ • Command handlers     │
│ • Slash commands       │    │ • Typer commands       │
│ • Subagent router      │    │                        │
│ • Safety hooks         │    │                        │
└────────────────────────┘    └────────────────────────┘
                 │                         │
                 └────────────┬────────────┘
                              ▼
                    ┌──────────────────┐
                    │  Agent Compat    │
                    │  (Unified API)   │
                    └──────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  Collectors  │    │   Analyzers      │    │  Reviewers   │
│              │    │                  │    │              │
│ • OCR        │    │ • Implications   │    │ • Error      │
│ • PDF Parser │    │ • Deductions     │    │   Checker    │
│ • Classifier │    │ • Stock Comp     │    │              │
│ • Drive API  │    │                  │    │              │
└──────────────┘    └──────────────────┘    └──────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌──────────────────────────┐
                    │   AI Engine Layer        │
                    │                          │
                    │ ┌──────────────────────┐ │
                    │ │ Agent SDK (Primary)  │ │
                    │ │ • Agentic loops      │ │
                    │ │ • Tool use           │ │
                    │ │ • Subagents          │ │
                    │ │ • Hooks              │ │
                    │ └──────────────────────┘ │
                    │ ┌──────────────────────┐ │
                    │ │ Legacy Direct API    │ │
                    │ │ • Anthropic SDK      │ │
                    │ │ • AWS Bedrock        │ │
                    │ └──────────────────────┘ │
                    └──────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│ Verification │    │     Storage      │    │    Config    │
│              │    │                  │    │              │
│ • Output     │    │ • Encrypted DB   │    │ • Settings   │
│   Validator  │    │ • Documents      │    │ • Keyring    │
│ • Sanity     │    │ • Analysis       │    │              │
│   Checks     │    │ • Profiles       │    │              │
└──────────────┘    └──────────────────┘    └──────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **CLI Framework** | Typer | Command-line interface and argument parsing |
| **Terminal UI** | Rich | Formatted output, tables, panels, progress bars |
| **AI Provider** | Anthropic Claude | Document classification, data extraction, analysis |
| **AI Alternative** | AWS Bedrock | Enterprise AI provider option |
| **OCR Engine** | Tesseract | Image text extraction |
| **PDF Processing** | PyMuPDF, pdf2image, Poppler | PDF parsing and conversion |
| **Database** | SQLite + SQLCipher | Encrypted local storage |
| **Data Models** | Pydantic | Type-safe data validation and serialization |
| **Credentials** | Python Keyring | Secure OS-level credential storage |
| **Cloud Storage** | Google Drive API | Optional document collection from Drive |
| **HTTP Client** | google-api-python-client | Google Drive integration |

### Design Principles

1. **Local-First Processing**: OCR and PDF parsing happen locally before cloud AI
2. **Privacy by Default**: SSN/EIN redaction before sending to AI
3. **Encryption at Rest**: All sensitive data encrypted in local database
4. **Fail-Safe Design**: Low confidence results flagged for manual review
5. **Verification Layer**: AI outputs validated against source documents
6. **Modular Architecture**: Clear separation between collection, analysis, and review
7. **Provider Flexibility**: Support for multiple AI providers (Anthropic, AWS)

## Core Components

### 1. CLI Layer (`cli.py`)

**Responsibility:** Command-line interface and user interaction

**Key Classes/Functions:**
- `app`: Main Typer application
- `_start_interactive_mode()`: Launch Agent SDK interactive session
- Command handlers: `init()`, `collect()`, `analyze()`, `optimize()`, `review()`, `chat()`
- Sub-applications: `documents_app`, `config_app`, `research_app`, `drive_app`

**Interactions:**
- Parses user commands and arguments
- Routes to interactive mode (default) or direct CLI
- Validates inputs
- Orchestrates calls to business logic layers
- Formats and displays results using Rich

**Example Flow (Direct CLI):**
```python
@app.command()
def collect(file: Path, year: int | None = None):
    # 1. Validate inputs
    # 2. Initialize DocumentCollector
    # 3. Process file
    # 4. Display results
```

**Example Flow (Interactive):**
```python
def _start_interactive_mode():
    # 1. Initialize Agent SDK
    # 2. Display welcome message
    # 3. Start REPL loop
    # 4. Parse slash commands or natural language
    # 5. Route to appropriate handler
    # 6. Display results with streaming
```

---

### 1a. Agent SDK Layer (`agent_sdk.py`)

**Responsibility:** Claude Agent SDK integration for agentic capabilities

**Key Class:** `TaxAgentSDK`

**Methods:**
- `classify_document_async()`: Agentic document classification with verification
- `analyze_documents_async()`: Multi-turn analysis with tool use
- `review_return_async()`: Comprehensive return review with cross-referencing
- `interactive_query_async()`: Conversational tax advice
- `invoke_subagent_async()`: Delegate to specialized subagents

**Agentic Features:**
- Multi-turn reasoning loops (configurable `max_turns`)
- Tool use (`Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch`)
- Streaming responses
- Hook integration for safety and audit
- Subagent delegation

**Configuration:**
```python
sdk_agent = TaxAgentSDK(
    model="claude-sonnet-4-5",
    max_turns=10,
    use_hooks=True  # Enable safety hooks
)
```

---

### 1b. Slash Command System (`slash_commands.py`)

**Responsibility:** Command registry and handlers for interactive mode

**Key Functions:**
- `register_command()`: Register slash commands
- `get_command()`: Retrieve command by name
- `get_completions()`: Tab completion support
- `parse_slash_command()`: Parse user input
- `execute_slash_command()`: Execute and return result

**Registered Commands:**
- `/help` - Show available commands
- `/status` - Display agent status
- `/documents` - Manage collected documents
- `/collect <file>` - Add document
- `/analyze` - Run tax analysis
- `/optimize` - Find deductions
- `/subagent <name>` - Invoke specialist
- `/subagents` - List specialists
- `/review <file>` - Review return
- `/config` - Manage settings

**Command Structure:**
```python
@dataclass
class SlashCommand:
    name: str
    description: str
    handler: Callable[..., str]
    aliases: list[str]
    subcommands: dict[str, SlashCommand]
    requires_init: bool
    usage: str
```

---

### 1c. Subagent System (`subagents.py`)

**Responsibility:** Specialized tax domain experts

**Key Class:** `SubagentDefinition`

**Available Subagents:**

1. **Stock Compensation Analyst** (`stock-compensation-analyst`)
   - RSU, ISO, NSO, ESPP taxation
   - Wash sale detection
   - AMT analysis
   - Cost basis verification

2. **Deduction Finder** (`deduction-finder`)
   - Aggressive deduction discovery
   - Standard vs itemized comparison
   - Credit hunting
   - Bunching strategies

3. **Compliance Auditor** (`compliance-auditor`)
   - Error detection
   - Income verification
   - Audit risk assessment
   - Mathematical checks

4. **Investment Tax Analyst** (`investment-tax-analyst`)
   - Capital gains optimization
   - Dividend classification
   - NIIT calculation
   - Tax-loss harvesting

5. **Retirement Tax Planner** (`retirement-tax-planner`)
   - 401(k), IRA, Roth optimization
   - RMD planning
   - Backdoor Roth strategies
   - Contribution maximization

6. **Self-Employment Specialist** (`self-employment-specialist`)
   - Schedule C analysis
   - SE tax calculation
   - Home office deduction
   - QBI deduction optimization

**Subagent Configuration:**
```python
@dataclass
class SubagentDefinition:
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str]
    max_turns: int
    model: str | None
```

**Usage:**
```python
# Get subagent for task
subagent = get_subagent_for_task("analyze RSU taxation")
# Returns: STOCK_COMPENSATION_ANALYST

# Invoke subagent
result = sdk_agent.invoke_subagent(
    "stock-compensation-analyst",
    "Analyze RSU vesting and sale tax implications",
    source_dir=Path("~/taxes")
)
```

---

### 1d. Safety Hooks (`hooks.py`)

**Responsibility:** Safety, audit, and control mechanisms

**Hook Types:**

**PreToolUse Hooks:**
- `audit_log_hook`: Log all tool invocations
- `sensitive_data_guard`: Restrict file access to tax directories
- `web_access_guard`: Control web tool usage

**PostToolUse Hooks:**
- `audit_log_hook`: Log tool completions
- `ssn_redaction_hook`: Redact SSN from outputs
- `ein_redaction_hook`: Redact EIN from outputs
- `rate_limit_hook`: Track tool usage for rate limiting

**Hook Configuration:**
```python
def get_tax_hooks() -> dict:
    return {
        "PreToolUse": [
            audit_log_hook,
            sensitive_data_guard,
            web_access_guard,
        ],
        "PostToolUse": [
            audit_log_hook,
            ssn_redaction_hook,
            ein_redaction_hook,
            rate_limit_hook,
        ],
    }
```

**File Access Control:**
```python
# Allowed directories
allowed_prefixes = [
    "/tmp/",
    "~/.tax-agent/data/",
    "~/.tax-agent/config/",
]

# Blocks access to other files
if not is_allowed:
    return {
        "permissionDecision": "deny",
        "permissionDecisionReason": "File access restricted"
    }
```

### 2. Document Collectors (`collectors/`)

**Responsibility:** Document ingestion and initial processing

#### `document_classifier.py`

**Purpose:** Orchestrates document collection and classification

**Key Class:** `DocumentCollector`

**Methods:**
- `process_file(file_path, tax_year)`: Process single file
- `process_directory(directory, tax_year)`: Batch process directory
- `process_google_drive_folder(folder_id, tax_year)`: Process from Google Drive

**Processing Steps:**
1. Extract text (via OCR or PDF parser)
2. Compute file hash for deduplication
3. Check for existing documents
4. Redact sensitive data (optional)
5. Classify document using AI
6. Extract structured data based on type
7. Verify extraction against source
8. Store in database

#### `ocr.py`

**Purpose:** Text extraction from images

**Key Function:** `extract_text_with_ocr(file_path)`

**Supported Formats:**
- Images: PNG, JPG, JPEG, TIFF
- PDFs (via pdf2image conversion)

**Process:**
```python
def extract_text_with_ocr(file_path: Path) -> str:
    if file_path.suffix.lower() == '.pdf':
        # Convert PDF to images
        images = convert_from_path(file_path)
        # OCR each page
        text = "\n\n".join(pytesseract.image_to_string(img) for img in images)
    else:
        # Direct OCR on image
        text = pytesseract.image_to_string(Image.open(file_path))
    return text
```

#### `pdf_parser.py`

**Purpose:** Direct PDF text extraction (faster than OCR)

**Key Function:** `extract_text_from_pdf(file_path)`

**Library:** PyMuPDF (fitz)

**Fallback:** If PDF text extraction fails, falls back to OCR

#### `google_drive.py`

**Purpose:** Google Drive integration for document collection

**Key Class:** `GoogleDriveCollector`

**Methods:**
- `authenticate_with_client_file(client_secrets)`: Initial OAuth setup
- `authenticate_interactive()`: Re-authenticate using stored config
- `list_folders(parent_id)`: List folders
- `list_files(folder_id)`: List files in folder
- `download_file(file_id)`: Download file to temp location
- `get_folder_info(folder_id)`: Get folder metadata

**OAuth Flow:**
1. Load client configuration from keyring
2. Run OAuth flow (opens browser)
3. User grants permissions
4. Store tokens in keyring
5. Auto-refresh on subsequent uses

**Supported File Types:**
- PDFs
- Images (PNG, JPG, TIFF)
- Google Docs (exported as PDF)

### 3. AI Agent (`agent.py`)

**Responsibility:** All AI interactions via Claude

**Key Class:** `TaxAgent`

**Provider Support:**
- Anthropic API (default)
- AWS Bedrock (enterprise)

**Methods:**

**Document Classification:**
```python
def classify_document(self, text: str) -> dict:
    # Returns: {
    #   "document_type": "W2",
    #   "confidence": 0.95,
    #   "issuer_name": "Google LLC",
    #   "tax_year": 2024,
    #   "reasoning": "..."
    # }
```

**Data Extraction:**
```python
def extract_w2_data(self, text: str) -> dict
def extract_1099_int_data(self, text: str) -> dict
def extract_1099_div_data(self, text: str) -> dict
def extract_1099_b_data(self, text: str) -> dict
```

**Tax Analysis:**
```python
def analyze_tax_implications(self, docs_summary: str, taxpayer_info: str) -> str
```

**Return Review:**
```python
def review_tax_return(self, return_text: str, source_docs: str) -> str
```

**Model Selection:**
- Default: `claude-3-5-sonnet` (balanced speed/cost/accuracy)
- High-accuracy: `claude-opus-4-20250514` (slower, more expensive)
- Configurable via settings

**System Prompts:**
- Highly detailed prompts for each task
- Focus on accuracy and specificity
- Include verification instructions
- Request structured JSON output where applicable

### 4. Analyzers (`analyzers/`)

**Responsibility:** Tax situation analysis and optimization

#### `implications.py`

**Purpose:** Analyze tax implications from collected documents

**Key Class:** `TaxAnalyzer`

**Methods:**
- `generate_analysis()`: Create comprehensive tax summary
- `generate_ai_analysis()`: Get AI-powered insights

**Output Structure:**
```python
{
    "total_income": float,
    "income_summary": {
        "wages": float,
        "interest": float,
        "dividends_ordinary": float,
        "dividends_qualified": float,
        "capital_gains_short": float,
        "capital_gains_long": float,
        "other": float
    },
    "tax_estimate": {
        "standard_deduction": float,
        "taxable_ordinary_income": float,
        "ordinary_income_tax": float,
        "capital_gains_tax": float,
        "total_tax": float
    },
    "withholding_summary": {...},
    "refund_or_owed": float,
    "estimated_refund": float,
    "estimated_owed": float
}
```

#### `deductions.py`

**Purpose:** Find deductions and tax optimization opportunities

**Key Class:** `TaxOptimizer`

**Methods:**
- `get_interview_questions()`: Generate personalized questions based on documents
- `find_deductions(interview_answers)`: Identify deductions and credits
- `analyze_stock_compensation(comp_type, details)`: Deep-dive stock comp analysis

**Interview Question Types:**
- `yes_no`: Boolean questions
- `number`: Numeric input (dollar amounts)
- `select`: Single choice from options
- `multi_select`: Multiple choices
- `text`: Free-form text

**Deduction Categories:**
- Standard vs. Itemized comparison
- Above-the-line deductions (IRA, HSA, student loan)
- Itemized deductions (mortgage, SALT, charitable)
- Tax credits (education, child, energy)

### 5. Reviewers (`reviewers/`)

**Responsibility:** Tax return review and error detection

#### `error_checker.py`

**Purpose:** Review completed returns for errors and opportunities

**Key Class:** `ReturnReviewer`

**Methods:**
- `review_return(return_file)`: Comprehensive return review

**Review Categories:**
1. **Income Verification**: Match against source documents
2. **Math Errors**: Validate calculations
3. **Deduction Optimization**: Standard vs itemized
4. **Credit Discovery**: Missed credits
5. **Compliance Checks**: Potential IRS red flags

**Finding Severities:**
- `ERROR`: Must be corrected (math errors, missing income)
- `WARNING`: Should be verified (unusual amounts)
- `SUGGESTION`: Optional improvements (missed deductions)
- `INFO`: Informational

### 6. Verification Layer (`verification.py`)

**Responsibility:** Prevent AI hallucinations and validate outputs

**Key Class:** `OutputVerifier`

**Verification Strategies:**

1. **Source Document Validation:**
   - Check extracted values appear in source text
   - Verify numeric values in multiple formats

2. **Sanity Checks:**
   - W-2: Box 1 ≥ Box 3 (wages ≥ SS wages)
   - W-2: Box 2 reasonably proportional to Box 1
   - 1099-B: Proceeds ≥ 0, cost basis reasonable

3. **Cross-Field Validation:**
   - Verify calculations (gain/loss = proceeds - basis)
   - Check short-term vs long-term classification

4. **Confidence Scoring:**
   ```python
   confidence = (verified_fields_count - errors_count) / total_fields
   ```

**Output:**
```python
{
    "verified": bool,
    "confidence": float,  # 0.0 to 1.0
    "issues": [
        {
            "field": str,
            "value": Any,
            "issue": str,
            "severity": "error" | "warning"
        }
    ],
    "verified_fields": [str]
}
```

### 7. Research Module (`research/`)

**Responsibility:** Look up current tax laws and IRS guidance

#### `tax_researcher.py`

**Purpose:** Verify tax rules using live web search

**Key Class:** `TaxResearcher`

**Methods:**
- `research_topic(topic)`: General tax topic research
- `research_current_limits()`: Verify contribution limits
- `check_for_law_changes()`: Identify recent tax law changes
- `verify_state_rules(state)`: State-specific tax rules

**Data Sources:**
- IRS.gov publications and notices
- Revenue procedures
- Tax law databases
- State tax authority websites

### 8. Storage Layer (`storage/`)

**Responsibility:** Persistent data storage with encryption

#### `database.py`

**Purpose:** Encrypted SQLite database management

**Key Class:** `TaxDatabase`

**Schema:**

```sql
-- Tax documents
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    tax_year INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    issuer_name TEXT NOT NULL,
    issuer_ein TEXT,
    recipient_ssn_last4 TEXT,
    raw_text TEXT NOT NULL,
    extracted_data TEXT NOT NULL,  -- JSON
    file_path TEXT,
    file_hash TEXT NOT NULL,
    confidence_score REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Taxpayer profiles
CREATE TABLE taxpayer_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tax_year INTEGER NOT NULL UNIQUE,
    profile_data TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Analysis results (cached)
CREATE TABLE analysis_results (
    id TEXT PRIMARY KEY,
    tax_year INTEGER NOT NULL,
    analysis_type TEXT NOT NULL,
    result_data TEXT NOT NULL,  -- JSON
    created_at TEXT NOT NULL
);
```

**Methods:**
- `save_document(doc)`: Store tax document
- `get_document(id)`: Retrieve by ID
- `get_documents(tax_year)`: List documents for year
- `save_taxpayer_profile(profile)`: Store taxpayer info
- `save_analysis_result(result)`: Cache analysis

**Encryption:**
- Uses SQLCipher for transparent encryption
- AES-256 encryption
- PBKDF2 key derivation (600,000 iterations)
- Falls back to unencrypted SQLite if SQLCipher unavailable (dev mode)

#### `encryption.py`

**Purpose:** Encryption utilities

**Functions:**
- `hash_file(file_path)`: SHA-256 file hash for deduplication
- `redact_sensitive_data(text)`: Remove SSN/EIN from text

**Redaction Patterns:**
```python
# SSN patterns
r'\b\d{3}-\d{2}-\d{4}\b'  # 123-45-6789
r'\b\d{9}\b'              # 123456789

# EIN patterns
r'\b\d{2}-\d{7}\b'        # 12-3456789

# Replacement
"[SSN REDACTED]"
"[EIN REDACTED]"
```

### 9. Configuration (`config.py`)

**Responsibility:** Application configuration and credential management

**Key Class:** `Config`

**Configuration File:** `~/.tax-agent/config.json`

**Settings:**
```json
{
  "tax_year": 2024,
  "state": "CA",
  "filing_status": "single",
  "ai_provider": "anthropic",
  "model": "claude-3-5-sonnet",
  "aws_region": "us-east-1",
  "ocr_engine": "pytesseract",
  "auto_redact_ssn": true,
  "initialized": true
}
```

**Secure Credential Storage (Keyring):**
- `anthropic-api-key`: Claude API key
- `aws-access-key-id`: AWS access key (Bedrock)
- `aws-secret-access-key`: AWS secret (Bedrock)
- `db-encryption-key`: Database password
- `google-drive-credentials`: OAuth tokens
- `google-drive-client-config`: OAuth client config

**Keyring Service:** `tax-prep-agent`

**Platform-Specific Keyrings:**
- macOS: Keychain
- Windows: Credential Manager
- Linux: Secret Service / gnome-keyring

### 10. Data Models (`models/`)

**Responsibility:** Type-safe data structures

#### `documents.py`

**Key Classes:**

```python
class DocumentType(Enum):
    W2 = "W2"
    FORM_1099_INT = "1099_INT"
    FORM_1099_DIV = "1099_DIV"
    FORM_1099_B = "1099_B"
    # ... more types

class TaxDocument(BaseModel):
    id: str
    tax_year: int
    document_type: DocumentType
    issuer_name: str
    issuer_ein: str | None
    recipient_ssn_last4: str | None
    raw_text: str
    extracted_data: dict[str, Any]
    file_path: str | None
    file_hash: str
    confidence_score: float
    needs_review: bool
    created_at: datetime
    updated_at: datetime
```

**Form-Specific Models:**
- `W2Data`: W-2 structured data
- `Form1099IntData`: 1099-INT data
- `Form1099DivData`: 1099-DIV data
- `Form1099BData`: 1099-B with transactions
- `Form1099BTransaction`: Individual stock transaction

#### `returns.py`

**Key Classes:**

```python
class ReviewSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    INFO = "info"

class ReviewFinding(BaseModel):
    severity: ReviewSeverity
    category: str
    title: str
    description: str
    expected_value: Any | None
    actual_value: Any | None
    potential_impact: float | None
    recommendation: str | None

class ReturnReview(BaseModel):
    return_summary: dict
    findings: list[ReviewFinding]
    overall_assessment: str
    errors_count: int
    warnings_count: int
    suggestions_count: int
```

#### `taxpayer.py`

**Key Class:**

```python
class TaxpayerProfile(BaseModel):
    tax_year: int
    filing_status: str | None
    state: str | None
    dependents_count: int
    interview_responses: dict[str, Any]
    created_at: datetime
    updated_at: datetime
```

## Data Flow

### Document Collection Flow

```
1. User Input
   └─> tax-agent collect ~/taxes/w2.pdf

2. CLI Handler (cli.py::collect)
   ├─> Validate file exists
   └─> Initialize DocumentCollector

3. DocumentCollector.process_file()
   ├─> Extract text (OCR or PDF)
   ├─> Compute file hash
   ├─> Check for duplicates (database)
   └─> Redact SSN/EIN (if enabled)

4. TaxAgent.classify_document()
   ├─> Send text to Claude
   ├─> Get classification response
   └─> Return document type + confidence

5. DocumentCollector._extract_data()
   ├─> Call type-specific extractor
   │   └─> TaxAgent.extract_w2_data()
   └─> Return structured data

6. OutputVerifier.verify_extraction()
   ├─> Check values in source text
   ├─> Run sanity checks
   └─> Calculate confidence score

7. Database.save_document()
   ├─> Encrypt (via SQLCipher)
   └─> Store in documents table

8. Display Results
   └─> Rich table with document details
```

### Analysis Flow

```
1. User Input
   └─> tax-agent analyze

2. CLI Handler (cli.py::analyze)
   └─> Initialize TaxAnalyzer(tax_year)

3. TaxAnalyzer.generate_analysis()
   ├─> Database.get_documents(tax_year)
   │   └─> Returns list[TaxDocument]
   │
   ├─> Aggregate income by type
   │   ├─> W-2 Box 1 → wages
   │   ├─> 1099-INT Box 1 → interest
   │   ├─> 1099-DIV Box 1a → dividends
   │   └─> 1099-B summary → capital gains
   │
   ├─> Calculate tax estimate
   │   ├─> Apply standard deduction
   │   ├─> Calculate ordinary income tax (brackets)
   │   └─> Calculate capital gains tax (rates)
   │
   └─> Summarize withholding
       ├─> W-2 Box 2 → federal withholding
       └─> W-2 Box 17 → state withholding

4. TaxAnalyzer.generate_ai_analysis() [if --ai]
   ├─> Format documents summary
   ├─> Format taxpayer info
   ├─> TaxAgent.analyze_tax_implications()
   │   ├─> Send to Claude with analysis prompt
   │   └─> Return AI insights
   └─> Display formatted analysis

5. Display Results
   ├─> Income table
   ├─> Tax estimate table
   ├─> Withholding table
   ├─> Refund/owed amount
   └─> AI analysis panel
```

### Optimization Flow

```
1. User Input
   └─> tax-agent optimize

2. CLI Handler (cli.py::optimize)
   └─> Initialize TaxOptimizer(tax_year)

3. TaxOptimizer.get_interview_questions()
   ├─> Database.get_documents(tax_year)
   ├─> TaxAgent generates contextual questions
   └─> Return question list

4. Interactive Interview Loop
   ├─> For each question:
   │   ├─> Display question
   │   ├─> Get user input
   │   └─> Store answer
   │
   └─> If stock compensation detected:
       ├─> Ask detailed follow-ups
       ├─> TaxOptimizer.analyze_stock_compensation()
       └─> Display specialized analysis

5. TaxOptimizer.find_deductions(answers)
   ├─> Compile document data + interview answers
   ├─> Send to Claude with deduction prompt
   ├─> Parse response
   └─> Return recommendations

6. Display Results
   ├─> Standard vs itemized recommendation
   ├─> Deductions table
   ├─> Credits table
   ├─> Estimated savings
   ├─> Action items
   └─> Warnings
```

### Return Review Flow

```
1. User Input
   └─> tax-agent review ~/taxes/2024_return.pdf

2. CLI Handler (cli.py::review)
   ├─> Validate file exists
   └─> Initialize ReturnReviewer(tax_year)

3. Extract Return Text
   ├─> pdf_parser.extract_text_from_pdf()
   └─> return_text

4. Load Source Documents
   ├─> Database.get_documents(tax_year)
   └─> Format as summary

5. ReturnReviewer.review_return()
   ├─> TaxAgent.review_tax_return(return_text, source_docs)
   │   ├─> Send to Claude with review prompt
   │   └─> Return structured findings
   │
   ├─> Parse AI response
   ├─> Create ReviewFinding objects
   └─> Calculate counts by severity

6. Display Results
   ├─> Review summary panel
   ├─> Overall assessment
   ├─> Findings table (severity, category, impact)
   └─> Detailed findings with recommendations
```

---

## Agent SDK Data Flows

### Interactive Mode Flow

```
1. User Starts Interactive Mode
   └─> tax-agent (no arguments)

2. CLI (cli.py::_start_interactive_mode)
   ├─> Check if SDK available
   ├─> Initialize TaxAgentSDK
   ├─> Load slash command registry
   ├─> Display welcome message
   └─> Start REPL loop

3. User Input Loop
   ├─> Read user input (with tab completion)
   └─> Classify input type

4. Route Input
   ├─> If starts with '/':
   │   ├─> parse_slash_command()
   │   ├─> execute_slash_command()
   │   └─> Display result
   │
   └─> Else (natural language):
       ├─> Prepare context (documents, profile)
       └─> TaxAgentSDK.interactive_query_async()

5. Agent SDK Processing (Natural Language)
   ├─> claude_code_sdk.query()
   ├─> Apply system prompt
   ├─> Enable tools (Read, Grep, WebSearch, etc.)
   ├─> Apply safety hooks
   └─> Stream response chunks

6. Agentic Loop (if needed)
   ├─> Agent decides to use tool
   ├─> PreToolUse hooks run
   │   ├─> audit_log_hook: Log invocation
   │   ├─> sensitive_data_guard: Check permissions
   │   └─> web_access_guard: Validate web access
   │
   ├─> Tool executes (e.g., Read file)
   │
   ├─> PostToolUse hooks run
   │   ├─> audit_log_hook: Log completion
   │   ├─> ssn_redaction_hook: Redact sensitive data
   │   └─> rate_limit_hook: Track usage
   │
   ├─> Agent receives (redacted) tool output
   ├─> Agent continues reasoning
   └─> Loop until max_turns or task complete

7. Display Response
   └─> Stream output to console with Rich formatting
```

### Subagent Invocation Flow

```
1. User Invokes Subagent
   └─> /subagent deduction-finder Find all missed deductions

2. Slash Command Handler
   ├─> parse_slash_command("subagent", ["deduction-finder", "..."])
   └─> cmd_subagent()

3. Subagent Lookup
   ├─> get_subagent("deduction-finder")
   └─> Returns SubagentDefinition

4. TaxAgentSDK.invoke_subagent_async()
   ├─> Load subagent configuration
   │   ├─> system_prompt (deduction-specific)
   │   ├─> allowed_tools (Read, Grep, WebSearch, calculate_tax)
   │   ├─> max_turns (10)
   │   └─> model (default or subagent-specific)
   │
   └─> claude_code_sdk.query() with subagent options

5. Subagent Processing
   ├─> Reads source documents to verify income
   ├─> Searches for deduction patterns
   ├─> Looks up current limits via WebSearch
   ├─> Calculates tax impact
   └─> Returns comprehensive recommendations

6. Stream Results
   └─> Display with deduction categories, amounts, actions
```

### Document Classification with Agent SDK

```
1. DocumentCollector.process_file()
   ├─> Extract text (OCR or PDF)
   └─> TaxAgentSDK.classify_document_async(text, file_path)

2. Agent SDK Classification
   ├─> Apply TAX_DOCUMENT_CLASSIFIER_PROMPT
   ├─> Enable tools: Read, Grep (for verification)
   ├─> max_turns: 3 (limited for performance)
   └─> Start agentic loop

3. Agentic Classification Loop
   ├─> Agent analyzes text
   ├─> If uncertain:
   │   ├─> Uses Grep to search for specific markers
   │   │   (e.g., "Form W-2", "Box 1", "Wages")
   │   └─> Verifies key fields match document type
   │
   ├─> Returns JSON classification:
   │   {
   │     "document_type": "W2",
   │     "document_category": "SOURCE",
   │     "confidence": 0.95,
   │     "issuer_name": "Google LLC",
   │     "tax_year": 2024,
   │     "reasoning": "Verified W-2 via Box labels"
   │   }
   │
   └─> Hooks ensure sensitive data redacted

4. Verification & Storage
   ├─> OutputVerifier.verify_extracted_data()
   ├─> Database.save_document()
   └─> Return result to user
```

### Analysis with Tool Use

```
1. User: /analyze

2. Slash Command Handler
   └─> cmd_analyze()

3. Load Context
   ├─> Database.get_documents() → documents_summary
   └─> get_profile() → taxpayer_info

4. TaxAgentSDK.analyze_documents_async()
   ├─> Apply TAX_ANALYSIS_PROMPT
   ├─> Enable tools: Read, Grep, Glob, WebSearch, WebFetch
   ├─> Set source_dir for file access
   ├─> max_turns: 10 (configurable)
   └─> Start analysis

5. Agentic Analysis
   ├─> Agent reads documents summary
   ├─> Decides to verify W-2 Box 1 amount
   │   ├─> Uses Read to access source document
   │   ├─> Extracts and verifies amount
   │   └─> Confirms accuracy
   │
   ├─> Decides to check current HSA limits
   │   ├─> Uses WebSearch for "HSA contribution limit 2024"
   │   ├─> Parses IRS guidance
   │   └─> Applies to taxpayer situation
   │
   ├─> Performs tax calculations
   ├─> Identifies optimization opportunities
   └─> Streams comprehensive analysis

6. Display Results
   └─> Real-time streaming output with Rich formatting
```

## AI Integration

### Prompt Engineering

**Key Strategies:**

1. **Structured Output Requests:**
   ```python
   "Respond with a JSON object containing: ..."
   ```

2. **Explicit Constraints:**
   ```python
   "Use null for any field you cannot find."
   "Only output the JSON object, no other text."
   ```

3. **Domain-Specific Instructions:**
   ```python
   "You are a tax document classifier specializing in W-2 forms..."
   ```

4. **Verification Requirements:**
   ```python
   "Cross-check EVERY W-2 Box 1 amount against Line 1..."
   ```

5. **Aggressive Tax Optimization:**
   ```python
   "You are an AGGRESSIVE tax advisor whose primary mission is to MINIMIZE..."
   ```

### Response Parsing

**Handling JSON responses:**

```python
try:
    # Clean up markdown code blocks
    response = response.strip()
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("json"):
            response = response[4:]

    return json.loads(response)
except json.JSONDecodeError:
    # Handle error gracefully
    return default_value
```

### Provider Abstraction

**Support for multiple AI providers:**

```python
class TaxAgent:
    def __init__(self, model: str | None = None):
        if config.ai_provider == "aws_bedrock":
            self._init_bedrock(model)
        else:
            self._init_anthropic(model)

    def _call(self, system: str, user_message: str) -> str:
        # Unified interface for both providers
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
```

**Model mapping:**

```python
ANTHROPIC_MODELS = {
    "claude-3-5-sonnet": "claude-3-5-sonnet",
    "claude-opus-4-20250514": "claude-opus-4-20250514",
}

BEDROCK_MODELS = {
    "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-v1:0",
    "claude-opus-4-20250514": "anthropic.claude-opus-4-20250514-v1:0",
}
```

## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────────┐
│ Layer 1: OS-Level Keyring (Credentials)        │
│  • API keys never in plain text                │
│  • Encryption passwords secure                 │
└─────────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────────┐
│ Layer 2: Application-Level Redaction           │
│  • SSN/EIN removed before AI processing        │
│  • Configurable redaction toggle               │
└─────────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────────┐
│ Layer 3: Encrypted Storage (SQLCipher)         │
│  • AES-256 encryption at rest                  │
│  • PBKDF2 key derivation                       │
│  • Transparent encryption/decryption           │
└─────────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────────┐
│ Layer 4: Local Processing First                │
│  • OCR/PDF extraction local                    │
│  • Only processed text sent to cloud           │
└─────────────────────────────────────────────────┘
                    │
┌─────────────────────────────────────────────────┐
│ Layer 5: Verification & Validation             │
│  • AI outputs verified against source          │
│  • Sanity checks on extracted data             │
│  • Confidence scoring                          │
└─────────────────────────────────────────────────┘
```

### Encryption Flow

**Database encryption:**

```python
# Open connection with encryption key
conn = sqlcipher3.connect(db_path)
conn.execute(f"PRAGMA key = '{password}'")

# All operations transparently encrypted
conn.execute("INSERT INTO documents ...")

# Encryption uses:
# - Algorithm: AES-256
# - Mode: CBC
# - Key derivation: PBKDF2
# - Iterations: 600,000 (OWASP recommended)
```

**Credential storage:**

```python
# Store API key securely
keyring.set_password("tax-prep-agent", "anthropic-api-key", api_key)

# Retrieve when needed
api_key = keyring.get_password("tax-prep-agent", "anthropic-api-key")

# Platform-specific backends:
# - macOS: Keychain
# - Windows: Credential Manager
# - Linux: Secret Service API
```

### Data Privacy

**What gets sent to AI:**
```
✓ Document text (after redaction)
✓ Classification requests
✓ Structured data extraction queries
✓ Tax analysis questions
```

**What does NOT get sent to AI:**
```
✗ Full SSN/EIN (redacted to last 4 digits)
✗ File paths
✗ Database contents
✗ Your API keys or passwords
✗ Personal metadata
```

## Storage Layer

### Database Schema Design

**Principles:**
- Document-centric: Each tax form is a separate document
- Year-based partitioning: Easy to query by tax year
- JSON for flexibility: `extracted_data` as JSON for schema evolution
- Audit trail: `created_at` and `updated_at` timestamps

**Indexes for Performance:**
```sql
CREATE INDEX idx_documents_tax_year ON documents(tax_year);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_hash ON documents(file_hash);
```

**Query Patterns:**

```python
# Get all documents for a year
SELECT * FROM documents WHERE tax_year = ?

# Find document by partial ID
SELECT * FROM documents WHERE id LIKE ?

# Check for duplicate by hash
SELECT id FROM documents WHERE file_hash = ?
```

### Data Retention

**Current behavior:**
- Documents persist indefinitely
- Analysis results cached (no automatic expiration)
- No automatic cleanup

**Future considerations:**
- Configurable retention periods
- Export functionality
- Secure deletion (overwrite before delete)

## Extension Points

### Adding New Document Types

1. **Add to DocumentType enum:**
   ```python
   class DocumentType(str, Enum):
       # ...
       FORM_1040_ES = "1040_ES"  # Estimated tax
   ```

2. **Create extraction method in TaxAgent:**
   ```python
   def extract_1040_es_data(self, text: str) -> dict:
       system = """Extract 1040-ES data..."""
       # ... implementation
   ```

3. **Add to DocumentCollector._extract_data():**
   ```python
   elif doc_type == DocumentType.FORM_1040_ES:
       return self.agent.extract_1040_es_data(text)
   ```

4. **Add verification logic (optional):**
   ```python
   def _verify_1040_es(self, data: dict) -> list[dict]:
       # Custom sanity checks
   ```

### Adding New AI Providers

1. **Add provider constant:**
   ```python
   AI_PROVIDER_OPENAI = "openai"
   ```

2. **Add initialization method:**
   ```python
   def _init_openai(self, base_model: str) -> None:
       from openai import OpenAI
       self.client = OpenAI(api_key=...)
       self.model = ...
   ```

3. **Update model mappings:**
   ```python
   OPENAI_MODELS = {
       "gpt-4": "gpt-4-turbo",
       # ...
   }
   ```

4. **Adapt `_call()` method if API differs**

### Adding New Commands

1. **Create command handler in cli.py:**
   ```python
   @app.command()
   def export(format: str = "csv"):
       """Export documents to CSV/JSON."""
       # Implementation
   ```

2. **Add business logic module:**
   ```python
   # src/tax_agent/exporters/csv_exporter.py
   class CSVExporter:
       def export_documents(self, year: int) -> Path:
           # Implementation
   ```

3. **Wire up dependencies**

### Adding State-Specific Logic

**Current:** State stored in config, used in analysis

**Extension pattern:**

```python
# src/tax_agent/state_rules/california.py
class CaliforniaRules:
    STANDARD_DEDUCTION_SINGLE = 5202
    SALT_CAP = None  # CA doesn't cap SALT

    def calculate_state_tax(self, income: float) -> float:
        # CA-specific progressive brackets
        # ...
```

**Integration:**

```python
# In TaxAnalyzer
def get_state_rules(state: str):
    if state == "CA":
        from tax_agent.state_rules.california import CaliforniaRules
        return CaliforniaRules()
    # ...
```

## Performance Considerations

### Bottlenecks

1. **OCR Processing**: 5-15 seconds per page
   - Mitigation: Use PDF text extraction when possible
   - Future: Parallel processing for multi-page documents

2. **AI API Calls**: 2-10 seconds per call
   - Mitigation: Cache analysis results
   - Future: Batch API requests where possible

3. **Database Queries**: Fast (< 100ms) for typical datasets
   - Mitigation: Indexed queries
   - Future: Add more indexes if queries slow down

### Optimization Opportunities

1. **Parallel Document Processing:**
   ```python
   with ThreadPoolExecutor() as executor:
       results = executor.map(process_file, files)
   ```

2. **Result Caching:**
   - Already caches analysis results in database
   - Could cache AI responses with TTL

3. **Lazy Loading:**
   - Don't load `raw_text` unless needed
   - Paginate document lists for large datasets

## Testing Strategy

### Unit Tests

**Collectors:**
- Test OCR with sample images
- Test PDF parsing with sample PDFs
- Mock AI responses for classification tests

**Analyzers:**
- Test income aggregation logic
- Test tax calculation formulas
- Mock database for data retrieval

**Verification:**
- Test sanity checks with valid/invalid data
- Test confidence scoring algorithm

### Integration Tests

**End-to-End Flows:**
- Collect → Analyze → Optimize
- Document upload → Database → Retrieval
- AI classification → Verification

### Test Data

**Sample documents:**
- `tests/fixtures/sample_w2.pdf`
- `tests/fixtures/sample_1099_div.pdf`

**Mock AI responses:**
```python
@pytest.fixture
def mock_ai_classification():
    return {
        "document_type": "W2",
        "confidence": 0.95,
        "issuer_name": "Test Corp",
        "tax_year": 2024
    }
```

## Future Architecture Enhancements

### Planned Improvements

1. **Multi-User Support:**
   - Database per user or user_id column
   - Separate encryption keys per user

2. **Web Interface:**
   - FastAPI backend
   - React frontend
   - Share core business logic with CLI

3. **Mobile App:**
   - Camera document capture
   - Cloud sync with encrypted backend

4. **Audit Trail:**
   - Log all document changes
   - Track analysis history
   - Export audit log

5. **Business Tax Support:**
   - Schedule C logic
   - Partnership/S-corp (K-1) handling
   - Depreciation tracking

6. **Export Capabilities:**
   - TurboTax import format
   - CSV export for spreadsheet users
   - PDF report generation

7. **Collaborative Features:**
   - Share documents with tax preparer
   - Comments and annotations
   - Review workflow

### Architectural Considerations

**Microservices split (if web app):**
```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Web/Mobile  │───▶│  API Gateway │───▶│  Auth Service│
│   Frontend   │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Document    │    │  Analysis    │    │  Storage     │
│  Service     │    │  Service     │    │  Service     │
└──────────────┘    └──────────────┘    └──────────────┘
```

**Database evolution:**
- PostgreSQL for multi-user
- Redis for caching
- S3/Cloud Storage for document files

## Conclusion

The Tax Prep Agent architecture prioritizes:

1. **Privacy**: Encryption, local processing, redaction
2. **Accuracy**: Verification layer, confidence scoring
3. **Extensibility**: Clear separation of concerns, provider abstraction
4. **User Experience**: Rich CLI, comprehensive error handling
5. **Security**: Defense in depth, credential isolation

The modular design allows for easy extension while maintaining code quality and security best practices.
