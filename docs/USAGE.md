# Usage Guide

Comprehensive guide to using the Tax Prep Agent CLI tool.

## Table of Contents

- [Getting Started](#getting-started)
- [Core Commands](#core-commands)
- [Document Management](#document-management)
- [Configuration](#configuration)
- [Tax Research](#tax-research)
- [Google Drive Integration](#google-drive-integration)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Getting Started

### First-Time Setup

After installing the tax-prep-agent, follow these steps to get started:

```bash
# 1. Initialize the agent (sets up encryption and API keys)
tax-agent init

# 2. Verify your setup
tax-agent status

# 3. Configure basic settings
tax-agent config set state CA
tax-agent config set filing_status single
tax-agent config set tax_year 2024
```

### Quick Workflow Example

```bash
# Collect documents from a folder
tax-agent collect ~/Documents/2024_Taxes/ --dir

# Analyze your tax situation
tax-agent analyze

# Find optimization opportunities
tax-agent optimize

# Review a completed return
tax-agent review ~/Documents/2024_tax_return.pdf
```

## Core Commands

### `tax-agent init`

Initialize the tax agent with encryption and API credentials.

**Usage:**
```bash
tax-agent init
```

**Interactive Setup:**

1. **Encryption Password**: Choose a strong password to encrypt your tax data
   - Minimum 12 characters recommended
   - Cannot be recovered if lost
   - Stored securely in system keyring

2. **AI Provider Selection**: Choose between:
   - **Anthropic API** (recommended for individuals)
   - **AWS Bedrock** (for enterprise deployments)

3. **API Credentials**:
   - For Anthropic: Enter API key from console.anthropic.com
   - For AWS Bedrock: Enter AWS credentials or use default credential chain

4. **Basic Configuration**:
   - State code (e.g., CA, NY, TX)
   - Tax year (defaults to current/previous year)

**Example Output:**
```
Tax Prep Agent Setup

This will set up encrypted storage for your tax documents.
You'll need:
  1. A password for encrypting your data
  2. API credentials (Anthropic API or AWS Bedrock)

Enter a password for encrypting your tax data: ************
Confirm password: ************

Choose your AI provider:
  1. Anthropic API (direct)
  2. AWS Bedrock
Enter choice [1]: 1

Enter your Anthropic API key: sk-ant-***************

State Configuration
Your state affects tax calculations and optimization suggestions.
Enter your state code (e.g., CA, NY, TX) or 'skip' to set later: CA

Setup Complete!
Data directory: /Users/you/.tax-agent/data
AI Provider: anthropic
Model: claude-sonnet-4-5-20250514
Tax Year: 2024
State: CA

Next steps:
  1. Collect documents: tax-agent collect <file>
  2. Run optimization: tax-agent optimize
```

---

### `tax-agent status`

Display current configuration and initialization status.

**Usage:**
```bash
tax-agent status
```

**Output Example:**
```
┌─────────────────── Tax Agent Status ────────────────────┐
│ Setting          │ Value                                │
│──────────────────│──────────────────────────────────────│
│ Initialized      │ Yes                                  │
│ Tax Year         │ 2024                                 │
│ State            │ CA                                   │
│ AI Provider      │ anthropic                            │
│ Model            │ claude-sonnet-4-5-20250514           │
│ API Key          │ Configured                           │
│ Data Directory   │ /Users/you/.tax-agent/data           │
└──────────────────────────────────────────────────────────┘
```

---

### `tax-agent collect <file>`

Collect and process a tax document using AI-powered OCR and classification.

**Usage:**
```bash
# Process a single file
tax-agent collect <file_path> [options]

# Process entire directory
tax-agent collect <directory_path> --dir
```

**Options:**
- `--year, -y <year>`: Specify tax year (overrides config)
- `--dir, -d`: Process all files in directory

**Supported File Formats:**
- PDF documents (.pdf)
- Image files (.png, .jpg, .jpeg, .tiff)

**Examples:**
```bash
# Single W-2 document
tax-agent collect ~/taxes/w2_google.pdf

# Process with specific year
tax-agent collect ~/taxes/1099-int_bank.pdf --year 2023

# Process entire directory
tax-agent collect ~/Documents/2024_Taxes/ --dir

# Process images
tax-agent collect ~/taxes/w2_photo.jpg
```

**Processing Steps:**

1. **Text Extraction**: Uses OCR (Tesseract) for images or PyMuPDF for PDFs
2. **Deduplication**: Checks file hash to prevent duplicate processing
3. **Redaction**: Optionally redacts SSN/EIN before AI processing
4. **Classification**: AI identifies document type with confidence score
5. **Data Extraction**: Extracts structured data based on document type
6. **Verification**: Cross-validates extracted data against source
7. **Storage**: Saves to encrypted database

**Output Example:**
```
Processing w2_google.pdf for tax year 2024...

Document processed successfully!

┌────────────────── Document Details ──────────────────┐
│ Field          │ Value                               │
│────────────────│─────────────────────────────────────│
│ ID             │ abc12345...                         │
│ Type           │ W2                                  │
│ Issuer         │ Google LLC                          │
│ EIN            │ 12-3456789                          │
│ Tax Year       │ 2024                                │
│ Confidence     │ 95%                                 │
│ Status         │ Ready                               │
│ Wages (Box 1)  │ $150,000.00                         │
│ Fed Tax        │ $35,000.00                          │
└──────────────────────────────────────────────────────┘
```

**Low Confidence Handling:**

Documents with confidence < 80% are flagged for review:
```
Status: Needs Review (75% confidence)

Please verify:
  - Check Box 1 wages: $150,000.00
  - Verify employer name: Google LLC
  - Review extracted data with: tax-agent documents show abc12345
```

---

### `tax-agent analyze`

Analyze collected documents to assess tax implications and estimate tax liability.

**Usage:**
```bash
tax-agent analyze [options]
```

**Options:**
- `--year, -y <year>`: Tax year to analyze (defaults to config)
- `--summary, -s`: Brief summary only (no detailed breakdown)
- `--ai / --no-ai`: Include/exclude AI analysis (default: enabled)

**Examples:**
```bash
# Full analysis with AI insights
tax-agent analyze

# Brief summary without AI commentary
tax-agent analyze --summary --no-ai

# Analyze specific year
tax-agent analyze --year 2023

# Quick check without waiting for AI
tax-agent analyze --no-ai
```

**Output Sections:**

#### 1. Income Summary
```
┌─────────────────── Income Summary ────────────────────┐
│ Source                      │ Amount                  │
│─────────────────────────────│─────────────────────────│
│ Wages                       │ $150,000.00             │
│ Interest                    │ $1,250.00               │
│ Ordinary Dividends          │ $3,500.00               │
│ Qualified Dividends         │ $2,800.00               │
│ Short-term Capital Gains    │ $5,000.00               │
│ Long-term Capital Gains     │ $12,000.00              │
│ Other Income                │ $0.00                   │
│                             │                         │
│ Total Income                │ $171,750.00             │
└─────────────────────────────────────────────────────────┘
```

#### 2. Tax Estimate
```
┌───────────────────── Tax Estimate ─────────────────────┐
│ Item                           │ Amount                │
│────────────────────────────────│───────────────────────│
│ Standard Deduction             │ $14,600.00            │
│ Taxable Ordinary Income        │ $157,150.00           │
│ Ordinary Income Tax            │ $32,450.00            │
│ Capital Gains Tax              │ $2,550.00             │
│ Estimated Total Tax            │ $35,000.00            │
└───────────────────────────────────────────────────────────┘
```

#### 3. Withholding Summary
```
┌────────────────── Withholding Summary ─────────────────┐
│ Type                        │ Amount                   │
│─────────────────────────────│──────────────────────────│
│ Federal Income Tax          │ $35,000.00               │
│ State Income Tax            │ $8,200.00                │
│ Social Security             │ $9,300.00                │
│ Medicare                    │ $2,175.00                │
└─────────────────────────────────────────────────────────┘
```

#### 4. Refund/Owed Status
```
Estimated Refund: $2,500.00
```
or
```
Estimated Amount Owed: $1,200.00
```

#### 5. AI Tax Analysis

When `--ai` is enabled (default), includes comprehensive analysis:

```
┌────────────────── AI Tax Analysis ──────────────────────┐
│ INCOME ANALYSIS                                         │
│ Your primary income is W-2 wages ($150,000) from Google │
│ LLC, placing you in the 24% marginal federal tax        │
│ bracket for 2024.                                       │
│                                                         │
│ Investment income totals $16,750, primarily from        │
│ long-term capital gains ($12,000) which benefit from    │
│ preferential 15% tax rate.                              │
│                                                         │
│ WITHHOLDING ANALYSIS                                    │
│ Federal withholding ($35,000) appears adequate based on │
│ estimated tax liability of $35,000. You're projected    │
│ for a small refund of $2,500.                           │
│                                                         │
│ OPTIMIZATION OPPORTUNITIES                              │
│ 1. Consider maximizing 401(k) contributions to reduce   │
│    taxable income by up to $23,000 (2024 limit)         │
│                                                         │
│ 2. HSA contributions if eligible - $4,150 deduction     │
│                                                         │
│ 3. Tax-loss harvesting on investment positions before   │
│    year-end to offset capital gains                     │
│                                                         │
│ 4. Standard deduction ($14,600) likely optimal unless   │
│    you have significant deductible expenses             │
│                                                         │
│ NEXT STEPS                                              │
│ Run 'tax-agent optimize' for personalized deduction    │
│ discovery and tax-saving strategies.                    │
└─────────────────────────────────────────────────────────┘
```

---

### `tax-agent optimize`

Interactive AI-powered interview to discover deductions, credits, and tax-saving opportunities.

**Usage:**
```bash
tax-agent optimize [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)
- `--interview / --no-interview, -i`: Run interactive interview (default: enabled)

**Examples:**
```bash
# Full interactive optimization
tax-agent optimize

# Skip interview, use collected data only
tax-agent optimize --no-interview

# Optimize for previous year
tax-agent optimize --year 2023
```

**Interview Process:**

The optimizer generates personalized questions based on your tax situation and collected documents.

#### Sample Interview Questions

**1. Home Ownership**
```
1. Do you own your home?
   Answer [y/n]: y

Follow-up: Did you pay mortgage interest this year?
   Answer [y/n]: y
```

**2. Retirement Contributions**
```
2. Did you contribute to retirement accounts?
   Answer [y/n]: y

How much did you contribute to traditional 401(k)?
   Amount ($) [0]: 19500
```

**3. Health Insurance**
```
3. What type of health insurance do you have?
   Options:
     1. Employer-provided
     2. HSA-eligible HDHP
     3. ACA Marketplace
     4. Medicare
     5. None
   Enter number [1]: 2
```

**4. Stock Compensation** (Critical for tech workers)
```
4. Did you receive stock compensation?
   Options (enter numbers separated by commas, or 'none'):
     1. RSUs (Restricted Stock Units)
     2. ISOs (Incentive Stock Options)
     3. NSOs (Non-Qualified Stock Options)
     4. ESPP (Employee Stock Purchase Plan)
     5. None
   Enter numbers: 1

Stock Compensation Detected
Let me analyze your equity compensation situation...

Analyzing RSUs (Restricted Stock Units)...
   How many shares vested this year? 500
   Average price at vesting ($)? 150
   How many shares did you sell? 300
   Average sale price ($)? 175
   Company name? Google
```

#### Stock Compensation Analysis Example

```
┌──────────── RSUs Analysis ────────────────┐
│ Tax Treatment:                            │
│ • Vesting treated as ordinary income      │
│ • 500 shares × $150 = $75,000 income      │
│ • Already reported on your W-2            │
│ • Tax withheld at vest: ~$16,500 (22%)    │
│                                           │
│ • Sale of 300 shares creates capital gain │
│ • Proceeds: 300 × $175 = $52,500          │
│ • Basis: 300 × $150 = $45,000             │
│ • Short-term gain: $7,500                 │
│ • Tax on gain: ~$1,800 (24% bracket)      │
│                                           │
│ Immediate Actions:                        │
│ ✓ Verify W-2 Box 1 includes $75,000 RSU  │
│   income                                  │
│ ✓ Ensure 1099-B reports 300 share sale   │
│ ✓ Check that cost basis is $150/share    │
│                                           │
│ Optimization Tips:                        │
│ • Hold remaining 200 shares >1 year for   │
│   long-term capital gains (15% vs 24%)    │
│ • Consider selling losing positions to    │
│   offset $7,500 short-term gain           │
│ • Increase W-4 withholding if planning    │
│   more RSU vests (22% often insufficient) │
│                                           │
│ Warnings:                                 │
│ ⚠ If you sold and repurchased within 30  │
│   days, watch for wash sale rules         │
│ ⚠ Marginal rate (24%) > withholding (22%)│
│   - may owe additional $1,500 on vesting  │
└───────────────────────────────────────────┘
```

**Output: Recommendations**

After the interview, receive comprehensive recommendations:

```
┌────── Standard vs. Itemized ──────┐
│ Recommendation: ITEMIZE deduction │
│                                   │
│ Itemized total: $18,500           │
│ Standard deduction: $14,600       │
│ Tax savings: $936 (24% bracket)   │
└───────────────────────────────────┘

┌──────────── Recommended Deductions ────────────┐
│ Deduction                │ Est. Value │ Action  │
│──────────────────────────│────────────│─────────│
│ Mortgage Interest        │ $12,000    │ Get 109 │
│ State/Local Taxes (SALT) │ $10,000    │ Capped  │
│ Charitable Contributions │ $3,500     │ Get rec │
│ Student Loan Interest    │ $2,500     │ Above-t │
│ HSA Contribution         │ $4,150     │ Contrib │
└────────────────────────────────────────────────┘

┌──────────── Recommended Credits ───────────────┐
│ Credit                      │ Est. Value      │
│─────────────────────────────│─────────────────│
│ Lifetime Learning Credit    │ $2,000          │
│ Residential Energy Credit   │ $1,200          │
└─────────────────────────────────────────────────┘

Estimated Total Tax Savings: $7,150

Action Items:
  - Obtain Form 1098 from mortgage lender
  - Gather charitable donation receipts for $3,500
  - Verify student loan interest paid with Form 1098-E
  - Make HSA contribution before tax deadline ($4,150 available)
  - Check eligibility for education credit (income limits)

Warnings:
  - SALT deduction capped at $10,000 for 2024
  - Charitable deductions require receipts >$250
  - HSA only eligible with HDHP enrollment
```

---

### `tax-agent review <return-file>`

Review a completed tax return PDF for errors and missed opportunities.

**Usage:**
```bash
tax-agent review <return_file_path> [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)

**Examples:**
```bash
# Review your completed return
tax-agent review ~/Documents/2024_Form1040.pdf

# Review with specific year
tax-agent review ~/taxes/return.pdf --year 2024
```

**Review Process:**

The reviewer performs comprehensive checks:

1. **Income Verification**: Matches income against source documents (W-2, 1099s)
2. **Math Errors**: Validates all calculations and totals
3. **Deduction Optimization**: Compares standard vs itemized
4. **Credit Discovery**: Identifies missed credits
5. **Compliance Checks**: Flags potential IRS concerns

**Output Example:**

```
┌─────────────── Tax Return Review ───────────────┐
│ Tax Year: 2024                                  │
│ Documents Checked: 8                            │
└─────────────────────────────────────────────────┘

⚠ Found 5 findings requiring attention

┌──────────────────── Findings ────────────────────────┐
│ Severity │ Category   │ Issue                 │ Impact│
│──────────│────────────│───────────────────────│───────│
│ ERROR    │ income     │ Missing 1099-DIV      │ $840  │
│ ERROR    │ income     │ W-2 Box 1 mismatch    │ $120  │
│ WARNING  │ deduction  │ SALT over limit       │ -     │
│ SUGGEST  │ credit     │ Missed education      │ $2,000│
│ SUGGEST  │ deduction  │ Student loan interest │ $500  │
└──────────────────────────────────────────────────────┘

Detailed Findings:

1. ERROR: Missing Dividend Income
   Your return is missing dividend income from Vanguard.
   Expected: $3,500 (from 1099-DIV)
   Actual: $2,250 on Schedule B
   Tax Impact: $840 additional tax owed
   Recommendation: Add missing $1,250 to Line 3b

2. ERROR: W-2 Wages Mismatch
   Form 1040 Line 1 doesn't match W-2 total.
   Expected: $150,000 (Google LLC W-2 Box 1)
   Actual: $149,500 on Line 1
   Tax Impact: $120 refund difference
   Recommendation: Correct Line 1 to $150,000

3. WARNING: SALT Deduction Exceeds Cap
   State and local tax deduction appears to exceed $10,000 cap.
   Recommendation: Verify Schedule A Line 5e is capped at $10,000

4. SUGGESTION: Missed Education Credit
   You may qualify for Lifetime Learning Credit based on 1098-T.
   Qualified expenses: $10,000
   Estimated credit: $2,000 (20% of first $10,000)
   Tax Impact: $2,000 reduction in tax
   Recommendation: Complete Form 8863 for education credits

5. SUGGESTION: Student Loan Interest Deduction
   You paid $2,500 in student loan interest (1098-E) but didn't claim.
   Estimated tax savings: $500 (at 24% bracket)
   Recommendation: Add $2,500 to Schedule 1 Line 21
```

---

### `tax-agent chat`

Start an interactive chat session for tax questions and strategy exploration.

**Usage:**
```bash
tax-agent chat [options]
```

**Options:**
- `--year, -y <year>`: Tax year context (defaults to config)

**Examples:**
```bash
# Start chat session
tax-agent chat

# Chat about previous year
tax-agent chat --year 2023
```

**Special Commands:**
- `quit` / `exit` / `bye` / `q`: End session
- `suggest`: Get topic suggestions
- `reset`: Clear conversation history

**Example Session:**
```
┌───────────── Interactive Tax Advisor ─────────────┐
│ Tax Year: 2024                                    │
│ State: CA                                         │
│                                                   │
│ Ask me anything about your taxes! I'll help you   │
│ find deductions, understand tax implications, and │
│ explore strategies to save money.                 │
│                                                   │
│ Type 'quit' or 'exit' to end the session.        │
│ Type 'suggest' for topic suggestions.            │
└───────────────────────────────────────────────────┘

Try asking:
  • How can I reduce my tax bill for 2024?
  • What are the benefits of a backdoor Roth IRA?
  • Should I itemize or take the standard deduction?

You: How do RSUs affect my taxes?

Advisor: RSUs (Restricted Stock Units) have important tax
implications:

1. AT VESTING:
   - Treated as ordinary income (like wages)
   - Fair market value on vesting date added to your W-2
   - Taxed at your marginal rate (could be 24%, 32%, or higher)
   - Employer withholds ~22% federal (often insufficient!)
   - Subject to Social Security and Medicare taxes

2. AT SALE:
   - Creates a capital gain/loss event
   - Your basis = FMV at vesting
   - Holding period determines short vs long-term treatment:
     * <1 year: Short-term (ordinary income rates)
     * >1 year: Long-term (preferential rates: 0%, 15%, 20%)

3. COMMON ISSUES:
   - Underwithholding: 22% flat rate often less than marginal rate
   - Surprise tax bills if you sell immediately
   - Wash sale complications if you trade frequently

4. OPTIMIZATION STRATEGIES:
   - Increase W-4 withholding to account for gap
   - Hold shares >1 year for long-term gains (if company stable)
   - Consider selling losing positions to offset gains
   - Make estimated payments if withholding insufficient

Would you like me to analyze your specific RSU situation
based on your collected documents?

You: yes

Advisor: Based on your W-2 from Google LLC, I can see:
[Continues with personalized analysis...]

You: quit

Session ended. Good luck with your taxes!
```

## Document Management

### `tax-agent documents list`

List all collected tax documents.

**Usage:**
```bash
tax-agent documents list [options]
```

**Options:**
- `--year, -y <year>`: Filter by tax year

**Examples:**
```bash
# List all documents for current year
tax-agent documents list

# List documents for 2023
tax-agent documents list --year 2023
```

**Output:**
```
┌─────────────── Tax Documents - 2024 ───────────────┐
│ ID        │ Type      │ Issuer           │ Status │
│───────────│───────────│──────────────────│────────│
│ abc12345  │ W2        │ Google LLC       │ Ready  │
│ def67890  │ 1099_INT  │ Chase Bank       │ Ready  │
│ ghi11121  │ 1099_DIV  │ Vanguard         │ Ready  │
│ jkl31415  │ 1099_B    │ E*TRADE          │ Review │
│ mno16171  │ 1098      │ Wells Fargo      │ Ready  │
└─────────────────────────────────────────────────────┘

8 document(s) total
```

---

### `tax-agent documents show <id>`

Show detailed information about a specific document.

**Usage:**
```bash
tax-agent documents show <document_id>
```

**ID Matching:**
- Full ID: `abc12345-6789-...`
- Partial ID: `abc` (must be unique)

**Examples:**
```bash
# Full ID
tax-agent documents show abc12345-6789-1234-5678

# Partial ID (unique prefix)
tax-agent documents show abc

# If multiple matches
tax-agent documents show a
# Output: Multiple documents match 'a':
#   abc12345... - W2 from Google LLC
#   aef67890... - 1099_INT from Chase Bank
```

**Output:**
```
┌────────────────────────────────────────┐
│ W2 from Google LLC                     │
└────────────────────────────────────────┘

ID                    abc12345-6789-1234-5678
Tax Year              2024
Document Type         W2
Issuer                Google LLC
EIN                   12-3456789
Confidence            95%
Needs Review          No
Created               2024-01-15 10:30
Source File           /Users/you/taxes/w2_google.pdf

Extracted Data:
{
  "employer_name": "Google LLC",
  "employer_ein": "12-3456789",
  "employee_ssn_last4": "1234",
  "employee_name": "John Doe",
  "box_1": 150000.00,
  "box_2": 35000.00,
  "box_3": 147000.00,
  "box_4": 9114.00,
  "box_5": 150000.00,
  "box_6": 2175.00,
  "box_12_codes": [
    {"code": "D", "amount": 19500.00},
    {"code": "DD", "amount": 12000.00}
  ],
  "box_13_retirement": true,
  "box_15_state": "CA",
  "box_16": 150000.00,
  "box_17": 8200.00
}
```

## Configuration

### `tax-agent config set <key> <value>`

Set a configuration value.

**Usage:**
```bash
tax-agent config set <key> <value>
```

**Valid Keys:**

| Key | Type | Example | Description |
|-----|------|---------|-------------|
| `state` | string | `CA` | Two-letter state code |
| `tax_year` | integer | `2024` | Tax year being prepared |
| `filing_status` | string | `single` | Filing status |
| `model` | string | `claude-opus-4-20250514` | Claude model to use |
| `auto_redact_ssn` | boolean | `true` | Auto-redact SSN before AI |

**Filing Status Values:**
- `single`
- `married_joint`
- `married_separate`
- `head_of_household`
- `qualifying_widow`

**Examples:**
```bash
# Set state
tax-agent config set state NY

# Set tax year
tax-agent config set tax_year 2023

# Set filing status
tax-agent config set filing_status married_joint

# Change AI model to Opus (more accurate, more expensive)
tax-agent config set model claude-opus-4-20250514

# Disable SSN redaction (for more accurate extraction)
tax-agent config set auto_redact_ssn false
```

---

### `tax-agent config get [key]`

Get configuration value(s).

**Usage:**
```bash
# Get specific value
tax-agent config get <key>

# Get all configuration
tax-agent config get
```

**Examples:**
```bash
# Get state
tax-agent config get state
# Output: state = CA

# Get all settings
tax-agent config get
```

**Output (all settings):**
```
┌───────────────── Configuration ─────────────────┐
│ Key              │ Value                        │
│──────────────────│──────────────────────────────│
│ tax_year         │ 2024                         │
│ state            │ CA                           │
│ filing_status    │ single                       │
│ ai_provider      │ anthropic                    │
│ model            │ claude-sonnet-4-5-20250514   │
│ aws_region       │ us-east-1                    │
│ ocr_engine       │ pytesseract                  │
│ auto_redact_ssn  │ True                         │
│ initialized      │ True                         │
└──────────────────────────────────────────────────┘
```

---

### `tax-agent config api-key`

Update your Anthropic API key.

**Usage:**
```bash
tax-agent config api-key
```

**Example:**
```bash
tax-agent config api-key
# Enter your Anthropic API key: sk-ant-***************
# API key updated successfully.
```

## Tax Research

The research commands use live web search to verify current tax laws and IRS guidance.

### `tax-agent research topic <topic>`

Research a specific tax topic with current IRS guidance.

**Usage:**
```bash
tax-agent research topic "<topic>" [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)

**Examples:**
```bash
# Research backdoor Roth IRAs
tax-agent research topic "backdoor Roth IRA"

# Research specific deduction
tax-agent research topic "home office deduction rules"

# Research for specific year
tax-agent research topic "standard deduction" --year 2023
```

**Output Example:**
```
Researching: backdoor Roth IRA (Tax Year 2024)...

┌────────────── Research: backdoor Roth IRA ───────────┐
│ WHAT IS A BACKDOOR ROTH IRA?                         │
│                                                      │
│ A backdoor Roth IRA is a strategy that allows high  │
│ earners who exceed Roth IRA income limits to        │
│ contribute to a Roth IRA indirectly.                │
│                                                      │
│ PROCESS:                                            │
│ 1. Make non-deductible contribution to traditional  │
│    IRA ($7,000 limit for 2024, $8,000 if 50+)      │
│ 2. Convert traditional IRA to Roth IRA              │
│ 3. Pay taxes on any earnings between contribution   │
│    and conversion                                   │
│                                                      │
│ INCOME LIMITS (2024):                               │
│ - Traditional IRA contribution: No limit            │
│ - Direct Roth IRA contribution:                     │
│   * Single: Phases out $146,000-$161,000           │
│   * Married: Phases out $230,000-$240,000          │
│                                                      │
│ KEY CONSIDERATIONS:                                 │
│ - Pro-rata rule: If you have existing pre-tax IRA  │
│   balances, conversion is partially taxable         │
│ - Step transaction doctrine: IRS may scrutinize    │
│   immediate conversions, though generally accepted  │
│ - Form 8606 required for non-deductible            │
│   contributions                                     │
│                                                      │
│ SOURCES:                                            │
│ - IRS Publication 590-A (Contributions)             │
│ - IRS Publication 590-B (Distributions)             │
│ - 2024 IRS Revenue Procedure for income limits     │
└──────────────────────────────────────────────────────┘
```

---

### `tax-agent research limits`

Verify current IRS contribution limits and thresholds.

**Usage:**
```bash
tax-agent research limits [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)

**Examples:**
```bash
# Get current year limits
tax-agent research limits

# Get 2023 limits
tax-agent research limits --year 2023
```

**Output:**
```
┌────── IRS Limits for Tax Year 2024 ──────┐
│ Verified Limits                          │
└──────────────────────────────────────────┘

┌────────── Contribution & Deduction Limits ─────────┐
│ Item                          │ Amount   │ Source  │
│───────────────────────────────│──────────│─────────│
│ Standard Deduction (Single)   │ $14,600  │ Rev Pro │
│ Standard Deduction (Married)  │ $29,200  │ Rev Pro │
│ 401(k) Contribution Limit     │ $23,000  │ IRS Not │
│ 401(k) Catch-up (50+)         │ $7,500   │ IRS Not │
│ IRA Contribution Limit        │ $7,000   │ IRS Pub │
│ IRA Catch-up (50+)            │ $1,000   │ IRS Pub │
│ HSA Limit (Self)              │ $4,150   │ Rev Pro │
│ HSA Limit (Family)            │ $8,300   │ Rev Pro │
│ HSA Catch-up (55+)            │ $1,000   │ Rev Pro │
│ SALT Deduction Cap            │ $10,000  │ Tax Law │
│ Estate Tax Exemption          │ $13.61M  │ Rev Pro │
│ Gift Tax Exclusion            │ $18,000  │ Rev Pro │
│ Social Security Wage Base     │ $168,600 │ SSA Ann │
└─────────────────────────────────────────────────────┘

Recent Changes:
  - 401(k) limit increased from $22,500 (2023) to $23,000
  - IRA limit increased from $6,500 (2023) to $7,000
  - HSA limits increased by $150-$300 due to inflation
  - Standard deduction increased by ~$750 (single)
```

---

### `tax-agent research changes`

Check for recent tax law changes affecting this tax year.

**Usage:**
```bash
tax-agent research changes [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)

**Examples:**
```bash
# Check changes for current year
tax-agent research changes

# Check what changed for 2023
tax-agent research changes --year 2023
```

---

### `tax-agent research state <state>`

Research state-specific tax rules.

**Usage:**
```bash
tax-agent research state <state_code> [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)

**Examples:**
```bash
# California tax rules
tax-agent research state CA

# New York for previous year
tax-agent research state NY --year 2023

# Texas (no income tax)
tax-agent research state TX
```

**Output Example (California):**
```
┌────── CA Tax Rules - 2024 ──────┐
│ State Tax Info                  │
└─────────────────────────────────┘

Top Marginal Rate        13.30%
Capital Gains            Taxed as ordinary income
Federal Conformity       Partial (many differences)

Notable Credits:
  - CA Earned Income Tax Credit (CalEITC)
  - Young Child Tax Credit
  - Renters Credit
  - Solar Energy System Credit

Recent Changes:
  - Middle Class Tax Refund (one-time, 2022)
  - Increased MCTR thresholds for inflation
  - New pass-through entity tax election
```

**Output Example (No Income Tax State):**
```
TX has NO state income tax!
```

## Google Drive Integration

See [GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md) for detailed setup instructions.

### `tax-agent drive auth`

Authenticate with Google Drive.

**Usage:**
```bash
# Initial setup with credentials file
tax-agent drive auth --setup <path_to_client_secrets.json>

# Re-authenticate
tax-agent drive auth

# Revoke access
tax-agent drive auth --revoke
```

**Examples:**
```bash
# First-time setup
tax-agent drive auth --setup ~/Downloads/client_secrets.json

# Check auth status / re-auth
tax-agent drive auth

# Remove credentials
tax-agent drive auth --revoke
```

---

### `tax-agent drive list [folder-id]`

List folders or files in Google Drive.

**Usage:**
```bash
# List folders in root
tax-agent drive list

# List folders in specific folder
tax-agent drive list <folder_id>

# List files in folder
tax-agent drive list <folder_id> --files
```

**Examples:**
```bash
# List root folders
tax-agent drive list

# List files in "2024 Taxes" folder
tax-agent drive list 1a2b3c4d5e6f --files
```

---

### `tax-agent drive collect <folder-id>`

Collect and process documents from a Google Drive folder.

**Usage:**
```bash
tax-agent drive collect <folder_id> [options]
```

**Options:**
- `--year, -y <year>`: Tax year (defaults to config)
- `--recursive, -r`: Include subfolders

**Examples:**
```bash
# Collect from folder
tax-agent drive collect 1a2b3c4d5e6f

# Collect with subfolders
tax-agent drive collect 1a2b3c4d5e6f --recursive

# Specific tax year
tax-agent drive collect 1a2b3c4d5e6f --year 2023
```

## Advanced Usage

### Batch Processing Multiple Years

```bash
# Process 2023 documents
tax-agent collect ~/taxes/2023/ --dir --year 2023
tax-agent analyze --year 2023

# Process 2024 documents
tax-agent collect ~/taxes/2024/ --dir --year 2024
tax-agent analyze --year 2024

# Compare years
tax-agent documents list --year 2023
tax-agent documents list --year 2024
```

### Using Different AI Models

```bash
# Use Opus for complex situations (more accurate, slower, costlier)
tax-agent config set model claude-opus-4-20250514

# Process complex return review
tax-agent review ~/taxes/complex_return.pdf

# Switch back to Sonnet for routine tasks
tax-agent config set model claude-sonnet-4-5-20250514
```

### Disabling SSN Redaction

For maximum accuracy, you can disable automatic SSN redaction:

```bash
# Disable redaction
tax-agent config set auto_redact_ssn false

# Collect documents (full SSN sent to AI)
tax-agent collect ~/taxes/w2.pdf

# Re-enable for security
tax-agent config set auto_redact_ssn true
```

**Security Note:** Only disable redaction if you trust your AI provider with full SSN access.

### AWS Bedrock Setup

For enterprise deployments:

```bash
# Re-run init and select Bedrock
tax-agent init

# Select option 2 (AWS Bedrock)
# Enter AWS credentials or use IAM role

# Verify setup
tax-agent status

# Use normally
tax-agent collect ~/taxes/documents/ --dir
```

## Troubleshooting

### Common Issues

#### Database Password Not Found

```bash
# Error: Database password not found. Run 'tax-agent init' first.

# Solution: Re-initialize
tax-agent init
```

#### API Key Not Configured

```bash
# Error: Anthropic API key not configured

# Solution: Update API key
tax-agent config api-key
```

#### Low Confidence Extraction

```bash
# Document flagged for review (confidence < 80%)

# Solutions:
# 1. Check document quality
#    - Ensure 300+ DPI
#    - Avoid skewed scans
#    - Use color scans

# 2. Review extracted data
tax-agent documents show <doc_id>

# 3. Delete and re-scan
#    (currently no edit capability)
```

#### Tesseract Not Found

```bash
# Error: tesseract is not installed or not in PATH

# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# Verify
tesseract --version
```

#### Poppler Not Found

```bash
# Error: Unable to get page count. Is poppler installed?

# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils

# Verify
pdftoppm -v
```

#### Google Drive Authentication Failed

```bash
# Error: Not authenticated with Google Drive

# Solution: Run auth setup
tax-agent drive auth --setup ~/Downloads/client_secrets.json

# See GOOGLE_DRIVE_SETUP.md for detailed instructions
```

### Getting Help

```bash
# Command-level help
tax-agent --help
tax-agent collect --help
tax-agent optimize --help

# Check configuration
tax-agent status
tax-agent config get

# Verify system dependencies
tesseract --version
pdftoppm -v
python --version
```

### Debugging

#### Enable Verbose Output

Currently not supported, but you can check:

```bash
# Review specific document
tax-agent documents show <id>

# Check all documents for a year
tax-agent documents list --year 2024

# Verify analysis
tax-agent analyze --no-ai  # Skip AI for faster checks
```

#### Check Database

The encrypted database is at: `~/.tax-agent/data/tax_data.db`

```bash
# Check database exists
ls -lh ~/.tax-agent/data/

# Verify configuration
cat ~/.tax-agent/config.json
```

#### API Usage and Costs

```bash
# Use Sonnet (default) for cost-effective analysis
tax-agent config set model claude-sonnet-4-5-20250514

# Reserve Opus for complex reviews only
tax-agent config set model claude-opus-4-20250514
tax-agent review complex_return.pdf

# Check current model
tax-agent config get model
```

### Data Backup

```bash
# Backup encrypted database
cp -r ~/.tax-agent/data/ ~/Backups/tax-agent-backup-2024-01-15/

# Backup includes:
# - tax_data.db (encrypted)
# - All document data

# To restore:
cp -r ~/Backups/tax-agent-backup-2024-01-15/ ~/.tax-agent/data/
```

**Important:** Keep your encryption password safe. Cannot recover data without it.

---

## Quick Reference

### Common Workflows

**First-Time User:**
```bash
tax-agent init
tax-agent config set state CA
tax-agent config set filing_status single
tax-agent collect ~/taxes/2024/ --dir
tax-agent analyze
tax-agent optimize
```

**Returning User:**
```bash
tax-agent collect new_document.pdf
tax-agent analyze
```

**Return Review:**
```bash
tax-agent review ~/taxes/2024_return.pdf
```

**Multi-Year Analysis:**
```bash
tax-agent analyze --year 2023
tax-agent analyze --year 2024
```

### Keyboard Shortcuts in Chat

- `Ctrl+C`: Exit chat session
- `Ctrl+D`: Exit chat session (Unix/Linux)
- Type `quit`: Exit gracefully

### File Size Limits

- PDFs: No strict limit (practical limit ~50MB)
- Images: Recommended max 10MB
- Processing time increases with file size

### Supported Tax Forms

**Income:** W-2, 1099-INT, 1099-DIV, 1099-B, 1099-NEC, 1099-MISC, 1099-R, 1099-G, 1099-K, K-1

**Deductions/Credits:** 1098, 1098-T, 1098-E, 5498

**Other:** W-2G (gambling), most IRS forms

For comprehensive form list, see [README.md](../README.md#supported-document-types).
