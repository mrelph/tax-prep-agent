# Tax Prep Agent

A CLI-powered tax document collection, analysis, and optimization tool that uses AI (Claude) to help you manage tax documents, identify deductions, and review tax returns. Built for individuals dealing with complex tax situations including stock compensation (RSUs, ISOs, ESPP), multiple income sources, and state-specific considerations.

## Features

### Document Collection & Processing
- **Smart Document Classification**: Automatically identifies tax document types using AI-powered OCR
- **Supported Document Types**: W-2, all 1099 variants (INT, DIV, B, NEC, MISC, R, G, K), 1098 forms, K-1, and more
- **Encrypted Storage**: All tax data is stored in an encrypted SQLite database using SQLCipher
- **Batch Processing**: Process entire directories of tax documents at once
- **High Accuracy**: Uses Claude's vision capabilities to extract structured data from PDFs and images

### AI-Powered Tax Analysis
- **Tax Implications Analysis**: Comprehensive review of your tax situation based on collected documents
- **Income Breakdown**: Detailed analysis by income type (wages, dividends, capital gains, etc.)
- **Withholding Analysis**: Identifies potential underpayment or overpayment situations
- **Estimated Tax Calculation**: Projects your tax liability and refund/payment amounts

### Tax Optimization Interview
- **Interactive Questionnaire**: AI-generated questions tailored to your specific tax situation
- **Deduction Discovery**: Identifies missed deductions and credits you may qualify for
- **Standard vs. Itemized Analysis**: Determines the best deduction strategy
- **Smart Follow-ups**: Asks relevant follow-up questions based on your answers

### Stock Compensation Expertise
- **RSU Tax Analysis**: Comprehensive handling of Restricted Stock Units including vesting, sales, and withholding
- **ISO Support**: Incentive Stock Options with AMT implications and holding period analysis
- **NSO & ESPP**: Non-qualified stock options and employee stock purchase plan handling
- **Wash Sale Detection**: Identifies potential wash sale issues in investment transactions
- **Tax Withholding Gaps**: Highlights common withholding shortfalls with equity compensation

### Tax Return Review
- **Error Detection**: Automatically identifies math errors, missing income, and incorrect amounts
- **Optimization Suggestions**: Finds missed deductions and credits in completed returns
- **Compliance Checking**: Flags potential IRS compliance concerns
- **Impact Analysis**: Estimates dollar impact of each finding

### Security & Privacy
- **Encrypted Database**: All data stored using SQLCipher with AES-256 encryption
- **Secure Key Storage**: API keys and passwords stored in system keyring (Keychain/Windows Credential Manager)
- **Automatic Redaction**: SSN and EIN redaction before sending data to AI (configurable)
- **Local Processing**: OCR and PDF parsing happen locally before AI analysis

### AI Provider Flexibility
- **Anthropic API**: Direct integration with Claude via Anthropic API (default)
- **AWS Bedrock** (Coming Soon): Use Claude through AWS Bedrock for enterprise deployments
- **Configurable Models**: Choose your preferred Claude model (Sonnet, Opus, etc.)

## Installation

### Prerequisites
- Python 3.11 or higher
- Tesseract OCR (for document scanning)
- Poppler (for PDF processing)

### Install System Dependencies

**macOS** (using Homebrew):
```bash
brew install tesseract poppler
```

**Ubuntu/Debian**:
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

**Windows**:
1. Download and install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Download and install [Poppler](https://blog.alivate.com.au/poppler-windows/)
3. Add both to your system PATH

### Install Tax Prep Agent

**Install from source**:
```bash
# Clone the repository
git clone <repository-url>
cd tax-prep-agent

# Install with pip
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

**Verify installation**:
```bash
tax-agent --help
```

## Quick Start

### 1. Initialize the Agent

Set up encrypted storage and configure your API key:

```bash
tax-agent init
```

You'll be prompted for:
- **Encryption password**: Protects your tax data (choose a strong password)
- **Anthropic API key**: Your Claude API key (get one at [console.anthropic.com](https://console.anthropic.com))

Your data will be stored in `~/.tax-agent/data/` with encryption enabled.

### 2. Configure Basic Settings

```bash
# Set your state (for state tax considerations)
tax-agent config set state CA

# Set tax year (defaults to 2024)
tax-agent config set tax_year 2024

# Set filing status
tax-agent config set filing_status single
```

### 3. Collect Tax Documents

Process a single document:
```bash
tax-agent collect ~/Documents/taxes/w2_2024.pdf
```

Process an entire directory:
```bash
tax-agent collect ~/Documents/taxes/ --dir
```

The agent will:
1. Extract text using OCR (for images) or PDF parsing
2. Classify the document type using AI
3. Extract structured data from the document
4. Store everything securely in the encrypted database
5. Flag any documents that need manual review

### 4. Analyze Your Tax Situation

```bash
tax-agent analyze
```

Get a comprehensive analysis including:
- Total income by source
- Tax withholding summary
- Estimated tax liability
- Refund or amount owed projection
- AI-powered insights and recommendations

### 5. Find Tax Optimization Opportunities

```bash
tax-agent optimize
```

Run an interactive interview to identify:
- Deductions you qualify for
- Tax credits you may have missed
- Strategies for stock compensation
- Planning opportunities for next year

## CLI Command Reference

### Core Commands

#### `tax-agent init`
Initialize the tax agent with encryption and API configuration.

```bash
tax-agent init
```

**Interactive prompts**:
- Encryption password (stored in system keyring)
- Anthropic API key (stored in system keyring)

#### `tax-agent status`
Show current configuration and initialization status.

```bash
tax-agent status
```

**Output**:
- Initialization status
- Current tax year
- Configured state
- API key status
- Data directory location

#### `tax-agent collect <file>`
Collect and process a tax document.

```bash
# Process single file
tax-agent collect ~/taxes/w2.pdf

# Process with specific year
tax-agent collect ~/taxes/1099-int.pdf --year 2023

# Process entire directory
tax-agent collect ~/taxes/ --dir
```

**Options**:
- `--year, -y`: Specify tax year (defaults to config setting)
- `--dir, -d`: Process all files in directory

**Supported formats**:
- PDF documents
- Image files (PNG, JPG, TIFF)

#### `tax-agent analyze`
Analyze collected documents for tax implications.

```bash
# Full analysis with AI insights
tax-agent analyze

# Brief summary only
tax-agent analyze --summary

# Analysis without AI commentary
tax-agent analyze --no-ai

# Specific tax year
tax-agent analyze --year 2023
```

**Options**:
- `--year, -y`: Tax year to analyze
- `--summary, -s`: Brief summary only
- `--ai / --no-ai`: Include/exclude AI analysis (default: enabled)

**Output includes**:
- Income summary by source
- Tax estimate
- Withholding summary
- Refund or amount owed
- AI tax analysis and recommendations

#### `tax-agent optimize`
Find tax-saving opportunities through AI-powered interview.

```bash
# Run interactive optimization
tax-agent optimize

# Skip interview (use collected data only)
tax-agent optimize --no-interview

# Specific tax year
tax-agent optimize --year 2023
```

**Options**:
- `--year, -y`: Tax year
- `--interview / --no-interview, -i`: Run interactive interview (default: enabled)

**The interview covers**:
- Home ownership and mortgage interest
- Retirement contributions
- Health insurance and HSA eligibility
- Work-from-home situations
- Stock compensation (RSUs, ISOs, ESPP, NSOs)
- Educational expenses
- Charitable giving
- State-specific considerations

**Stock compensation deep dive**:
When you indicate stock compensation, the agent asks detailed follow-ups:
- Number of shares vested/exercised
- Vesting/exercise price
- Sales and sale prices
- Company name

And provides analysis of:
- Tax treatment (ordinary income vs. capital gains)
- Withholding sufficiency
- AMT implications (for ISOs)
- Wash sale risks
- Optimization strategies

#### `tax-agent review <return-file>`
Review a completed tax return for errors and optimization opportunities.

```bash
tax-agent review ~/taxes/2024_tax_return.pdf

# Specific tax year
tax-agent review ~/taxes/return.pdf --year 2024
```

**Options**:
- `--year, -y`: Tax year

**The review checks for**:
- Math errors
- Missing income
- Incorrect amounts vs. source documents
- Missed deductions and credits
- Compliance concerns
- Optimization opportunities

**Finding severity levels**:
- **ERROR**: Must be corrected (math errors, missing income)
- **WARNING**: Should be verified (unusual amounts, missing documentation)
- **SUGGESTION**: Optional improvements (missed deductions)
- **INFO**: Informational items

### Document Management

#### `tax-agent documents list`
List all collected tax documents.

```bash
# List all documents for current year
tax-agent documents list

# List for specific year
tax-agent documents list --year 2023
```

**Options**:
- `--year, -y`: Filter by tax year

#### `tax-agent documents show <id>`
Show detailed information about a specific document.

```bash
# Full document ID or partial match
tax-agent documents show abc12345

# Partial ID (must be unique)
tax-agent documents show abc
```

**Output includes**:
- Document type
- Issuer information
- Tax year
- Confidence score
- Review status
- All extracted data (structured JSON)
- Source file path

### Configuration Management

#### `tax-agent config set <key> <value>`
Set a configuration value.

```bash
# Set state
tax-agent config set state CA

# Set tax year
tax-agent config set tax_year 2024

# Set filing status
tax-agent config set filing_status married_joint

# Set AI model
tax-agent config set model claude-sonnet-4-20250514

# Enable/disable SSN redaction
tax-agent config set auto_redact_ssn true
```

**Valid configuration keys**:
- `state`: Two-letter state code (e.g., CA, NY, TX)
- `tax_year`: Four-digit year (e.g., 2024)
- `filing_status`: single, married_joint, married_separate, head_of_household, qualifying_widow
- `model`: Claude model name (e.g., claude-sonnet-4-20250514, claude-opus-4-20250514)
- `auto_redact_ssn`: true/false

#### `tax-agent config get [key]`
Get configuration value(s).

```bash
# Get specific value
tax-agent config get state

# Get all configuration
tax-agent config get
```

#### `tax-agent config api-key`
Update your Anthropic API key.

```bash
tax-agent config api-key
```

## Configuration Options

### Configuration File Location
`~/.tax-agent/config.json`

### Available Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `tax_year` | integer | 2024 | Current tax year being processed |
| `state` | string | null | Two-letter state code for state tax rules |
| `filing_status` | string | null | Tax filing status (see values below) |
| `ai_provider` | string | "anthropic" | AI provider: "anthropic" or "aws_bedrock" |
| `model` | string | "claude-sonnet-4-20250514" | Claude model to use |
| `aws_region` | string | "us-east-1" | AWS region for Bedrock (when using AWS) |
| `ocr_engine` | string | "pytesseract" | OCR engine for document processing |
| `auto_redact_ssn` | boolean | true | Automatically redact SSN/EIN before AI processing |

**Filing status values**:
- `single`
- `married_joint` (Married Filing Jointly)
- `married_separate` (Married Filing Separately)
- `head_of_household`
- `qualifying_widow` (Qualifying Widow(er))

### Secure Credential Storage

Sensitive credentials are stored in your system's secure keyring:
- **macOS**: Keychain
- **Windows**: Credential Manager
- **Linux**: Secret Service API / gnome-keyring

**Stored credentials**:
- Anthropic API key
- AWS credentials (when using Bedrock)
- Database encryption password

## Supported Document Types

The agent can process and extract data from the following tax forms:

### Income Documents

| Form | Description | Key Data Extracted |
|------|-------------|-------------------|
| **W-2** | Wage and Tax Statement | Wages, federal/state withholding, SS/Medicare, Box 12 codes |
| **1099-INT** | Interest Income | Interest income, early withdrawal penalty, tax-exempt interest |
| **1099-DIV** | Dividend Income | Ordinary dividends, qualified dividends, capital gain distributions |
| **1099-B** | Brokerage Transactions | Stock sales, proceeds, cost basis, wash sales, short/long-term gains |
| **1099-NEC** | Non-Employee Compensation | Self-employment income, contractor payments |
| **1099-MISC** | Miscellaneous Income | Rent, royalties, other income |
| **1099-R** | Retirement Distributions | IRA/401k distributions, taxable amounts, early withdrawal penalties |
| **1099-G** | Government Payments | Unemployment compensation, state tax refunds |
| **1099-K** | Payment Card Transactions | Third-party payment processor income |
| **K-1** | Partnership/S-Corp Income | Pass-through income, losses, deductions |

### Deduction & Credit Documents

| Form | Description | Key Data Extracted |
|------|-------------|-------------------|
| **1098** | Mortgage Interest | Mortgage interest paid, points, property tax |
| **1098-T** | Tuition Statement | Qualified tuition, scholarships, education credits eligibility |
| **1098-E** | Student Loan Interest | Student loan interest paid |
| **5498** | IRA Contributions | Traditional/Roth IRA contributions, rollover amounts |

### Additional Support
- **W-2G**: Gambling winnings
- **1099 variants**: All major 1099 forms
- **Unknown documents**: Flagged for manual review

## AI Provider Options

### Anthropic API (Default)

Direct integration with Anthropic's Claude API.

**Setup**:
1. Get API key from [console.anthropic.com](https://console.anthropic.com)
2. Run `tax-agent init` or `tax-agent config api-key`
3. Enter your API key when prompted

**Pricing**: Pay-per-use based on Anthropic's pricing
**Best for**: Individual use, small businesses

### AWS Bedrock (Coming Soon)

Use Claude through AWS Bedrock for enterprise deployments.

**Benefits**:
- AWS billing integration
- VPC deployment options
- Enterprise security compliance
- AWS CloudWatch logging

**Setup** (when available):
```bash
# Set AI provider
tax-agent config set ai_provider aws_bedrock

# Set AWS region
tax-agent config set aws_region us-east-1

# Configure AWS credentials (stored in system keyring)
# Credentials will be prompted during init or can be set via AWS CLI
```

**Prerequisites**:
- AWS account with Bedrock access
- Claude model access enabled in your AWS region
- AWS credentials with appropriate permissions

**Best for**: Enterprise deployments, organizations already on AWS

## Security Features

### Data Encryption

**Database Encryption**:
- Uses SQLCipher for transparent database encryption
- AES-256 encryption algorithm
- PBKDF2 key derivation with 600,000 iterations (OWASP recommended)
- Unique encryption key per installation

**Key Storage**:
- Encryption passwords stored in OS-native keyring
- Never stored in plain text
- Separate from application data

### Privacy Protection

**SSN/EIN Redaction**:
```python
# Automatically enabled by default
# SSN patterns (XXX-XX-XXXX or XXXXXXXXX) redacted before AI processing
# EIN patterns (XX-XXXXXXX) redacted before AI processing
```

**Configure redaction**:
```bash
# Enable automatic redaction (default)
tax-agent config set auto_redact_ssn true

# Disable if you need full SSN in analysis
tax-agent config set auto_redact_ssn false
```

**What gets redacted**:
- Full Social Security Numbers → `[SSN REDACTED]`
- Employer Identification Numbers → `[EIN REDACTED]`
- Last 4 digits are preserved for verification

### Data Storage

**Local-only processing**:
- All sensitive data stored locally on your machine
- OCR and PDF parsing happen locally
- Only processed/redacted text sent to AI APIs

**Data location**:
- Database: `~/.tax-agent/data/tax_data.db` (encrypted)
- Config: `~/.tax-agent/config.json` (no secrets)
- Credentials: System keyring (OS-secured)

### Best Practices

1. **Use a strong encryption password**: Min 12+ characters, mix of types
2. **Keep your encryption password safe**: Can't recover data without it
3. **Regularly backup encrypted data**: Copy `~/.tax-agent/data/` directory
4. **Use environment-appropriate AI provider**: Bedrock for enterprise compliance
5. **Review redaction settings**: Enable for production, consider disabling for testing
6. **Rotate API keys periodically**: Use `tax-agent config api-key` to update

## Examples

### Example 1: First-Time Setup and Document Collection

```bash
# Initial setup
tax-agent init
# Enter encryption password: ************
# Enter Anthropic API key: sk-ant-...

# Configure basic settings
tax-agent config set state CA
tax-agent config set filing_status single

# Check status
tax-agent status

# Collect all documents from a folder
tax-agent collect ~/Documents/2024_Taxes/ --dir

# Review collected documents
tax-agent documents list
```

### Example 2: Stock Compensation Analysis

```bash
# Collect your W-2 and 1099-B
tax-agent collect ~/taxes/w2_company.pdf
tax-agent collect ~/taxes/1099b_etrade.pdf

# Run optimization interview
tax-agent optimize

# During the interview:
# Q: Did you receive stock compensation?
# A: Select "RSUs (Restricted Stock Units)"

# Follow-up questions:
# Shares vested: 500
# Average vesting price: $150
# Shares sold: 300
# Average sale price: $175
# Company: TechCorp

# Receive detailed analysis of:
# - Tax treatment (ordinary income at vesting)
# - Withholding gaps (22% vs. your marginal rate)
# - Capital gains on sale ($7,500 short-term gain)
# - Estimated tax impact
# - Optimization strategies
```

### Example 3: Comprehensive Tax Review

```bash
# Collect all documents
tax-agent collect ~/taxes/2024/ --dir

# Analyze your situation
tax-agent analyze

# Run optimization to find deductions
tax-agent optimize

# After filing, review your return
tax-agent review ~/taxes/2024_Form1040.pdf

# Review findings:
# - ERROR: Box 1a missing dividend income from Vanguard ($1,250)
# - WARNING: State tax withheld doesn't match W-2 total
# - SUGGESTION: Missed $500 student loan interest deduction
```

### Example 4: Multi-Year Tax Management

```bash
# Collect documents for 2024
tax-agent collect ~/taxes/2024/ --dir --year 2024

# Collect documents for 2023 (amended return)
tax-agent collect ~/taxes/2023/ --dir --year 2023

# Analyze 2024
tax-agent analyze --year 2024

# Analyze 2023
tax-agent analyze --year 2023

# Compare withholding between years
tax-agent documents list --year 2024
tax-agent documents list --year 2023
```

### Example 5: Finding Deductions

```bash
# Run optimization interview
tax-agent optimize

# Sample interview Q&A:
# Q: Do you own your home?
# A: y

# Q: Did you contribute to retirement accounts?
# A: y

# Q: What type of health insurance do you have?
# A: HSA-eligible HDHP

# Q: Did you pay for education expenses?
# A: y

# Receive recommendations:
# - Mortgage interest deduction: $12,000
# - Property tax deduction: $8,000
# - HSA contribution room: $4,150
# - Lifetime Learning Credit: $2,000
# - Standard vs. Itemized: ITEMIZE (saves $3,200)
```

## Troubleshooting

### Installation Issues

**Tesseract not found**:
```bash
# Verify Tesseract installation
tesseract --version

# macOS: Install via Homebrew
brew install tesseract

# Ubuntu: Install via apt
sudo apt-get install tesseract-ocr
```

**Poppler not found**:
```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

### Runtime Issues

**"Database password not found" error**:
```bash
# Re-run initialization
tax-agent init
```

**"API key not configured" error**:
```bash
# Update API key
tax-agent config api-key
```

**Low confidence document extraction**:
- Ensure document image is high quality (300+ DPI recommended)
- Check that document is not too rotated or skewed
- Review flagged documents manually: `tax-agent documents show <id>`
- Scan documents in color if possible

**SQLCipher import error** (falls back to unencrypted):
```bash
# Install SQLCipher Python bindings
pip install sqlcipher3-binary

# Verify installation
python -c "import sqlcipher3; print('SQLCipher OK')"
```

### Common Questions

**Q: Can I edit extracted data?**
A: Currently, editing is not supported via CLI. Documents with low confidence are flagged for review. You can delete and re-collect documents.

**Q: What happens if I forget my encryption password?**
A: The data cannot be recovered. Keep your password safe and consider backing up your encrypted database.

**Q: Does the AI see my full SSN?**
A: By default, no. SSNs are automatically redacted before sending to the AI API. Only last 4 digits are preserved for verification.

**Q: Can I use this for business taxes?**
A: The current version is designed for individual tax returns (Form 1040). Business tax support (Schedule C, partnerships) is limited but improving.

**Q: How accurate is the tax calculation?**
A: The agent provides estimates based on collected documents. Always verify with a tax professional or tax software for final filing.

**Q: Which Claude model should I use?**
A:
- **claude-sonnet-4-20250514** (default): Best balance of speed, cost, and accuracy
- **claude-opus-4-20250514**: Highest accuracy for complex situations (more expensive)
- Use Sonnet for routine analysis, Opus for complex stock compensation or large returns

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=tax_agent --cov-report=html

# Run specific test
pytest tests/test_analyzers.py
```

### Code Quality

```bash
# Linting with Ruff
ruff check .

# Auto-fix issues
ruff check --fix .

# Type checking
mypy src/tax_agent
```

### Project Structure

```
tax-prep-agent/
├── src/tax_agent/
│   ├── __init__.py
│   ├── cli.py              # CLI commands and interface
│   ├── agent.py            # Claude API integration
│   ├── config.py           # Configuration management
│   ├── analyzers/
│   │   ├── deductions.py   # Deduction finder and optimizer
│   │   └── implications.py # Tax implications analyzer
│   ├── collectors/
│   │   ├── ocr.py          # OCR processing
│   │   ├── pdf_parser.py   # PDF text extraction
│   │   └── document_classifier.py  # Document type classification
│   ├── models/
│   │   ├── documents.py    # Document data models
│   │   ├── returns.py      # Tax return models
│   │   └── taxpayer.py     # Taxpayer profile models
│   ├── reviewers/
│   │   └── error_checker.py  # Tax return reviewer
│   └── storage/
│       ├── database.py     # Encrypted database
│       └── encryption.py   # Encryption utilities
├── tests/
│   ├── conftest.py
│   ├── test_analyzers.py
│   └── test_models.py
├── data/                   # Reference data
│   ├── prompts/            # AI prompts
│   └── tax_rules/          # Tax rule definitions
├── pyproject.toml          # Project configuration
└── README.md
```

## Documentation

Comprehensive documentation is available in the `/docs` directory:

- **[Usage Guide](docs/USAGE.md)** - Complete CLI command reference with examples
- **[Google Drive Setup](docs/GOOGLE_DRIVE_SETUP.md)** - Step-by-step OAuth integration guide
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and component documentation
- **[API Reference](docs/API.md)** - Python module and API documentation

See the [Documentation Index](docs/README.md) for a complete guide to all documentation.

## Contributing

Contributions are welcome! Areas for improvement:

1. **Additional document types**: Support for more specialized forms
2. **State tax rules**: Expanded state-specific deduction logic
3. **Business tax support**: Schedule C, partnerships, S-corps
4. **Multi-state handling**: Better support for multi-state filers
5. **Tax planning**: Forward-looking tax planning features
6. **Export capabilities**: Export to TurboTax, H&R Block formats
7. **Audit trail**: Better documentation and audit logging

Please see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and [API.md](docs/API.md) for technical details on extending the system.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This tool is for informational purposes only and does not constitute tax advice. Always consult with a qualified tax professional for your specific situation. The developers are not responsible for any errors, omissions, or tax filing issues resulting from use of this software.

## Changelog

### Version 0.1.0 (Current)
- Initial release
- Document collection and classification
- AI-powered tax analysis
- Tax optimization interview
- Stock compensation analysis (RSUs, ISOs, NSOs, ESPP)
- Tax return review
- Encrypted database storage
- Anthropic API integration
- AWS Bedrock support (coming soon)

## Support

For issues, questions, or feature requests, please open an issue on the GitHub repository.

---

**Built with**:
- [Claude](https://www.anthropic.com/claude) (Anthropic's AI assistant)
- [Typer](https://typer.tiangolo.com/) (CLI framework)
- [Rich](https://rich.readthedocs.io/) (Terminal formatting)
- [Pydantic](https://docs.pydantic.dev/) (Data validation)
- [SQLCipher](https://www.zetetic.net/sqlcipher/) (Encrypted database)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (Document scanning)
