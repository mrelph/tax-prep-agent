# Claude Agent SDK Integration Plan for Tax Prep Agent

## Executive Summary

This plan details how to migrate the tax-prep-agent from the direct Anthropic Python SDK (`anthropic`) to the Claude Agent SDK (`claude-agent-sdk`). The Agent SDK provides significant advantages for this project including built-in tool execution, agentic loops, session management, custom tool definitions, and hooks for controlling agent behavior.

## 1. What is the Claude Agent SDK?

The Claude Agent SDK (formerly Claude Code SDK) provides the same tools, agent loop, and context management that power Claude Code, but programmable in Python and TypeScript. Unlike the direct Anthropic SDK which is purely an API client, the Agent SDK enables building autonomous AI agents.

### Key Differences from Standard Anthropic SDK

| Feature | Current (Anthropic SDK) | Claude Agent SDK |
|---------|------------------------|------------------|
| **Architecture** | Stateless API calls | Agentic loops with state |
| **Tool Execution** | Must implement yourself | Built-in tools (Read, Write, Bash, Grep, etc.) |
| **Conversation** | Manual message management | Session-based with automatic context |
| **Custom Tools** | Not native | In-process MCP servers with `@tool` decorator |
| **Hooks** | Not available | PreToolUse, PostToolUse, Stop, etc. |
| **File Operations** | Text-based only | Direct file access capabilities |
| **Subagents** | Not available | Native subagent support |
| **Permissions** | Manual | Built-in permission modes |

## 2. Current Implementation Analysis

### Current Architecture (`src/tax_agent/agent.py`)

The current `TaxAgent` class uses the Anthropic SDK directly:

```python
# Current pattern - stateless API calls
class TaxAgent:
    def __init__(self, model: str | None = None):
        self.client = Anthropic(api_key=api_key)  # or AnthropicBedrock

    def _call(self, system: str, user_message: str, max_tokens: int = 4096) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
```

### Current Features Using Claude

1. **Document Classification** (`classify_document`) - Single API call with JSON response
2. **Data Extraction** (`extract_w2_data`, `extract_1099_*_data`) - Structured JSON extraction
3. **Tax Analysis** (`analyze_tax_implications`) - Long-form analysis text
4. **Return Review** (`review_tax_return`) - Structured findings
5. **Cross-Reference Validation** (`validate_documents_cross_reference`) - JSON validation results
6. **Audit Risk Assessment** (`assess_audit_risk`) - Risk scoring
7. **Filing Scenario Comparison** (`compare_filing_scenarios`) - Multi-scenario analysis
8. **Investment Tax Analysis** (`analyze_investment_taxes`) - Complex calculations
9. **Tax Planning** (`generate_tax_planning_recommendations`) - Forward-looking advice

### Current Limitations

1. **No Agentic Loops** - Each analysis is a single call; cannot iterate or self-correct
2. **No Tool Use** - Cannot read additional files or verify data during analysis
3. **Stateless** - Chat module manually manages conversation history
4. **No Interruption** - Long analyses cannot be interrupted
5. **Manual JSON Parsing** - Brittle parsing of Claude's responses
6. **No Verification Actions** - Cannot verify calculations or cross-reference IRS data

## 3. Benefits of Agent SDK for Tax Prep Agent

### 3.1 Built-in Tools Enable New Capabilities

| Tool | Tax Application |
|------|-----------------|
| **Read** | Read additional documents during analysis, verify source data |
| **Grep** | Search across documents for specific values, patterns |
| **Glob** | Find all documents matching patterns (e.g., all W-2s) |
| **WebFetch** | Look up current IRS limits, tax rules, form instructions |
| **WebSearch** | Research tax law changes, state-specific rules |
| **Bash** | Run calculations, validate data, generate reports |
| **Write** | Generate tax planning reports, export summaries |

### 3.2 Agentic Loops for Complex Analysis

Instead of single-shot analysis, the agent can:
- Review a tax return, identify issues, re-read source documents to verify
- Discover a discrepancy, search for related transactions, propose corrections
- Generate optimization recommendations, verify each against current IRS rules

### 3.3 Interactive Document Review

With `ClaudeSDKClient` and session management:
- Multi-turn conversation about tax situation
- Agent remembers context between questions
- Can interrupt long analyses if user spots an issue

### 3.4 Custom Tax Tools via MCP

Create specialized tools:
- `calculate_tax_bracket` - Tax bracket calculations
- `check_contribution_limits` - Verify 401k/IRA limits
- `wash_sale_detector` - Analyze transactions for wash sales
- `state_tax_calculator` - State-specific calculations

### 3.5 Hooks for Safety and Auditing

- **PreToolUse**: Validate Claude is not accessing files outside tax documents
- **PostToolUse**: Log all tool usage for audit trail
- **Stop**: Ensure sensitive data handling before termination

## 4. Detailed Implementation Plan

### Phase 1: Foundation

#### 1.1 Install and Configure Agent SDK

**File: `pyproject.toml`**
```toml
dependencies = [
    # Replace: "anthropic>=0.40.0",
    "claude-agent-sdk>=0.1.10",
    # Keep other dependencies
]
```

**Requirements:**
- Python 3.10+ (currently 3.11+, compatible)
- Node.js 18+ (for Claude Code CLI bundled with SDK)

#### 1.2 Create New Agent Module

**New File: `src/tax_agent/agent_sdk.py`**

```python
"""Claude Agent SDK integration for tax document analysis."""

from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
)
from typing import Any, AsyncIterator
import asyncio

class TaxAgentSDK:
    """Agent SDK-powered tax agent with tool use and agentic loops."""

    def __init__(self, config: "Config"):
        self.config = config
        self.tax_tools = self._create_tax_tools()
        self.options = self._build_options()

    def _build_options(self) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            system_prompt=self._get_tax_system_prompt(),
            mcp_servers={"tax_tools": self.tax_tools},
            allowed_tools=[
                "Read", "Grep", "Glob", "WebFetch", "WebSearch",
                "mcp__tax_tools__calculate_tax",
                "mcp__tax_tools__check_limits",
                "mcp__tax_tools__detect_wash_sales",
            ],
            permission_mode="bypassPermissions",  # For automated analysis
            cwd=str(self.config.data_dir),
        )

    async def analyze_documents(self, prompt: str) -> AsyncIterator[Any]:
        """Run agentic document analysis."""
        async for message in query(prompt=prompt, options=self.options):
            yield message
```

#### 1.3 Create Custom Tax Tools

**New File: `src/tax_agent/tools/tax_calculations.py`**

```python
"""Custom MCP tools for tax calculations."""

from claude_agent_sdk import tool, create_sdk_mcp_server
from typing import Any
from datetime import datetime

@tool(
    "calculate_tax",
    "Calculate federal income tax for given income and filing status",
    {"income": float, "filing_status": str, "tax_year": int}
)
async def calculate_tax(args: dict[str, Any]) -> dict[str, Any]:
    """Calculate federal income tax using current brackets."""
    income = args["income"]
    filing_status = args["filing_status"]
    year = args.get("tax_year", datetime.now().year)

    # Tax brackets would be loaded from data
    tax = calculate_from_brackets(income, brackets.get(filing_status))

    return {
        "content": [{
            "type": "text",
            "text": f"Tax on ${income:,.2f} as {filing_status}: ${tax:,.2f}"
        }]
    }

@tool(
    "check_contribution_limits",
    "Check IRS contribution limits for retirement accounts",
    {"account_type": str, "age": int, "tax_year": int}
)
async def check_contribution_limits(args: dict[str, Any]) -> dict[str, Any]:
    """Return current contribution limits."""
    limits = {
        "401k": {"regular": 23000, "catch_up": 7500, "catch_up_age": 50},
        "ira": {"regular": 7000, "catch_up": 1000, "catch_up_age": 50},
        "hsa_individual": {"regular": 4150},
        "hsa_family": {"regular": 8300},
    }
    # ... implementation
    return {"content": [{"type": "text", "text": result}]}

@tool(
    "detect_wash_sales",
    "Analyze transactions for wash sale violations",
    {"transactions": list}
)
async def detect_wash_sales(args: dict[str, Any]) -> dict[str, Any]:
    """Detect wash sales in transaction list."""
    # Analyze 30-day windows around each sale at a loss
    # ... implementation
    return {"content": [{"type": "text", "text": result}]}

def create_tax_tools_server():
    """Create the MCP server with all tax tools."""
    return create_sdk_mcp_server(
        name="tax_tools",
        version="1.0.0",
        tools=[calculate_tax, check_contribution_limits, detect_wash_sales]
    )
```

### Phase 2: Migrate Core Functions

#### 2.1 Document Classification with Agentic Loop

Replace single-call classification with agentic verification:

```python
async def classify_document_agentic(self, file_path: Path, text: str) -> dict:
    """Classify document using agentic loop that can verify uncertain classifications."""
    options = ClaudeAgentOptions(
        system_prompt="""You are a tax document classifier. When classifying:
1. First identify the document type from visual cues and content
2. If uncertain, use the Grep tool to search for specific markers
3. Verify your classification by checking key fields match the form type
4. Return a JSON classification with confidence score""",
        allowed_tools=["Read", "Grep"],
        cwd=str(file_path.parent),
        max_turns=3,
    )

    result = {}
    async for message in query(
        prompt=f"Classify this tax document:\n\n{text[:8000]}",
        options=options
    ):
        if hasattr(message, 'result'):
            result = parse_classification(message.result)

    return result
```

#### 2.2 Interactive Chat with Session Management

Replace manual history management with ClaudeSDKClient:

```python
class TaxAdvisorChatSDK:
    """Interactive chat using Agent SDK for session management."""

    def __init__(self, tax_year: int | None = None):
        self.tax_year = tax_year or get_config().tax_year
        self.client: ClaudeSDKClient | None = None

    async def start_session(self) -> None:
        """Start a new chat session."""
        options = ClaudeAgentOptions(
            system_prompt=self._build_tax_advisor_prompt(),
            allowed_tools=["Read", "Grep", "WebSearch", "WebFetch",
                          "mcp__tax_tools__calculate_tax"],
            mcp_servers={"tax_tools": create_tax_tools_server()},
        )

        self.client = ClaudeSDKClient(options=options)
        await self.client.connect()

    async def chat(self, user_message: str) -> str:
        """Send message and get response with full context."""
        if not self.client:
            await self.start_session()

        await self.client.query(user_message)

        response_parts = []
        async for message in self.client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_parts.append(block.text)

        return "".join(response_parts)
```

### Phase 3: Advanced Features

#### 3.1 Implement Safety Hooks

**New File: `src/tax_agent/hooks.py`**

```python
"""Safety and audit hooks for tax agent."""

from claude_agent_sdk import HookMatcher, HookContext
from typing import Any
import logging

logger = logging.getLogger("tax_agent.audit")

async def audit_log_hook(input_data: dict, tool_use_id: str | None, context: HookContext) -> dict:
    """Log all tool usage for audit trail."""
    tool_name = input_data.get("tool_name", "unknown")
    logger.info(f"Tool used: {tool_name}")
    return {}

async def sensitive_data_guard(input_data: dict, tool_use_id: str | None, context: HookContext) -> dict:
    """Block access to files outside tax context."""
    if input_data.get("tool_name") == "Read":
        file_path = input_data.get("tool_input", {}).get("file_path", "")
        allowed_prefixes = ["/tmp/", str(get_config().data_dir)]
        if not any(file_path.startswith(prefix) for prefix in allowed_prefixes):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"File access restricted: {file_path}"
                }
            }
    return {}

async def ssn_redaction_hook(input_data: dict, tool_use_id: str | None, context: HookContext) -> dict:
    """Redact SSNs from tool outputs."""
    import re
    if "tool_result" in input_data:
        result = str(input_data["tool_result"])
        redacted = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN REDACTED]', result)
        if redacted != result:
            return {"hookSpecificOutput": {"updatedResult": redacted}}
    return {}

def get_tax_hooks() -> dict:
    return {
        "PreToolUse": [
            HookMatcher(hooks=[audit_log_hook]),
            HookMatcher(matcher="Read|Write", hooks=[sensitive_data_guard]),
        ],
        "PostToolUse": [
            HookMatcher(hooks=[audit_log_hook, ssn_redaction_hook]),
        ],
    }
```

#### 3.2 Subagents for Specialized Analysis

```python
"""Specialized subagents for tax analysis domains."""

from claude_agent_sdk import AgentDefinition

TAX_SUBAGENTS = {
    "stock-compensation-analyst": AgentDefinition(
        description="Expert in RSU, ISO, NSO, and ESPP taxation",
        prompt="""You are an expert in equity compensation taxation.
Analyze: tax treatment at vesting/exercise/sale, AMT implications, wash sales.""",
        tools=["Read", "Grep", "WebSearch", "mcp__tax_tools__detect_wash_sales"],
    ),

    "deduction-finder": AgentDefinition(
        description="Aggressive deduction and credit optimizer",
        prompt="""Find EVERY legal deduction. Search for: above-the-line deductions,
itemized opportunities, credits. Compare standard vs itemized.""",
        tools=["Read", "Grep", "mcp__tax_tools__calculate_tax"],
    ),

    "compliance-auditor": AgentDefinition(
        description="IRS compliance and audit risk assessor",
        prompt="""Review for: mathematical errors, missing income, unusual deductions.
Cross-reference all amounts against source documents.""",
        tools=["Read", "Grep", "Glob"],
    ),
}
```

### Phase 4: CLI Integration

Add async support for Agent SDK operations:

```python
import asyncio
from functools import wraps

def async_command(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@app.command()
@async_command
async def analyze_interactive() -> None:
    """Run interactive analysis with agent capabilities."""
    from tax_agent.agent_sdk import TaxAgentSDK

    agent = TaxAgentSDK(get_config())

    with console.status("[cyan]Analyzing...[/cyan]"):
        async for message in agent.analyze_documents(
            "Analyze my tax situation and find optimization opportunities."
        ):
            # Handle streaming output
            pass
```

### Phase 5: Backward Compatibility

```python
"""Compatibility layer for gradual migration."""

class TaxAgentCompat:
    """Unified interface supporting both legacy and SDK modes."""

    def __init__(self, use_sdk: bool = False):
        self.use_sdk = use_sdk
        if use_sdk:
            self.agent = TaxAgentSDK(get_config())
        else:
            self.agent = LegacyTaxAgent()

    def classify_document(self, text: str) -> dict:
        if self.use_sdk:
            return asyncio.run(self.agent.classify_document_async(text))
        return self.agent.classify_document(text)
```

## 5. New Capabilities Enabled

### 5.1 Automated Document Verification
Agent can read documents, search for discrepancies, verify against IRS rules via web.

### 5.2 Multi-Step Tax Optimization
```
User: "Find all tax-saving opportunities"
Agent:
  1. Reads all collected documents
  2. Calculates current tax situation
  3. Searches for applicable deductions
  4. Verifies eligibility via IRS.gov
  5. Recommends specific actions with dollar amounts
```

### 5.3 Real-Time Tax Research
Use `WebSearch` and `WebFetch` to verify current limits, lookup form instructions, check tax law changes.

## 6. Migration Strategy

### Recommended: Incremental Migration

1. Install SDK, create new agent module alongside existing
2. Add new agentic features (interactive chat, verification)
3. Migrate document classification with verification
4. Migrate analysis functions with tool access
5. Deprecate legacy agent, make SDK default

### Configuration Flag
```bash
tax-agent config set use_agent_sdk true
```

## 7. Challenges and Mitigations

| Challenge | Mitigation |
|-----------|------------|
| Async/await throughout | Use compatibility wrappers, `asyncio.run()` |
| Node.js dependency | Document in installation, provide setup script |
| API cost increase | Add `max_turns` limits, monitor usage |
| Longer analysis times | Add progress indicators, interruptibility |
| SSN handling | Implement hooks for automatic redaction |
| AWS Bedrock support | SDK supports via environment variables |

## 8. File Changes Summary

### New Files
- `src/tax_agent/agent_sdk.py` - Main Agent SDK integration
- `src/tax_agent/tools/tax_calculations.py` - Custom MCP tools
- `src/tax_agent/hooks.py` - Safety and audit hooks
- `src/tax_agent/subagents.py` - Specialized subagent definitions
- `src/tax_agent/agent_compat.py` - Backward compatibility layer

### Modified Files
- `pyproject.toml` - Add `claude-agent-sdk` dependency
- `src/tax_agent/config.py` - Add SDK configuration options
- `src/tax_agent/cli.py` - Add async command support
- `src/tax_agent/chat.py` - Use ClaudeSDKClient for sessions
- `src/tax_agent/collectors/document_classifier.py` - Agentic classification
- `src/tax_agent/analyzers/*.py` - Tool-enabled analysis

### Unchanged (Initially)
- `src/tax_agent/agent.py` - Keep as fallback
- `src/tax_agent/storage/` - No changes needed
- `src/tax_agent/models/` - No changes needed
