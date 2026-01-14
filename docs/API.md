# API and Module Documentation

Complete reference for the Tax Prep Agent's Python modules, classes, and functions.

## Table of Contents

- [Core Modules](#core-modules)
- [Agent Module](#agent-module)
- [Collectors](#collectors)
- [Analyzers](#analyzers)
- [Reviewers](#reviewers)
- [Storage](#storage)
- [Models](#models)
- [Utilities](#utilities)

## Core Modules

### `tax_agent` Package

Main package containing all tax preparation functionality.

**Location:** `src/tax_agent/`

**Public API:**
```python
from tax_agent import get_agent, get_config, get_database
```

## Agent Modules

### `tax_agent.agent_sdk` (Primary)

Agent SDK-powered tax agent with agentic capabilities, tool use, and specialized subagents.

### `tax_agent.agent` (Legacy)

Direct Anthropic API integration for backward compatibility.

### `tax_agent.agent_compat`

Compatibility layer that automatically routes to Agent SDK or legacy API based on availability and configuration.

---

## Agent SDK Module

### `tax_agent.agent_sdk`

Claude Agent SDK integration providing agentic loops, tool use, and specialized subagents.

#### `TaxAgentSDK`

Main Agent SDK class for agentic tax operations.

**Initialization:**

```python
from tax_agent.agent_sdk import TaxAgentSDK, get_sdk_agent

# Create new SDK agent
sdk_agent = TaxAgentSDK(
    model="claude-sonnet-4-5",  # or any supported model
    max_turns=10,               # Maximum agentic turns
    use_hooks=True              # Enable safety/audit hooks
)

# Get global singleton
sdk_agent = get_sdk_agent()

# Check if SDK is available
if sdk_agent.is_available:
    # Use Agent SDK features
    pass
else:
    # Falls back to legacy API
    pass
```

**Constructor:**

```python
def __init__(
    self,
    model: str | None = None,
    max_turns: int | None = None,
    use_hooks: bool = True,
) -> None:
    """
    Initialize the SDK-based tax agent.

    Args:
        model: Claude model to use. Supports:
               - "claude-opus-4-5" → claude-opus-4-5-20251101
               - "claude-sonnet-4-5" → claude-sonnet-4-5-20250929
               - "claude-3-5-sonnet" → claude-3-5-sonnet-20241022
        max_turns: Maximum agentic turns before stopping.
                   Defaults to config.agent_sdk_max_turns (10)
        use_hooks: Whether to enable safety/audit hooks.
                   Recommended for production use.

    Raises:
        None - Falls back gracefully if SDK unavailable
    """
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `is_available` | `bool` | Whether Agent SDK is available |
| `model` | `str` | Full model identifier being used |
| `max_turns` | `int` | Maximum agentic turns configured |
| `use_hooks` | `bool` | Whether hooks are enabled |

---

#### Methods (Async)

The Agent SDK provides async methods that support streaming responses and agentic loops.

##### `classify_document_async()`

Classify a tax document with agentic verification.

```python
async def classify_document_async(
    self,
    text: str,
    file_path: Path | None = None,
) -> dict:
    """
    Classify a tax document using agentic loop with verification.

    The agent can use tools (Read, Grep) to verify classification
    by searching for specific markers in the source file.

    Args:
        text: Extracted text from the document
        file_path: Optional path to source file for tool access

    Returns:
        dict: {
            "document_type": str,          # W2, 1099_INT, 1040, etc.
            "document_category": str,      # "SOURCE" or "RETURN"
            "confidence": float,           # 0.0-1.0
            "issuer_name": str,            # Entity that issued
            "tax_year": int,               # Tax year
            "reasoning": str               # Why classified this way
        }

    Example:
        >>> async for message in sdk_agent.classify_document_async(
        ...     text=w2_text,
        ...     file_path=Path("~/taxes/w2.pdf")
        ... ):
        ...     result = message
        >>> result["document_type"]
        'W2'
        >>> result["confidence"]
        0.95
    """
```

---

##### `analyze_documents_async()`

Comprehensive tax analysis with agentic verification and tool use.

```python
async def analyze_documents_async(
    self,
    documents_summary: str,
    taxpayer_info: str,
    source_dir: Path | None = None,
) -> AsyncIterator[str]:
    """
    Analyze tax documents with agentic capabilities.

    The agent can:
    - Read source documents to verify amounts
    - Search for patterns across documents
    - Look up current IRS limits via web search
    - Cross-reference information
    - Perform multi-step analysis

    Args:
        documents_summary: Summary of all collected documents
        taxpayer_info: Taxpayer profile information
        source_dir: Directory containing source documents for tool access

    Yields:
        str: Analysis text chunks as they're generated (streaming)

    Example:
        >>> async for chunk in sdk_agent.analyze_documents_async(
        ...     documents_summary=docs,
        ...     taxpayer_info=profile,
        ...     source_dir=Path("~/.tax-agent/data")
        ... ):
        ...     print(chunk, end="", flush=True)

        # Outputs streaming analysis with verification
    """
```

---

##### `review_return_async()`

Comprehensive tax return review with cross-validation.

```python
async def review_return_async(
    self,
    return_text: str,
    source_documents: str,
    source_dir: Path | None = None,
) -> AsyncIterator[str]:
    """
    Review a tax return with agentic verification.

    The agent can:
    - Read source documents to verify amounts
    - Cross-reference every line item
    - Detect mathematical errors
    - Find missed deductions and credits
    - Assess compliance and audit risk

    Args:
        return_text: Text extracted from the tax return
        source_documents: Summary of source documents
        source_dir: Directory containing source documents

    Yields:
        str: Review findings as they're generated

    Example:
        >>> async for chunk in sdk_agent.review_return_async(
        ...     return_text=return_pdf_text,
        ...     source_documents=docs_summary,
        ...     source_dir=Path("~/taxes")
        ... ):
        ...     print(chunk, end="", flush=True)
    """
```

---

##### `interactive_query_async()`

Interactive conversational tax queries with full tool access.

```python
async def interactive_query_async(
    self,
    query_text: str,
    context: dict | None = None,
    source_dir: Path | None = None,
) -> AsyncIterator[str]:
    """
    Run an interactive tax query with full agentic capabilities.

    The agent can use all available tools to research and
    verify information before providing answers.

    Args:
        query_text: The user's question or request
        context: Optional context (documents, profile, etc.)
        source_dir: Directory for file access

    Yields:
        str: Response chunks as they're generated

    Example:
        >>> context = {
        ...     "documents": ["W-2", "1099-B"],
        ...     "tax_year": 2024
        ... }
        >>> async for chunk in sdk_agent.interactive_query_async(
        ...     "How will my RSUs affect my taxes?",
        ...     context=context,
        ...     source_dir=Path("~/taxes")
        ... ):
        ...     print(chunk, end="", flush=True)
    """
```

---

##### `invoke_subagent_async()`

Delegate task to a specialized subagent.

```python
async def invoke_subagent_async(
    self,
    subagent_name: str,
    prompt: str,
    source_dir: Path | None = None,
) -> AsyncIterator[str]:
    """
    Invoke a specialized subagent for a specific task.

    Args:
        subagent_name: Name of the subagent (e.g., 'deduction-finder')
        prompt: Task prompt for the subagent
        source_dir: Directory for file access

    Yields:
        str: Response chunks from the subagent

    Available subagents:
        - stock-compensation-analyst
        - deduction-finder
        - compliance-auditor
        - investment-tax-analyst
        - retirement-tax-planner
        - self-employment-specialist

    Example:
        >>> async for chunk in sdk_agent.invoke_subagent_async(
        ...     "deduction-finder",
        ...     "Find all missed deductions for my situation",
        ...     source_dir=Path("~/.tax-agent/data")
        ... ):
        ...     print(chunk, end="", flush=True)
    """
```

---

#### Methods (Synchronous)

Synchronous wrappers for backward compatibility.

```python
# Synchronous versions that block until complete
def classify_document(text: str, file_path: Path | None = None) -> dict
def analyze_documents(docs_summary: str, taxpayer_info: str, source_dir: Path | None = None) -> str
def review_return(return_text: str, source_docs: str, source_dir: Path | None = None) -> str
def interactive_query(query: str, context: dict | None = None, source_dir: Path | None = None) -> str
def invoke_subagent(name: str, prompt: str, source_dir: Path | None = None) -> str
```

---

#### Subagent Management

```python
def get_subagent(self, name: str) -> SubagentDefinition | None:
    """
    Get a specialized subagent by name.

    Returns:
        SubagentDefinition or None if not found
    """

def list_subagents(self) -> list[dict[str, str]]:
    """
    List all available specialized subagents.

    Returns:
        List of dicts with 'name' and 'description'

    Example:
        >>> subagents = sdk_agent.list_subagents()
        >>> for agent in subagents:
        ...     print(f"{agent['name']}: {agent['description']}")
    """
```

---

## Slash Commands Module

### `tax_agent.slash_commands`

Slash command registry and handlers for the interactive interface.

#### `SlashCommand`

Definition of a slash command.

```python
@dataclass
class SlashCommand:
    name: str                          # Command name (without /)
    description: str                   # Help text
    handler: Callable[..., str]        # Command function
    aliases: list[str]                 # Alternative names
    subcommands: dict[str, SlashCommand]  # Nested commands
    requires_init: bool                # Needs initialization
    usage: str                         # Usage example
```

---

#### Functions

##### `register_command()`

Register a new slash command.

```python
def register_command(
    name: str,
    description: str,
    handler: Callable[..., str],
    aliases: list[str] | None = None,
    requires_init: bool = True,
    usage: str = "",
) -> SlashCommand:
    """
    Register a slash command.

    Example:
        >>> def cmd_example(args: list[str], context: dict) -> str:
        ...     return f"Example command with args: {args}"
        >>>
        >>> register_command(
        ...     "example",
        ...     "Example command",
        ...     cmd_example,
        ...     aliases=["ex"],
        ...     usage="<arg1> <arg2>"
        ... )
    """
```

---

##### `get_command()`

Retrieve a command by name or alias.

```python
def get_command(name: str) -> SlashCommand | None:
    """
    Get a slash command by name (with or without leading /).

    Example:
        >>> cmd = get_command("help")
        >>> cmd = get_command("/help")  # Same result
    """
```

---

##### `get_completions()`

Get tab completions for partial input.

```python
def get_completions(partial: str) -> list[str]:
    """
    Get command completions for partial input.

    Args:
        partial: Partial command text (with or without /)

    Returns:
        List of matching command names with /

    Example:
        >>> get_completions("/an")
        ['/analyze']
        >>> get_completions("/d")
        ['/documents', '/docs', '/d']
    """
```

---

##### `parse_slash_command()`

Parse user input into command and arguments.

```python
def parse_slash_command(input_text: str) -> tuple[str | None, list[str]]:
    """
    Parse a slash command from input text.

    Returns:
        Tuple of (command_name, args) or (None, []) if not a slash command

    Example:
        >>> parse_slash_command("/collect ~/taxes/w2.pdf --year 2024")
        ('collect', ['~/taxes/w2.pdf', '--year', '2024'])
        >>> parse_slash_command("How do RSUs work?")
        (None, [])
    """
```

---

##### `execute_slash_command()`

Execute a slash command and return result.

```python
async def execute_slash_command(
    command_name: str,
    args: list[str],
    context: dict[str, Any] | None = None,
) -> str:
    """
    Execute a slash command and return the result.

    Example:
        >>> result = await execute_slash_command(
        ...     "status",
        ...     [],
        ...     {}
        ... )
    """
```

---

## Subagents Module

### `tax_agent.subagents`

Specialized subagents for tax analysis domains.

#### `SubagentDefinition`

Configuration for a specialized subagent.

```python
@dataclass
class SubagentDefinition:
    name: str                    # Subagent identifier
    description: str             # What it specializes in
    system_prompt: str           # Domain-specific prompt
    allowed_tools: list[str]     # Tools it can use
    max_turns: int               # Maximum agentic turns
    model: str | None            # Model override (optional)
```

---

#### Available Subagents

##### Stock Compensation Analyst

```python
STOCK_COMPENSATION_ANALYST = SubagentDefinition(
    name="stock-compensation-analyst",
    description="Expert in RSU, ISO, NSO, and ESPP taxation",
    system_prompt="...",  # Specialized prompt
    allowed_tools=["Read", "Grep", "Glob", "detect_wash_sales", "calculate_tax"],
    max_turns=8,
)
```

**Expertise:**
- RSU vesting and sale taxation
- ISO AMT calculations
- NSO ordinary income treatment
- ESPP qualifying vs disqualifying dispositions
- Wash sale detection
- Cost basis verification

---

##### Deduction Finder

```python
DEDUCTION_FINDER = SubagentDefinition(
    name="deduction-finder",
    description="Aggressive deduction and credit optimizer",
    system_prompt="...",
    allowed_tools=["Read", "Grep", "Glob", "WebSearch", "calculate_tax", "check_limits"],
    max_turns=10,
)
```

**Expertise:**
- Above-the-line deductions
- Itemized vs standard comparison
- Business deductions (Schedule C)
- Tax credits (education, child, energy, etc.)
- Bunching strategies

---

##### Compliance Auditor

```python
COMPLIANCE_AUDITOR = SubagentDefinition(
    name="compliance-auditor",
    description="IRS compliance and audit risk assessor",
    system_prompt="...",
    allowed_tools=["Read", "Grep", "Glob"],
    max_turns=8,
)
```

**Expertise:**
- Income verification against source docs
- Mathematical error detection
- Deduction reasonableness checks
- Audit red flag identification
- Compliance issue severity rating

---

##### Investment Tax Analyst

```python
INVESTMENT_TAX_ANALYST = SubagentDefinition(
    name="investment-tax-analyst",
    description="Capital gains, dividends, and investment income specialist",
    system_prompt="...",
    allowed_tools=["Read", "Grep", "Glob", "detect_wash_sales", "calculate_tax"],
    max_turns=10,
)
```

**Expertise:**
- Short vs long-term capital gains
- Qualified dividend classification
- Wash sale detection
- Net Investment Income Tax (NIIT)
- Cost basis issues
- Tax-loss harvesting strategies

---

##### Retirement Tax Planner

```python
RETIREMENT_TAX_PLANNER = SubagentDefinition(
    name="retirement-tax-planner",
    description="401(k), IRA, and retirement account optimization specialist",
    system_prompt="...",
    allowed_tools=["Read", "Grep", "WebSearch", "check_limits", "calculate_tax"],
    max_turns=8,
)
```

**Expertise:**
- Contribution limits and optimization
- Traditional vs Roth analysis
- Backdoor Roth strategies
- Mega backdoor Roth
- RMD planning
- Early distribution strategies

---

##### Self-Employment Specialist

```python
SELF_EMPLOYMENT_SPECIALIST = SubagentDefinition(
    name="self-employment-specialist",
    description="Schedule C, SE tax, and business deduction expert",
    system_prompt="...",
    allowed_tools=["Read", "Grep", "Glob", "calculate_tax"],
    max_turns=8,
)
```

**Expertise:**
- Schedule C analysis
- Self-employment tax calculation
- Home office deduction (simplified vs actual)
- Vehicle expenses
- Section 179 deductions
- QBI deduction
- Estimated tax requirements

---

#### Functions

```python
def get_subagent(name: str) -> SubagentDefinition | None:
    """Get a subagent by name."""

def list_subagents() -> list[dict[str, str]]:
    """List all subagents with names and descriptions."""

def get_subagent_for_task(task_description: str) -> SubagentDefinition | None:
    """
    Suggest the best subagent for a task based on keywords.

    Example:
        >>> agent = get_subagent_for_task("analyze my RSU taxes")
        >>> agent.name
        'stock-compensation-analyst'
    """
```

---

## Safety Hooks Module

### `tax_agent.hooks`

Safety and audit hooks for Agent SDK operations.

#### Hook Functions

All hooks follow the same signature:

```python
async def hook_name(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Hook function.

    Args:
        input_data: Tool invocation or result data
        tool_use_id: Unique identifier for this tool use
        context: Additional context

    Returns:
        dict: Hook-specific output (can be empty)
              May include permission decisions or data transformations
    """
```

---

#### PreToolUse Hooks

Run before a tool is executed.

##### `audit_log_hook()`

Log all tool invocations for audit trail.

```python
async def audit_log_hook(input_data, tool_use_id, context) -> dict:
    """
    Log tool usage.

    Logs:
        - Tool name
        - Tool inputs
        - Timestamp
        - Context information
    """
```

---

##### `sensitive_data_guard()`

Restrict file access to tax-relevant directories.

```python
async def sensitive_data_guard(input_data, tool_use_id, context) -> dict:
    """
    Block access to files outside allowed directories.

    Allowed:
        - /tmp/
        - ~/.tax-agent/data/
        - ~/.tax-agent/config/

    Returns:
        - Empty dict if allowed
        - Permission denial if blocked
    """
```

---

##### `web_access_guard()`

Control web tool usage based on configuration.

```python
async def web_access_guard(input_data, tool_use_id, context) -> dict:
    """
    Block web tools if disabled in config.

    Checks config.agent_sdk_allow_web setting.
    """
```

---

#### PostToolUse Hooks

Run after a tool completes.

##### `ssn_redaction_hook()`

Redact SSN patterns from tool outputs.

```python
async def ssn_redaction_hook(input_data, tool_use_id, context) -> dict:
    """
    Redact Social Security Numbers from outputs.

    Patterns:
        - XXX-XX-XXXX → [SSN REDACTED]
        - XXXXXXXXX → [SSN REDACTED]

    Returns:
        Updated result with redactions
    """
```

---

##### `ein_redaction_hook()`

Optionally redact EIN patterns from outputs.

```python
async def ein_redaction_hook(input_data, tool_use_id, context) -> dict:
    """
    Redact Employer Identification Numbers.

    Only active if config.redact_ein is True.

    Pattern:
        - XX-XXXXXXX → [EIN REDACTED]
    """
```

---

##### `rate_limit_hook()`

Track tool usage for rate limiting.

```python
async def rate_limit_hook(input_data, tool_use_id, context) -> dict:
    """
    Track tool invocations for rate limiting.

    Especially monitors expensive web tools.
    """
```

---

#### Hook Configuration

```python
def get_tax_hooks() -> dict:
    """
    Get all hooks configured for the tax agent.

    Returns:
        dict: {
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

    Example:
        >>> from tax_agent.hooks import get_tax_hooks
        >>> hooks = get_tax_hooks()
        >>> # Pass to ClaudeCodeOptions
    """

def get_minimal_hooks() -> dict:
    """
    Get minimal hooks for performance-sensitive operations.

    Returns only essential security hooks.
    """
```

---

#### `TaxAgent`

Main class for all AI interactions.

**Initialization:**

```python
from tax_agent.agent import TaxAgent, get_agent

# Create new agent instance
agent = TaxAgent()

# With specific model
agent = TaxAgent(model="claude-opus-4-20250514")

# Get global singleton
agent = get_agent()
```

**Constructor:**

```python
def __init__(self, model: str | None = None) -> None:
    """
    Initialize the tax agent.

    Args:
        model: Claude model to use. Defaults to config setting.
               Options: "claude-3-5-sonnet",
                       "claude-opus-4-20250514"

    Raises:
        ValueError: If API key not configured
    """
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `provider` | `str` | AI provider name ("anthropic" or "aws_bedrock") |
| `model` | `str` | Model identifier being used |
| `client` | `Anthropic | AnthropicBedrock` | Underlying API client |

---

#### Methods

##### `classify_document()`

Classify a tax document and identify its type.

```python
def classify_document(self, text: str) -> dict:
    """
    Classify a tax document using AI.

    Args:
        text: Extracted text from the document (after optional redaction)

    Returns:
        dict: {
            "document_type": str,  # One of DocumentType enum values
            "confidence": float,   # 0.0 to 1.0
            "issuer_name": str,    # Entity that issued the document
            "tax_year": int,       # Tax year (e.g., 2024)
            "reasoning": str       # Explanation of classification
        }

    Example:
        >>> text = "W-2 Wage and Tax Statement\\nEmployer: Google LLC..."
        >>> result = agent.classify_document(text)
        >>> result["document_type"]
        'W2'
        >>> result["confidence"]
        0.95
    """
```

---

##### `extract_w2_data()`

Extract structured data from a W-2 form.

```python
def extract_w2_data(self, text: str) -> dict:
    """
    Extract all fields from a W-2 tax form.

    Args:
        text: Full text of W-2 document

    Returns:
        dict: {
            "employer_name": str,
            "employer_ein": str,              # Format: XX-XXXXXXX
            "employer_address": str,
            "employee_ssn_last4": str,        # Only last 4 digits
            "employee_name": str,
            "box_1": float,                   # Wages, tips, other compensation
            "box_2": float,                   # Federal income tax withheld
            "box_3": float,                   # Social security wages
            "box_4": float,                   # Social security tax withheld
            "box_5": float,                   # Medicare wages and tips
            "box_6": float,                   # Medicare tax withheld
            "box_7": float | None,            # Social security tips
            "box_10": float | None,           # Dependent care benefits
            "box_12_codes": list[dict],       # [{"code": "D", "amount": 1000}, ...]
            "box_13_statutory": bool,
            "box_13_retirement": bool,
            "box_13_sick_pay": bool,
            "box_15_state": str,              # State abbreviation
            "box_16": float,                  # State wages
            "box_17": float,                  # State income tax
            "box_18": float | None,           # Local wages
            "box_19": float | None,           # Local income tax
            "box_20": str | None              # Locality name
        }

    Example:
        >>> data = agent.extract_w2_data(w2_text)
        >>> data["box_1"]
        150000.00
        >>> data["employer_name"]
        'Google LLC'
    """
```

---

##### `extract_1099_int_data()`

Extract structured data from a 1099-INT form.

```python
def extract_1099_int_data(self, text: str) -> dict:
    """
    Extract interest income data from 1099-INT.

    Args:
        text: Full text of 1099-INT document

    Returns:
        dict: {
            "payer_name": str,
            "payer_ein": str,
            "recipient_ssn_last4": str,
            "recipient_name": str,
            "box_1": float,                   # Interest income
            "box_2": float | None,            # Early withdrawal penalty
            "box_3": float | None,            # Interest on US Savings Bonds
            "box_4": float | None,            # Federal income tax withheld
            "box_5": float | None,            # Investment expenses
            "box_6": float | None,            # Foreign tax paid
            "box_8": float | None,            # Tax-exempt interest
            "box_9": float | None,            # Private activity bond interest
            "state": str | None,
            "state_tax_withheld": float | None
        }
    """
```

---

##### `extract_1099_div_data()`

Extract structured data from a 1099-DIV form.

```python
def extract_1099_div_data(self, text: str) -> dict:
    """
    Extract dividend income data from 1099-DIV.

    Args:
        text: Full text of 1099-DIV document

    Returns:
        dict: {
            "payer_name": str,
            "payer_ein": str,
            "recipient_ssn_last4": str,
            "recipient_name": str,
            "box_1a": float,                  # Total ordinary dividends
            "box_1b": float | None,           # Qualified dividends
            "box_2a": float | None,           # Total capital gain distributions
            "box_2b": float | None,           # Unrecap. Sec. 1250 gain
            "box_2c": float | None,           # Section 1202 gain
            "box_2d": float | None,           # Collectibles (28%) gain
            "box_2e": float | None,           # Section 897 ordinary dividends
            "box_2f": float | None,           # Section 897 capital gain
            "box_3": float | None,            # Nondividend distributions
            "box_4": float | None,            # Federal income tax withheld
            "box_5": float | None,            # Section 199A dividends
            "box_6": float | None,            # Investment expenses
            "box_7": float | None,            # Foreign tax paid
            "box_11": bool,                   # FATCA filing requirement
            "box_12": float | None,           # Exempt-interest dividends
            "box_13": float | None,           # Private activity bond interest
            "state": str | None,
            "state_tax_withheld": float | None
        }
    """
```

---

##### `extract_1099_b_data()`

Extract structured data from a 1099-B form (brokerage transactions).

```python
def extract_1099_b_data(self, text: str) -> dict:
    """
    Extract brokerage transaction data from 1099-B.

    Args:
        text: Full text of 1099-B document

    Returns:
        dict: {
            "payer_name": str,
            "payer_ein": str,
            "recipient_ssn_last4": str,
            "recipient_name": str,
            "transactions": [
                {
                    "description": str,           # Security description
                    "date_acquired": str,         # YYYY-MM-DD or "Various"
                    "date_sold": str,             # YYYY-MM-DD
                    "proceeds": float,            # Sale proceeds
                    "cost_basis": float | None,   # Cost basis
                    "wash_sale_loss": float | None,
                    "gain_loss": float | None,
                    "term": "short" | "long" | None,
                    "covered": bool               # Basis reported to IRS?
                },
                ...
            ],
            "summary": {
                "total_proceeds": float,
                "total_cost_basis": float | None,
                "short_term_gain_loss": float,
                "long_term_gain_loss": float
            },
            "federal_tax_withheld": float | None
        }

    Note:
        max_tokens is increased to 8000 for 1099-B due to potentially
        large number of transactions.
    """
```

---

##### `analyze_tax_implications()`

Comprehensive tax analysis based on collected documents.

```python
def analyze_tax_implications(
    self,
    documents_summary: str,
    taxpayer_info: str
) -> str:
    """
    Analyze tax implications and provide optimization insights.

    Uses an aggressive tax minimization system prompt to find all
    possible deductions, credits, and strategies.

    Args:
        documents_summary: Summary of all collected tax documents
        taxpayer_info: Taxpayer profile (state, filing status, etc.)

    Returns:
        str: Comprehensive analysis including:
            - Income analysis
            - Withholding gaps
            - Deduction opportunities
            - Credit hunting
            - Investment tax optimization
            - Retirement strategies
            - State tax considerations
            - Action items with dollar estimates
            - Total potential savings

    Example:
        >>> docs = "W-2: $150,000 wages\\n1099-DIV: $3,500 dividends..."
        >>> info = "State: CA, Filing: Single"
        >>> analysis = agent.analyze_tax_implications(docs, info)
        >>> print(analysis)
        # Returns detailed multi-section analysis
    """
```

---

##### `review_tax_return()`

Review a completed tax return for errors and optimization.

```python
def review_tax_return(
    self,
    return_text: str,
    source_documents: str
) -> str:
    """
    Expert review of tax return against source documents.

    Uses IRS auditor perspective to find errors, missed opportunities,
    and compliance issues.

    Args:
        return_text: Text extracted from completed tax return PDF
        source_documents: Summary of source documents (W-2, 1099s, etc.)

    Returns:
        str: Review findings including:
            - Income verification (IRS matching)
            - Math error detection
            - Deduction optimization
            - Credit opportunities
            - Investment tax issues
            - Filing status optimization
            - Compliance red flags

            Each finding includes:
            - Severity (ERROR/WARNING/OPPORTUNITY)
            - Category
            - Expected vs actual values
            - Tax impact in dollars
            - Specific action to take

    Example:
        >>> return_text = extract_text_from_pdf("return.pdf")
        >>> docs = database.get_documents_summary(2024)
        >>> review = agent.review_tax_return(return_text, docs)
        >>> # Parse review for findings
    """
```

## Collectors

### `tax_agent.collectors.document_classifier`

Orchestrates document collection and classification.

#### `DocumentCollector`

Main document collection class.

**Initialization:**

```python
from tax_agent.collectors.document_classifier import DocumentCollector

collector = DocumentCollector()
```

---

##### `process_file()`

Process a single tax document file.

```python
def process_file(
    self,
    file_path: str | Path,
    tax_year: int | None = None
) -> TaxDocument:
    """
    Process a tax document file (PDF or image).

    Process flow:
    1. Extract text (OCR for images, PyMuPDF for PDFs)
    2. Compute file hash for deduplication
    3. Check for existing document
    4. Optionally redact SSN/EIN
    5. Classify using AI
    6. Extract structured data
    7. Verify extraction
    8. Save to database

    Args:
        file_path: Path to PDF or image file
        tax_year: Tax year (defaults to config)

    Returns:
        TaxDocument: Processed and stored document

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If document already exists (duplicate hash)

    Example:
        >>> collector = DocumentCollector()
        >>> doc = collector.process_file("~/taxes/w2.pdf", 2024)
        >>> doc.document_type
        <DocumentType.W2>
        >>> doc.confidence_score
        0.95
    """
```

---

##### `process_directory()`

Batch process all files in a directory.

```python
def process_directory(
    self,
    directory: str | Path,
    tax_year: int | None = None
) -> list[tuple[Path, TaxDocument | Exception]]:
    """
    Process all supported files in a directory.

    Args:
        directory: Path to directory containing tax documents
        tax_year: Tax year (defaults to config)

    Returns:
        list[tuple[Path, TaxDocument | Exception]]:
            List of (file_path, result) tuples.
            Result is either TaxDocument (success) or Exception (error)

    Example:
        >>> results = collector.process_directory("~/taxes/2024/")
        >>> successes = [r for f, r in results if not isinstance(r, Exception)]
        >>> failures = [r for f, r in results if isinstance(r, Exception)]
        >>> print(f"Processed {len(successes)}/{len(results)} successfully")
    """
```

---

##### `process_google_drive_folder()`

Process documents from a Google Drive folder.

```python
def process_google_drive_folder(
    self,
    folder_id: str,
    tax_year: int | None = None,
    recursive: bool = False
) -> list[tuple[str, TaxDocument | Exception]]:
    """
    Collect and process documents from Google Drive.

    Requires prior authentication via:
        tax-agent drive auth --setup <client_secrets.json>

    Args:
        folder_id: Google Drive folder ID
        tax_year: Tax year (defaults to config)
        recursive: Include subfolders (default: False)

    Returns:
        list[tuple[str, TaxDocument | Exception]]:
            List of (filename, result) tuples

    Example:
        >>> results = collector.process_google_drive_folder(
        ...     "1a2b3c4d5e6f",
        ...     tax_year=2024,
        ...     recursive=True
        ... )
    """
```

---

### `tax_agent.collectors.ocr`

Text extraction using OCR.

#### Functions

##### `extract_text_with_ocr()`

Extract text from images or PDFs using Tesseract OCR.

```python
def extract_text_with_ocr(file_path: str | Path) -> str:
    """
    Extract text using OCR (Optical Character Recognition).

    For PDFs: Converts each page to image, then OCRs
    For images: Direct OCR

    Args:
        file_path: Path to PDF or image file

    Returns:
        str: Extracted text

    Raises:
        FileNotFoundError: If file doesn't exist
        RuntimeError: If Tesseract not installed

    Supported formats:
        - PDF (via pdf2image)
        - PNG, JPG, JPEG, TIFF

    Example:
        >>> text = extract_text_with_ocr("w2_scan.jpg")
        >>> "Form W-2" in text
        True

    Performance:
        - Images: ~2-5 seconds
        - PDF pages: ~5-10 seconds per page
    """
```

---

### `tax_agent.collectors.pdf_parser`

Direct PDF text extraction (faster than OCR).

#### Functions

##### `extract_text_from_pdf()`

Extract text directly from PDF.

```python
def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extract text from PDF using PyMuPDF.

    Faster than OCR but only works if PDF has embedded text.
    Falls back to OCR if text extraction yields < 100 characters.

    Args:
        file_path: Path to PDF file

    Returns:
        str: Extracted text

    Example:
        >>> text = extract_text_from_pdf("w2.pdf")
        >>> len(text) > 100  # Should have substantial text
        True

    Performance:
        - Typically < 1 second per PDF
        - Much faster than OCR for text-based PDFs
    """
```

---

### `tax_agent.collectors.google_drive`

Google Drive integration.

#### `GoogleDriveCollector`

Collects documents from Google Drive.

**Initialization:**

```python
from tax_agent.collectors.google_drive import GoogleDriveCollector

drive = GoogleDriveCollector()
```

---

##### `is_authenticated()`

Check if valid Google Drive credentials exist.

```python
def is_authenticated(self) -> bool:
    """
    Check if we have valid Google credentials.

    Returns:
        bool: True if authenticated and credentials valid

    Example:
        >>> drive = GoogleDriveCollector()
        >>> if not drive.is_authenticated():
        ...     print("Please run: tax-agent drive auth")
    """
```

---

##### `authenticate_with_client_file()`

Initial authentication with OAuth client secrets.

```python
def authenticate_with_client_file(
    self,
    client_secrets_file: str | Path
) -> bool:
    """
    Authenticate using client secrets JSON file.

    Opens browser for OAuth2 flow. User grants permissions,
    tokens stored in system keyring.

    Args:
        client_secrets_file: Path to client_secrets.json from
                            Google Cloud Console

    Returns:
        bool: True if authentication successful

    Raises:
        FileNotFoundError: If client secrets file not found

    Example:
        >>> drive = GoogleDriveCollector()
        >>> drive.authenticate_with_client_file("~/client_secrets.json")
        # Browser opens for authorization
        True
    """
```

---

##### `list_folders()`

List folders in Google Drive.

```python
def list_folders(self, parent_id: str = "root") -> list[DriveFolder]:
    """
    List folders in specified parent.

    Args:
        parent_id: Parent folder ID or "root" (default)

    Returns:
        list[DriveFolder]: List of folder objects with id and name

    Example:
        >>> folders = drive.list_folders()
        >>> tax_folder = next(f for f in folders if f.name == "2024 Taxes")
        >>> tax_folder.id
        '1a2b3c4d5e6f'
    """
```

---

##### `list_files()`

List files in a folder.

```python
def list_files(self, folder_id: str) -> list[DriveFile]:
    """
    List supported files in folder.

    Only returns files with supported MIME types:
    - application/pdf
    - image/png, image/jpeg, image/tiff
    - application/vnd.google-apps.document (Google Docs)

    Args:
        folder_id: Google Drive folder ID

    Returns:
        list[DriveFile]: List of file objects

    Example:
        >>> files = drive.list_files("1a2b3c4d5e6f")
        >>> pdf_files = [f for f in files if f.mime_type == "application/pdf"]
    """
```

---

##### `download_file()`

Download a file from Google Drive.

```python
def download_file(
    self,
    file_id: str,
    destination: Path
) -> Path:
    """
    Download file from Google Drive.

    For Google Docs, automatically exports as PDF.

    Args:
        file_id: Google Drive file ID
        destination: Local path to save file

    Returns:
        Path: Path to downloaded file

    Example:
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
        ...     path = drive.download_file("abc123", Path(tmp.name))
        ...     # Process file
    """
```

## Analyzers

### `tax_agent.analyzers.implications`

Tax situation analysis.

#### `TaxAnalyzer`

Analyzes tax implications from collected documents.

**Initialization:**

```python
from tax_agent.analyzers.implications import TaxAnalyzer

analyzer = TaxAnalyzer(tax_year=2024)
```

---

##### `generate_analysis()`

Generate comprehensive tax analysis.

```python
def generate_analysis(self) -> dict:
    """
    Analyze collected documents and calculate tax estimates.

    Retrieves all documents for tax year, aggregates income,
    calculates estimated tax, and projects refund/owed.

    Returns:
        dict: {
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
            "withholding_summary": {
                "federal": float,
                "state": float,
                "social_security": float,
                "medicare": float
            },
            "refund_or_owed": float,  # Positive = refund, negative = owed
            "estimated_refund": float,
            "estimated_owed": float
        }

    Example:
        >>> analyzer = TaxAnalyzer(2024)
        >>> analysis = analyzer.generate_analysis()
        >>> analysis["total_income"]
        171750.00
        >>> analysis["refund_or_owed"]
        2500.00  # Expecting $2,500 refund
    """
```

---

##### `generate_ai_analysis()`

Get AI-powered tax insights.

```python
def generate_ai_analysis(self) -> str:
    """
    Generate comprehensive AI analysis of tax situation.

    Uses aggressive tax optimization prompts to find savings.

    Returns:
        str: Multi-section analysis including:
            - Income breakdown and implications
            - Withholding analysis
            - Deduction opportunities
            - Credit suggestions
            - Tax-saving strategies
            - Next steps

    Example:
        >>> analysis = analyzer.generate_ai_analysis()
        >>> print(analysis)
        # Displays detailed tax analysis text
    """
```

---

### `tax_agent.analyzers.deductions`

Tax optimization and deduction discovery.

#### `TaxOptimizer`

Finds deductions, credits, and tax-saving strategies.

**Initialization:**

```python
from tax_agent.analyzers.deductions import TaxOptimizer

optimizer = TaxOptimizer(tax_year=2024)
```

---

##### `get_interview_questions()`

Generate personalized interview questions.

```python
def get_interview_questions(self) -> list[dict]:
    """
    Generate AI-powered interview questions based on documents.

    Questions are tailored to the user's specific tax situation
    based on collected documents.

    Returns:
        list[dict]: [
            {
                "id": str,              # Unique identifier
                "question": str,        # Question text
                "type": str,            # Question type
                "relevance": str,       # Why this question
                "options": list[str]    # For select/multi_select
            },
            ...
        ]

    Question types:
        - "yes_no": Boolean question
        - "number": Numeric input (dollar amounts)
        - "select": Single choice
        - "multi_select": Multiple choices
        - "text": Free-form

    Example:
        >>> questions = optimizer.get_interview_questions()
        >>> questions[0]
        {
            "id": "home_ownership",
            "question": "Do you own your home?",
            "type": "yes_no",
            "relevance": "Mortgage interest may be deductible"
        }
    """
```

---

##### `find_deductions()`

Identify deductions and credits based on interview answers.

```python
def find_deductions(
    self,
    interview_answers: dict[str, Any]
) -> dict:
    """
    Find applicable deductions and credits.

    Args:
        interview_answers: Dict mapping question IDs to answers

    Returns:
        dict: {
            "standard_vs_itemized": {
                "recommendation": "standard" | "itemized",
                "reasoning": str,
                "standard_amount": float,
                "itemized_amount": float,
                "savings": float
            },
            "recommended_deductions": [
                {
                    "name": str,
                    "estimated_value": float,
                    "action_needed": str
                },
                ...
            ],
            "recommended_credits": [
                {
                    "name": str,
                    "estimated_value": float
                },
                ...
            ],
            "estimated_total_savings": float,
            "action_items": list[str],
            "warnings": list[str]
        }

    Example:
        >>> answers = {
        ...     "home_ownership": True,
        ...     "mortgage_interest": 12000.00,
        ...     "state_local_tax": 8000.00
        ... }
        >>> deductions = optimizer.find_deductions(answers)
        >>> deductions["standard_vs_itemized"]["recommendation"]
        'itemized'
        >>> deductions["estimated_total_savings"]
        3500.00
    """
```

---

##### `analyze_stock_compensation()`

Deep analysis of stock compensation tax implications.

```python
def analyze_stock_compensation(
    self,
    comp_type: str,
    details: dict
) -> dict:
    """
    Analyze stock compensation tax treatment.

    Args:
        comp_type: Type of compensation
            - "RSUs (Restricted Stock Units)"
            - "ISOs (Incentive Stock Options)"
            - "NSOs (Non-Qualified Stock Options)"
            - "ESPP (Employee Stock Purchase Plan)"
        details: Stock details dict:
            {
                "shares_vested": str | int,
                "vesting_price": str | float,
                "shares_sold": str | int,
                "sale_price": str | float,
                "company": str
            }

    Returns:
        dict: {
            "tax_treatment": str,        # How it's taxed
            "immediate_actions": str,    # What to do now
            "optimization_tips": str,    # How to optimize
            "warnings": str              # What to watch out for
        }

    Example:
        >>> details = {
        ...     "shares_vested": "500",
        ...     "vesting_price": "150",
        ...     "shares_sold": "300",
        ...     "sale_price": "175",
        ...     "company": "Google"
        ... }
        >>> analysis = optimizer.analyze_stock_compensation(
        ...     "RSUs (Restricted Stock Units)",
        ...     details
        ... )
        >>> print(analysis["tax_treatment"])
        # RSU vesting taxed as ordinary income...
    """
```

## Reviewers

### `tax_agent.reviewers.error_checker`

Tax return review and error detection.

#### `ReturnReviewer`

Reviews completed tax returns for errors and opportunities.

**Initialization:**

```python
from tax_agent.reviewers.error_checker import ReturnReviewer

reviewer = ReturnReviewer(tax_year=2024)
```

---

##### `review_return()`

Comprehensive tax return review.

```python
def review_return(self, return_file: Path) -> ReturnReview:
    """
    Review a completed tax return PDF.

    Extracts text from return, loads source documents,
    sends to AI for comprehensive review.

    Args:
        return_file: Path to completed tax return PDF

    Returns:
        ReturnReview: Review result object containing:
            - return_summary: Dict of return info
            - findings: list[ReviewFinding]
            - overall_assessment: str
            - errors_count: int
            - warnings_count: int
            - suggestions_count: int

    Example:
        >>> reviewer = ReturnReviewer(2024)
        >>> review = reviewer.review_return(Path("~/2024_return.pdf"))
        >>> review.errors_count
        2
        >>> for finding in review.findings:
        ...     if finding.severity == ReviewSeverity.ERROR:
        ...         print(f"{finding.title}: ${finding.potential_impact}")
        Missing 1099-DIV Income: $840.00
        W-2 Box 1 Mismatch: $120.00
    """
```

## Storage

### `tax_agent.storage.database`

Encrypted database management.

#### `TaxDatabase`

Main database class for encrypted storage.

**Initialization:**

```python
from tax_agent.storage.database import TaxDatabase, get_database

# Create new instance
db = TaxDatabase()

# With custom path/password
db = TaxDatabase(
    db_path=Path("/custom/path/tax_data.db"),
    password="custom_password"
)

# Get global singleton
db = get_database()
```

---

##### `save_document()`

Save a tax document to the database.

```python
def save_document(self, document: TaxDocument) -> None:
    """
    Store tax document in encrypted database.

    Args:
        document: TaxDocument instance to save

    Raises:
        sqlite3.IntegrityError: If document ID already exists

    Example:
        >>> from tax_agent.models.documents import TaxDocument, DocumentType
        >>> doc = TaxDocument(
        ...     id="abc123",
        ...     tax_year=2024,
        ...     document_type=DocumentType.W2,
        ...     issuer_name="Google LLC",
        ...     # ... other fields
        ... )
        >>> db.save_document(doc)
    """
```

---

##### `get_document()`

Retrieve a document by ID.

```python
def get_document(self, document_id: str) -> TaxDocument | None:
    """
    Get document by ID.

    Args:
        document_id: Document UUID

    Returns:
        TaxDocument | None: Document if found, None otherwise

    Example:
        >>> doc = db.get_document("abc12345-...")
        >>> doc.document_type
        <DocumentType.W2>
    """
```

---

##### `get_documents()`

List documents with optional filtering.

```python
def get_documents(
    self,
    tax_year: int | None = None,
    document_type: str | None = None
) -> list[TaxDocument]:
    """
    Get list of documents, optionally filtered.

    Args:
        tax_year: Filter by tax year (optional)
        document_type: Filter by type (optional)

    Returns:
        list[TaxDocument]: List of matching documents

    Example:
        >>> # All documents for 2024
        >>> docs_2024 = db.get_documents(tax_year=2024)

        >>> # All W-2s
        >>> w2s = db.get_documents(document_type="W2")

        >>> # W-2s from 2024
        >>> w2s_2024 = db.get_documents(
        ...     tax_year=2024,
        ...     document_type="W2"
        ... )
    """
```

---

### `tax_agent.storage.encryption`

Encryption and data protection utilities.

#### Functions

##### `hash_file()`

Compute SHA-256 hash of a file.

```python
def hash_file(file_path: str | Path) -> str:
    """
    Compute SHA-256 hash of file for deduplication.

    Args:
        file_path: Path to file

    Returns:
        str: Hex-encoded SHA-256 hash

    Example:
        >>> hash1 = hash_file("w2.pdf")
        >>> hash2 = hash_file("w2_copy.pdf")
        >>> hash1 == hash2  # Same file
        True
    """
```

---

##### `redact_sensitive_data()`

Remove SSN and EIN from text.

```python
def redact_sensitive_data(text: str) -> str:
    """
    Redact Social Security Numbers and EINs from text.

    Patterns redacted:
    - SSN: XXX-XX-XXXX or XXXXXXXXX → [SSN REDACTED]
    - EIN: XX-XXXXXXX → [EIN REDACTED]

    Last 4 digits preserved for verification.

    Args:
        text: Original text

    Returns:
        str: Text with SSN/EIN redacted

    Example:
        >>> text = "SSN: 123-45-6789\\nEIN: 12-3456789"
        >>> redacted = redact_sensitive_data(text)
        >>> "123-45" in redacted
        False
        >>> "6789" in redacted  # Last 4 preserved
        True
        >>> "[SSN REDACTED]" in redacted
        True
    """
```

## Models

### `tax_agent.models.documents`

Document data models.

#### `DocumentType`

Enumeration of supported tax document types.

```python
from tax_agent.models.documents import DocumentType

class DocumentType(str, Enum):
    W2 = "W2"
    W2_G = "W2_G"
    FORM_1099_INT = "1099_INT"
    FORM_1099_DIV = "1099_DIV"
    FORM_1099_B = "1099_B"
    FORM_1099_NEC = "1099_NEC"
    FORM_1099_MISC = "1099_MISC"
    FORM_1099_R = "1099_R"
    FORM_1099_G = "1099_G"
    FORM_1099_K = "1099_K"
    FORM_1098 = "1098"
    FORM_1098_T = "1098_T"
    FORM_1098_E = "1098_E"
    FORM_5498 = "5498"
    K1 = "K1"
    UNKNOWN = "UNKNOWN"

# Usage
doc_type = DocumentType.W2
assert doc_type.value == "W2"
```

---

#### `TaxDocument`

Main document model.

```python
from tax_agent.models.documents import TaxDocument, DocumentType
from datetime import datetime

doc = TaxDocument(
    id="abc12345-6789-...",
    tax_year=2024,
    document_type=DocumentType.W2,
    issuer_name="Google LLC",
    issuer_ein="12-3456789",
    recipient_ssn_last4="1234",
    raw_text="Full extracted text...",
    extracted_data={
        "box_1": 150000.00,
        "box_2": 35000.00,
        # ... more fields
    },
    file_path="/path/to/w2.pdf",
    file_hash="sha256hash...",
    confidence_score=0.95,
    needs_review=False,
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# Access fields
print(doc.issuer_name)  # "Google LLC"
print(doc.extracted_data["box_1"])  # 150000.00

# Serialize to dict
doc_dict = doc.model_dump()

# Serialize to JSON
doc_json = doc.model_dump_json()
```

---

### `tax_agent.models.returns`

Tax return review models.

#### `ReviewSeverity`

Finding severity levels.

```python
from tax_agent.models.returns import ReviewSeverity

class ReviewSeverity(str, Enum):
    ERROR = "error"          # Must fix
    WARNING = "warning"      # Should verify
    SUGGESTION = "suggestion"  # Optional improvement
    INFO = "info"           # Informational
```

---

#### `ReviewFinding`

Individual review finding.

```python
from tax_agent.models.returns import ReviewFinding, ReviewSeverity

finding = ReviewFinding(
    severity=ReviewSeverity.ERROR,
    category="income",
    title="Missing 1099-DIV Income",
    description="Return is missing dividend income from Vanguard.",
    expected_value=3500.00,
    actual_value=2250.00,
    potential_impact=840.00,  # Dollar tax impact
    recommendation="Add missing $1,250 to Line 3b"
)

# Access
if finding.severity == ReviewSeverity.ERROR:
    print(f"ERROR: {finding.title}")
    print(f"Tax impact: ${finding.potential_impact}")
```

---

## Configuration

### `tax_agent.config`

Configuration and credential management.

#### `Config`

Main configuration class.

**Initialization:**

```python
from tax_agent.config import Config, get_config

# Create new instance
config = Config()

# With custom directory
config = Config(config_dir=Path("/custom/.tax-agent"))

# Get global singleton
config = get_config()
```

---

##### Properties

```python
# Read-only properties
config.is_initialized  # bool
config.tax_year        # int
config.state           # str | None
config.ai_provider     # str ("anthropic" | "aws_bedrock")
config.aws_region      # str
config.db_path         # Path
config.data_dir        # Path

# Set properties
config.tax_year = 2024
config.state = "CA"
config.ai_provider = "anthropic"
config.aws_region = "us-west-2"
```

---

##### Methods

###### `initialize()`

Initialize the application with encryption.

```python
def initialize(self, password: str) -> None:
    """
    Initialize application with database encryption.

    Creates data directory and stores encryption password
    in system keyring.

    Args:
        password: Encryption password for database

    Example:
        >>> config = Config()
        >>> config.initialize("my-secure-password-123")
        >>> config.is_initialized
        True
    """
```

---

###### `get()` / `set()`

Get/set configuration values.

```python
def get(self, key: str, default: Any = None) -> Any:
    """Get configuration value."""

def set(self, key: str, value: Any) -> None:
    """Set configuration value and save to file."""

# Example
config.set("tax_year", 2024)
config.set("state", "CA")
year = config.get("tax_year")  # 2024
```

---

###### Credential Methods

```python
# API key
config.set_api_key("sk-ant-...")
api_key = config.get_api_key()  # From keyring

# AWS credentials
config.set_aws_credentials("AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/...")
access, secret = config.get_aws_credentials()

# Google Drive
config.set_google_credentials({...})
creds = config.get_google_credentials()

# Database password
password = config.get_db_password()
```

## Verification

### `tax_agent.verification`

AI output verification to prevent hallucinations.

#### `OutputVerifier`

Verifies AI-extracted data against source documents.

**Initialization:**

```python
from tax_agent.verification import OutputVerifier

verifier = OutputVerifier()
```

---

##### `verify_extracted_data()`

Verify extracted data against source document.

```python
def verify_extracted_data(
    self,
    document_type: str,
    extracted_data: dict[str, Any],
    raw_text: str
) -> dict[str, Any]:
    """
    Verify AI extraction results.

    Checks:
    1. Values appear in source text
    2. Document-specific sanity checks (W-2: Box1 >= Box3, etc.)
    3. Cross-field validation (calculations correct)

    Args:
        document_type: Type of document ("W2", "1099_INT", etc.)
        extracted_data: AI-extracted data
        raw_text: Original document text

    Returns:
        dict: {
            "verified": bool,               # Overall verification pass
            "confidence": float,            # 0.0 to 1.0
            "issues": [
                {
                    "field": str,
                    "value": Any,
                    "issue": str,
                    "severity": "error" | "warning"
                },
                ...
            ],
            "verified_fields": list[str]    # Fields that passed
        }

    Example:
        >>> data = {"box_1": 150000.00, "box_2": 35000.00}
        >>> raw = "Box 1: $150,000.00\\nBox 2: $35,000.00..."
        >>> result = verifier.verify_extracted_data("W2", data, raw)
        >>> result["verified"]
        True
        >>> result["confidence"]
        0.95
        >>> len(result["issues"])
        0
    """
```

---

## Utilities

### Helper Functions

#### `verify_extraction()`

Convenience function for verification.

```python
from tax_agent.verification import verify_extraction

result = verify_extraction(
    document_type="W2",
    extracted_data={"box_1": 150000.00},
    raw_text="Box 1: $150,000.00..."
)
```

## Usage Examples

### Complete Document Processing

```python
from tax_agent.collectors.document_classifier import DocumentCollector
from tax_agent.storage.database import get_database

# Process a document
collector = DocumentCollector()
doc = collector.process_file("~/taxes/w2.pdf", tax_year=2024)

# Check results
if doc.needs_review:
    print(f"Low confidence: {doc.confidence_score:.0%}")
    print(f"Please review document manually")
else:
    print(f"Processed {doc.document_type.value} from {doc.issuer_name}")

# Retrieve later
db = get_database()
docs = db.get_documents(tax_year=2024)
for doc in docs:
    print(f"{doc.document_type.value}: {doc.issuer_name}")
```

---

### Tax Analysis

```python
from tax_agent.analyzers.implications import TaxAnalyzer

analyzer = TaxAnalyzer(tax_year=2024)

# Generate analysis
analysis = analyzer.generate_analysis()

# Check results
print(f"Total Income: ${analysis['total_income']:,.2f}")
print(f"Estimated Tax: ${analysis['tax_estimate']['total_tax']:,.2f}")

if analysis['refund_or_owed'] > 0:
    print(f"Refund: ${analysis['estimated_refund']:,.2f}")
else:
    print(f"Owed: ${analysis['estimated_owed']:,.2f}")

# Get AI insights
insights = analyzer.generate_ai_analysis()
print(insights)
```

---

### Tax Optimization

```python
from tax_agent.analyzers.deductions import TaxOptimizer

optimizer = TaxOptimizer(tax_year=2024)

# Get questions
questions = optimizer.get_interview_questions()

# Collect answers (simulated here)
answers = {}
for q in questions:
    if q["type"] == "yes_no":
        answers[q["id"]] = True
    elif q["type"] == "number":
        answers[q["id"]] = 10000.00

# Find deductions
results = optimizer.find_deductions(answers)

print(f"Recommendation: {results['standard_vs_itemized']['recommendation']}")
print(f"Total Savings: ${results['estimated_total_savings']:,.0f}")

for deduction in results['recommended_deductions']:
    print(f"- {deduction['name']}: ${deduction['estimated_value']:,.0f}")
```

---

### Return Review

```python
from pathlib import Path
from tax_agent.reviewers.error_checker import ReturnReviewer
from tax_agent.models.returns import ReviewSeverity

reviewer = ReturnReviewer(tax_year=2024)
review = reviewer.review_return(Path("~/taxes/2024_return.pdf"))

print(f"Overall: {review.overall_assessment}")
print(f"Errors: {review.errors_count}")
print(f"Warnings: {review.warnings_count}")
print(f"Suggestions: {review.suggestions_count}")

# Show errors only
for finding in review.findings:
    if finding.severity == ReviewSeverity.ERROR:
        print(f"\nERROR: {finding.title}")
        print(f"  {finding.description}")
        print(f"  Impact: ${finding.potential_impact:,.2f}")
        print(f"  Fix: {finding.recommendation}")
```

---

## Error Handling

### Common Exceptions

```python
# File not found
try:
    collector.process_file("nonexistent.pdf")
except FileNotFoundError as e:
    print(f"File not found: {e}")

# API key not configured
try:
    agent = TaxAgent()
except ValueError as e:
    print(f"Configuration error: {e}")
    print("Run: tax-agent init")

# Duplicate document
try:
    collector.process_file("w2.pdf")
except ValueError as e:
    if "already exists" in str(e):
        print("Document already processed")

# Database password not found
try:
    db = TaxDatabase()
except ValueError as e:
    print(f"Database error: {e}")
    print("Run: tax-agent init")
```

---

## Type Hints

All public APIs use type hints for better IDE support:

```python
from typing import Any

def process_file(
    self,
    file_path: str | Path,
    tax_year: int | None = None
) -> TaxDocument:
    ...

def get_documents(
    self,
    tax_year: int | None = None
) -> list[TaxDocument]:
    ...

def analyze_tax_implications(
    self,
    documents_summary: str,
    taxpayer_info: str
) -> str:
    ...
```

---

## Pydantic Models

All data models use Pydantic for validation:

```python
from tax_agent.models.documents import TaxDocument

# Validation on creation
doc = TaxDocument(
    id="abc",
    tax_year=2024,
    confidence_score=1.5,  # ERROR: must be 0-1
)
# Raises: pydantic.ValidationError

# Correct usage
doc = TaxDocument(
    id="abc",
    tax_year=2024,
    confidence_score=0.95,  # ✓
    # ... other required fields
)

# Serialization
doc_dict = doc.model_dump()
doc_json = doc.model_dump_json()

# Deserialization
doc2 = TaxDocument(**doc_dict)
```

---

## Contributing

When extending the API:

1. **Add type hints** to all public functions
2. **Write docstrings** in Google style
3. **Include examples** in docstrings
4. **Update this documentation**
5. **Add tests** for new functionality

Example:

```python
def my_new_function(
    param1: str,
    param2: int | None = None
) -> dict[str, Any]:
    """
    Brief description of what this does.

    Longer explanation if needed. Explain the purpose,
    when to use it, and any important caveats.

    Args:
        param1: Description of param1
        param2: Description of param2 (optional, defaults to None)

    Returns:
        dict[str, Any]: Description of return value

    Raises:
        ValueError: When param1 is invalid
        RuntimeError: When something goes wrong

    Example:
        >>> result = my_new_function("test", 42)
        >>> result["status"]
        'success'
    """
    # Implementation
```

---

For more information, see:
- [Usage Guide](USAGE.md) - CLI command reference
- [Architecture](ARCHITECTURE.md) - System design
- [Google Drive Setup](GOOGLE_DRIVE_SETUP.md) - Drive integration
