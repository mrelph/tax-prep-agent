# Web vs CLI Implementation Plan for Tax Prep Agent

## Executive Summary

Based on my analysis of the existing tax-prep-agent codebase and the Claude Agent SDK integration plan, I will present a comprehensive comparison between web-based and CLI-based implementations. The codebase already has a solid foundation with:

- **Core Agent Layer** (`/mnt/c/Coding/tax-prep-agent/src/tax_agent/agent.py`) - Claude API integration
- **Agent SDK Integration** (`/mnt/c/Coding/tax-prep-agent/src/tax_agent/agent_sdk.py`) - Agentic capabilities
- **Storage Layer** (`/mnt/c/Coding/tax-prep-agent/src/tax_agent/storage/database.py`) - Encrypted SQLite with SQLCipher
- **Security Infrastructure** (`/mnt/c/Coding/tax-prep-agent/src/tax_agent/storage/encryption.py`) - SSN redaction, hashing
- **Document Processing** (`/mnt/c/Coding/tax-prep-agent/src/tax_agent/collectors/`) - PDF, OCR, Google Drive

---

## Part 1: CLI-Based Version (Enhanced with Agent SDK)

### Architecture Overview

The current CLI architecture follows this pattern:

```
User CLI (Typer + Rich)
        |
Command Handlers (collect, analyze, review, chat)
        |
+-------+-------+-------+
|               |               |
Collectors    Analyzers    Reviewers
|               |               |
+-------+-------+-------+
        |
TaxAgent/TaxAgentSDK (AI)
        |
+-------+-------+-------+
|               |               |
Storage    Verification   Config
(SQLCipher)               (Keyring)
```

**Enhancement with Agent SDK:**

The `agent_sdk.py` file already provides the foundation. Key enhancements needed:

1. **Agentic Loops**: Multi-turn document verification
2. **Tool Use**: Built-in Read/Grep/WebSearch/WebFetch tools
3. **Streaming**: Real-time response streaming in terminal
4. **Session Management**: Persistent chat context via `ClaudeSDKClient`

### User Experience Flow (CLI)

```
1. tax-agent init
   - Create encrypted database
   - Store API key in keyring
   - Configure tax year/state

2. tax-agent collect <file>
   - Local OCR/PDF extraction
   - Agent SDK classifies with verification loop
   - Structured data extraction
   - Storage in encrypted DB

3. tax-agent analyze --agentic
   - Agent reads source documents via tools
   - Cross-references with web for current IRS limits
   - Multi-turn analysis with self-correction
   - Streaming output to terminal

4. tax-agent chat
   - Interactive session with full tool access
   - Context maintained across messages
   - Can reference collected documents
```

### Technology Stack (CLI Enhanced)

| Component | Current | Enhanced |
|-----------|---------|----------|
| CLI Framework | Typer + Rich | Same |
| AI Client | Anthropic SDK | Claude Agent SDK |
| Async Support | Limited | Full async/await |
| Tool Access | None | Read, Grep, WebSearch, etc. |
| Session Mgmt | Manual history | ClaudeSDKClient sessions |

### File Upload/Document Handling (CLI)

Current implementation in `document_classifier.py` and `collectors/`:

```python
# Existing pattern - works for CLI
def process_file(file_path: Path, tax_year: int):
    # 1. Extract text (OCR or PDF parser)
    if is_pdf_scanned(file_path):
        text = extract_text_with_ocr(file_path)
    else:
        text = extract_pdf_text(file_path)

    # 2. Redact SSN if configured
    if config.auto_redact_ssn:
        text = redact_sensitive_data(text)

    # 3. Classify and extract
    classification = agent.classify_document(text)
    # ...
```

### Session Management (CLI)

Current chat implementation in `chat.py`:

```python
class TaxAdvisorChat:
    def __init__(self):
        self.conversation_history: list[dict] = []

    def chat(self, user_message: str) -> str:
        # Manual history management
        self.conversation_history.append({"role": "user", "content": user_message})
        response = self.agent._call(system, user_message)
        self.conversation_history.append({"role": "assistant", "content": response})
```

**Enhanced with Agent SDK**:

```python
class TaxAdvisorChatSDK:
    async def start_session(self) -> None:
        self.client = ClaudeSDKClient(options=options)
        await self.client.connect()

    async def chat(self, user_message: str) -> str:
        # SDK handles session automatically
        await self.client.query(user_message)
        async for message in self.client.receive_response():
            yield message
```

### Real-time Streaming (CLI)

Current: Single response returned after completion

Enhanced with Agent SDK:

```python
@app.command()
@async_command
async def analyze_interactive():
    agent = TaxAgentSDK(get_config())

    with console.status("[cyan]Analyzing...[/cyan]"):
        async for message in agent.analyze_documents_async(...):
            console.print(message.text, end="")  # Stream to terminal
```

### Security Considerations (CLI)

**Current Implementation (Excellent Foundation):**

1. **Keyring Storage** (`config.py`):
   - API keys stored in OS keyring
   - Database password in keyring
   - Google OAuth tokens in keyring

2. **SSN Redaction** (`encryption.py`):
   ```python
   def redact_ssn(text: str) -> str:
       pattern_dashed = r"\b\d{3}-\d{2}-\d{4}\b"
       return re.sub(pattern_dashed, "[SSN REDACTED]", text)
   ```

3. **Encrypted Database** (`database.py`):
   ```python
   conn = sqlcipher3.connect(str(self.db_path))
   conn.execute(f"PRAGMA key = '{self._password}'")
   ```

**Agent SDK Additions**:

```python
async def sensitive_data_guard(input_data: dict, ...):
    """Block access to files outside tax context."""
    if input_data.get("tool_name") == "Read":
        file_path = input_data.get("tool_input", {}).get("file_path", "")
        if not is_allowed_path(file_path):
            return {"permissionDecision": "deny"}
```

### Deployment Options (CLI)

1. **PyPI Package**: `pip install tax-prep-agent`
2. **Homebrew**: For macOS users
3. **Docker**: Containerized with Tesseract pre-installed
4. **Windows MSI**: Bundled installer with dependencies

---

## Part 2: Web-Based Version

### Architecture Overview

```
+--------------------+
|   React Frontend   |
| (Next.js/Vite)     |
+--------------------+
         |
+--------------------+
|   API Gateway      |
| (FastAPI/Express)  |
+--------------------+
         |
+--------------------+
|   Shared Core      |
| (tax_agent.*)      |
+--------------------+
         |
+--------+--------+
|                 |
+--------+  +--------+
|Storage |  |Agent   |
|(DB)    |  |(SDK)   |
+--------+  +--------+
```

### Technology Stack (Web)

| Layer | Recommended Technology | Rationale |
|-------|----------------------|-----------|
| **Frontend** | Next.js 14 + React | SSR, file handling, TypeScript |
| **UI Components** | Tailwind + shadcn/ui | Clean tax forms, accessibility |
| **API** | FastAPI (Python) | Reuse existing Python core |
| **Real-time** | WebSockets + SSE | Stream agent responses |
| **Auth** | NextAuth.js + JWT | Multi-user support |
| **File Upload** | React Dropzone + presigned URLs | Large file handling |
| **Database** | PostgreSQL + pgcrypto | Multi-user, encrypted columns |
| **Cache** | Redis | Session state, rate limiting |
| **File Storage** | S3/R2 (encrypted) | Document storage |

### User Experience Flow (Web)

```
1. Landing Page / Login
   - OAuth (Google/GitHub) or email/password
   - MFA for extra security

2. Dashboard
   - Tax year selector
   - Document overview cards
   - Quick actions: Upload, Analyze, Chat

3. Document Upload
   - Drag-and-drop zone
   - Progress indicators
   - Real-time classification status
   - Preview extracted data

4. Analysis View
   - Streaming AI analysis
   - Interactive charts (income breakdown)
   - Collapsible sections
   - Export to PDF

5. Chat Interface
   - Persistent sidebar or modal
   - Message history
   - Typing indicators
   - Reference document links
```

### File Upload/Document Handling (Web)

**Frontend (React)**:
```typescript
// Chunked upload with progress
const uploadDocument = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('taxYear', taxYear.toString());

  const response = await fetch('/api/documents/upload', {
    method: 'POST',
    body: formData,
    headers: { 'Authorization': `Bearer ${token}` }
  });

  // WebSocket for processing status
  const ws = new WebSocket(`/ws/processing/${response.documentId}`);
  ws.onmessage = (event) => {
    const status = JSON.parse(event.data);
    setProcessingStatus(status);  // OCR progress, classification, etc.
  };
};
```

**Backend (FastAPI)**:
```python
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    tax_year: int,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks
):
    # Save to temp location
    temp_path = await save_upload(file)

    # Create document record
    doc_id = await create_document_record(current_user.id, tax_year, temp_path)

    # Process async
    background_tasks.add_task(process_document_async, doc_id, temp_path)

    return {"documentId": doc_id, "status": "processing"}
```

### Session Management (Web)

**Multi-user Sessions**:
```python
# Redis-backed session state
class SessionManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def get_chat_session(self, user_id: str, session_id: str):
        key = f"chat:{user_id}:{session_id}"
        history = await self.redis.lrange(key, 0, -1)
        return [json.loads(msg) for msg in history]

    async def add_message(self, user_id: str, session_id: str, message: dict):
        key = f"chat:{user_id}:{session_id}"
        await self.redis.rpush(key, json.dumps(message))
        await self.redis.expire(key, 86400 * 30)  # 30 day TTL
```

### Real-time Streaming (Web)

**Server-Sent Events for Agent Responses**:
```python
@router.get("/chat/{session_id}/stream")
async def stream_response(
    session_id: str,
    message: str,
    current_user: User = Depends(get_current_user)
):
    async def event_generator():
        sdk_agent = TaxAgentSDK()
        async for chunk in sdk_agent.interactive_query_async(message):
            yield {
                "event": "message",
                "data": json.dumps({"text": chunk})
            }
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_generator())
```

**Frontend SSE Handler**:
```typescript
const streamChat = (message: string) => {
  const eventSource = new EventSource(
    `/api/chat/${sessionId}/stream?message=${encodeURIComponent(message)}`
  );

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    setMessages(prev => [...prev, { role: 'assistant', content: data.text }]);
  };

  eventSource.addEventListener('done', () => eventSource.close());
};
```

### Security Considerations (Web)

**Additional Web-Specific Security**:

| Concern | Solution |
|---------|----------|
| **SSN in transit** | TLS 1.3, redact before API |
| **SSN in storage** | Column-level encryption (pgcrypto) |
| **SSN in memory** | Process, redact, discard |
| **Auth tokens** | HttpOnly cookies, short expiry |
| **CSRF** | SameSite cookies, CSRF tokens |
| **Rate limiting** | Redis-based per-user limits |
| **File uploads** | Virus scanning, size limits |
| **API keys** | Server-side only, env vars |

**Database Schema with Encryption**:
```sql
-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Documents with encrypted fields
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    tax_year INT NOT NULL,
    document_type TEXT NOT NULL,
    -- Encrypted: contains SSN references
    raw_text_encrypted BYTEA,
    extracted_data_encrypted BYTEA,
    -- Not encrypted: for queries
    issuer_name TEXT,
    file_hash TEXT,
    confidence_score REAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Encryption with pgcrypto
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt on insert
INSERT INTO documents (raw_text_encrypted, ...)
VALUES (pgp_sym_encrypt($1, $encryption_key), ...);

-- Decrypt on read
SELECT pgp_sym_decrypt(raw_text_encrypted, $encryption_key) as raw_text
FROM documents WHERE user_id = $user_id;
```

### Deployment Options (Web)

| Platform | Pros | Cons |
|----------|------|------|
| **Vercel + Railway** | Easy, auto-scaling | Cost at scale |
| **AWS (ECS/Lambda)** | Full control, compliance | Complex setup |
| **Self-hosted** | Data control | Maintenance burden |
| **Fly.io** | Good DX, edge deploys | Smaller ecosystem |

**Recommended Production Stack**:
```
Frontend: Vercel (Next.js)
API: Railway or Render (FastAPI)
Database: Neon or Supabase (Postgres)
Cache: Upstash Redis
Storage: Cloudflare R2 (S3-compatible)
OCR: Google Cloud Vision API (for web uploads)
```

---

## Part 3: Comparison Matrix

### Development Effort

| Aspect | CLI (Enhanced) | Web (New) |
|--------|---------------|-----------|
| **Core Logic** | Already exists | Reuse from CLI |
| **UI/UX** | Rich terminal (done) | 2-3 weeks new |
| **Auth System** | Keyring (done) | 1-2 weeks new |
| **File Upload** | Local paths (done) | 1 week new |
| **Streaming** | 2-3 days new | 1 week new |
| **Agent SDK** | 1 week integration | Same |
| **Database** | SQLite (done) | PostgreSQL migration |
| **Testing** | Existing + new | New test suite |
| **Documentation** | Update existing | Write from scratch |
| **Total Estimate** | 2-3 weeks | 6-8 weeks |

### User Accessibility

| Factor | CLI | Web |
|--------|-----|-----|
| **Technical Users** | Excellent | Good |
| **Non-technical Users** | Poor | Excellent |
| **Mobile Access** | None | Possible (responsive) |
| **Installation** | Required | None (browser) |
| **Updates** | Manual (`pip upgrade`) | Automatic |
| **Offline Use** | Full | Limited |
| **Learning Curve** | Higher | Lower |

### Feature Parity

| Feature | CLI | Web |
|---------|-----|-----|
| **Document Collection** | Full | Full |
| **OCR Processing** | Local (fast) | Cloud API (cost) |
| **Classification** | Same | Same |
| **Analysis** | Same | Same + visualizations |
| **Chat** | Terminal | Rich UI |
| **Export** | MD/PDF | MD/PDF + online share |
| **Google Drive** | OAuth flow | Seamless integration |
| **Batch Processing** | Excellent | Possible |
| **Scripting** | Native | API-based |

### Maintenance Complexity

| Aspect | CLI | Web |
|--------|-----|-----|
| **Dependencies** | Python only | Python + Node + DB |
| **Deployment** | PyPI | Multi-service |
| **Monitoring** | Local logs | Observability stack |
| **Updates** | Single package | Frontend + Backend + DB |
| **Scaling** | N/A (local) | Required |
| **Security Patches** | OS keyring | Multiple surfaces |

### Cost Considerations

| Cost Type | CLI | Web |
|-----------|-----|-----|
| **Development** | $15-25k | $40-60k |
| **Hosting** | $0 (local) | $50-500/month |
| **API (Claude)** | Pay per use | Same |
| **OCR (Cloud)** | $0 (local) | $1-5/1000 pages |
| **Database** | $0 (SQLite) | $20-100/month |
| **CDN/Storage** | $0 | $10-50/month |
| **Maintenance** | Low | Medium-High |

---

## Part 4: Hybrid Approach

### Shared Backend Architecture

```
+------------------+     +------------------+
|   CLI Client     |     |   Web Client     |
| (Typer + Rich)   |     | (React/Next.js)  |
+------------------+     +------------------+
         |                       |
         |   +-----------------+ |
         +-->|   FastAPI Core  |<+
             |                 |
             | /api/documents  |
             | /api/analyze    |
             | /api/chat       |
             | /api/export     |
             +-----------------+
                    |
         +----------+----------+
         |                     |
+------------------+  +------------------+
|   tax_agent.*    |  |   Agent SDK      |
| (Business Logic) |  | (AI Operations)  |
+------------------+  +------------------+
         |                     |
+------------------+  +------------------+
|   Database       |  |   File Storage   |
| (SQLite/Postgres)|  | (Local/S3)       |
+------------------+  +------------------+
```

### API Design for Shared Services

**OpenAPI Specification**:
```yaml
openapi: 3.0.0
info:
  title: Tax Prep Agent API
  version: 1.0.0

paths:
  /api/documents:
    post:
      summary: Upload and process document
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                tax_year:
                  type: integer
    get:
      summary: List documents
      parameters:
        - name: tax_year
          in: query
          schema:
            type: integer

  /api/analyze:
    post:
      summary: Run tax analysis
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                tax_year:
                  type: integer
                agentic:
                  type: boolean

  /api/chat:
    post:
      summary: Send chat message
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                session_id:
                  type: string
                message:
                  type: string

  /api/chat/{session_id}/stream:
    get:
      summary: Stream chat response (SSE)
```

### Code Reuse Opportunities

**Current Reusable Modules**:

| Module | CLI Use | Web Reuse | Changes Needed |
|--------|---------|-----------|----------------|
| `agent.py` | Direct | 100% | None |
| `agent_sdk.py` | Direct | 100% | None |
| `chat.py` | Direct | 90% | Add user_id param |
| `verification.py` | Direct | 100% | None |
| `models/*.py` | Direct | 100% | None |
| `collectors/*.py` | Direct | 80% | Async uploads |
| `analyzers/*.py` | Direct | 100% | None |
| `reviewers/*.py` | Direct | 100% | None |
| `storage/database.py` | Direct | 70% | PostgreSQL adapter |
| `storage/encryption.py` | Direct | 100% | None |
| `config.py` | Direct | 50% | Web config pattern |
| `cli.py` | Direct | 0% | CLI-only |

**Refactored Core Package Structure**:
```
tax_agent/
├── core/                    # Shared business logic
│   ├── agent.py            # AI operations
│   ├── agent_sdk.py        # Agent SDK wrapper
│   ├── analysis/           # Tax analysis
│   ├── collectors/         # Document processing
│   ├── reviewers/          # Return review
│   └── verification.py     # Output validation
├── models/                  # Pydantic models (shared)
├── storage/
│   ├── base.py             # Abstract storage interface
│   ├── sqlite.py           # SQLite implementation (CLI)
│   └── postgres.py         # PostgreSQL implementation (Web)
├── adapters/
│   ├── cli/                # CLI-specific code
│   │   ├── commands.py
│   │   └── display.py
│   └── api/                # Web API-specific code
│       ├── routes.py
│       └── auth.py
```

### Database Abstraction Layer

```python
# storage/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from tax_agent.models.documents import TaxDocument

class TaxStorageBase(ABC):
    @abstractmethod
    async def save_document(self, doc: TaxDocument, user_id: Optional[str] = None) -> str:
        pass

    @abstractmethod
    async def get_documents(
        self,
        tax_year: int,
        user_id: Optional[str] = None
    ) -> List[TaxDocument]:
        pass

    @abstractmethod
    async def get_document(self, doc_id: str, user_id: Optional[str] = None) -> Optional[TaxDocument]:
        pass

# storage/sqlite.py (CLI)
class SQLiteStorage(TaxStorageBase):
    def __init__(self, db_path: Path, password: str):
        self.db = TaxDatabase(db_path, password)

    async def save_document(self, doc: TaxDocument, user_id: Optional[str] = None) -> str:
        # Ignore user_id for single-user CLI
        self.db.save_document(doc)
        return doc.id

# storage/postgres.py (Web)
class PostgresStorage(TaxStorageBase):
    def __init__(self, connection_string: str, encryption_key: str):
        self.pool = asyncpg.create_pool(connection_string)
        self.encryption_key = encryption_key

    async def save_document(self, doc: TaxDocument, user_id: str) -> str:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO documents (id, user_id, tax_year, ...)
                VALUES ($1, $2, $3, pgp_sym_encrypt($4, $5), ...)
                """,
                doc.id, user_id, doc.tax_year, doc.raw_text, self.encryption_key
            )
        return doc.id
```

---

## Part 5: Implementation Recommendations

### Which to Build First: CLI

**Rationale**:

1. **Foundation exists** - The codebase is already CLI-first
2. **Agent SDK integration** - Can be completed in 2-3 weeks
3. **Validates core logic** - Ensures analysis/chat works before web
4. **Developer adoption** - Tax developers prefer CLI tools
5. **Lower risk** - Less infrastructure, faster iteration

**CLI Enhancement Roadmap**:

| Week | Deliverable |
|------|-------------|
| 1 | Agent SDK full integration (async, streaming) |
| 2 | Custom MCP tools (tax calculations, limits lookup) |
| 3 | Safety hooks (file access control, SSN redaction) |
| 4 | Testing, documentation, PyPI release |

### When to Start Web Version

**After CLI Enhanced is stable**:

1. **API layer extraction** - Refactor CLI to use internal API
2. **Database abstraction** - Implement PostgreSQL adapter
3. **Web frontend** - Build React UI with streaming support
4. **Auth system** - Add multi-user authentication
5. **Cloud deployment** - Set up infrastructure

**Web Development Roadmap**:

| Week | Deliverable |
|------|-------------|
| 1-2 | FastAPI backend with shared core |
| 3-4 | PostgreSQL migration, auth system |
| 5-6 | React frontend, document upload |
| 7-8 | Chat UI, streaming, export |
| 9-10 | Testing, security audit, deploy |

### Migration Path Between Versions

**CLI to Web Migration for Users**:

```bash
# Export from CLI
tax-agent export --format json --output ~/tax-data-2024.json

# Import to Web (via API)
curl -X POST https://app.taxprep.ai/api/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@tax-data-2024.json"
```

**Data Compatibility**:
- JSON export format includes all document data
- Database schema compatible (same Pydantic models)
- File hashes ensure no duplicate uploads

### Shared Components Summary

| Component | Location | Used By |
|-----------|----------|---------|
| `TaxAgent` | `core/agent.py` | Both |
| `TaxAgentSDK` | `core/agent_sdk.py` | Both |
| `TaxDocument` | `models/documents.py` | Both |
| `OutputVerifier` | `core/verification.py` | Both |
| `DocumentCollector` | `core/collectors/` | Both (async for web) |
| `TaxAnalyzer` | `core/analysis/` | Both |
| `ReturnReviewer` | `core/reviewers/` | Both |
| `redact_ssn` | `core/encryption.py` | Both |
| Tax rules YAML | `data/tax_rules/` | Both |

---

## Appendix: Critical Files for Implementation

1. **`src/tax_agent/agent_sdk.py`** - Core Agent SDK integration that needs enhancement with full streaming, custom MCP tools, and safety hooks

2. **`src/tax_agent/storage/database.py`** - Database layer that needs abstraction for PostgreSQL support in web version

3. **`src/tax_agent/agent.py`** - Legacy agent that provides the baseline AI operations and will be wrapped by both versions

4. **`src/tax_agent/chat.py`** - Chat implementation that needs ClaudeSDKClient integration for session management

5. **`docs/agent-sdk-plan.md`** - Detailed Agent SDK integration plan with code patterns to follow
