# Tax Prep Agent Documentation

Comprehensive documentation for the Tax Prep Agent - an AI-powered CLI tool for tax document collection, analysis, and return review.

## Documentation Index

### Getting Started

- **[Main README](../README.md)** - Project overview, installation, and quick start
- **[Usage Guide](USAGE.md)** - Complete CLI command reference with examples

### Integration Guides

- **[Google Drive Setup](GOOGLE_DRIVE_SETUP.md)** - Step-by-step OAuth setup for Google Drive integration

### Technical Documentation

- **[Architecture Overview](ARCHITECTURE.md)** - System design, component interaction, and data flow
- **[API Reference](API.md)** - Python module and API documentation

## Quick Links

### Common Tasks

| Task | Documentation |
|------|---------------|
| First-time setup | [README: Installation](../README.md#installation) → [USAGE: Getting Started](USAGE.md#getting-started) |
| Collect documents | [USAGE: collect command](USAGE.md#tax-agent-collect-file) |
| Analyze taxes | [USAGE: analyze command](USAGE.md#tax-agent-analyze) |
| Find deductions | [USAGE: optimize command](USAGE.md#tax-agent-optimize) |
| Review return | [USAGE: review command](USAGE.md#tax-agent-review-return-file) |
| Google Drive setup | [Google Drive Setup Guide](GOOGLE_DRIVE_SETUP.md) |
| Troubleshooting | [USAGE: Troubleshooting](USAGE.md#troubleshooting) |

### Developer Resources

| Resource | Documentation |
|----------|---------------|
| System architecture | [ARCHITECTURE](ARCHITECTURE.md) |
| Module API reference | [API Reference](API.md) |
| Adding new features | [ARCHITECTURE: Extension Points](ARCHITECTURE.md#extension-points) |
| Data models | [API: Models](API.md#models) |
| Testing strategy | [ARCHITECTURE: Testing](ARCHITECTURE.md#testing-strategy) |

## Documentation Overview

### [USAGE.md](USAGE.md)

**Audience:** End users and tax filers

**Contents:**
- Complete CLI command reference
- Interactive examples and workflows
- Configuration options
- Tax research commands
- Google Drive usage
- Common issues and solutions

**Best for:**
- Learning how to use the tool
- Finding command syntax
- Troubleshooting errors
- Understanding features

---

### [GOOGLE_DRIVE_SETUP.md](GOOGLE_DRIVE_SETUP.md)

**Audience:** Users wanting Google Drive integration

**Contents:**
- Step-by-step Google Cloud Console setup
- OAuth 2.0 credential creation
- Authentication flow walkthrough
- Security and privacy details
- Comprehensive troubleshooting

**Best for:**
- Setting up Drive integration for the first time
- Debugging OAuth issues
- Understanding security model
- Revoking access

---

### [ARCHITECTURE.md](ARCHITECTURE.md)

**Audience:** Developers and contributors

**Contents:**
- High-level system design
- Component breakdown and responsibilities
- Data flow diagrams
- AI integration patterns
- Security architecture
- Extension points

**Best for:**
- Understanding how the system works
- Contributing new features
- Debugging complex issues
- Architectural decisions

---

### [API.md](API.md)

**Audience:** Developers building on or extending the tool

**Contents:**
- Complete Python API reference
- Class and method documentation
- Type signatures
- Usage examples
- Error handling

**Best for:**
- Programmatic usage
- Building extensions
- Understanding module interfaces
- API integration

## Documentation Standards

### Code Examples

All code examples are tested and use this format:

```python
# Python code examples include type hints
from tax_agent import get_agent

agent = get_agent()
result = agent.classify_document(text)
```

```bash
# CLI examples show command and expected output
tax-agent collect ~/taxes/w2.pdf

# Output:
# Processing w2.pdf for tax year 2024...
# Document processed successfully!
```

### Conventions

| Symbol | Meaning |
|--------|---------|
| `required_arg` | Required argument or parameter |
| `[optional_arg]` | Optional argument or parameter |
| `<placeholder>` | User-provided value |
| `option1 \| option2` | Choice between options |

### Example Paths

Documentation uses these example paths:

| Platform | Example Path |
|----------|--------------|
| macOS/Linux | `~/Documents/taxes/w2.pdf` |
| Windows | `C:\Users\<YourName>\Documents\taxes\w2.pdf` |
| Generic | `/path/to/file` or `<file_path>` |

## Getting Help

### In-Application Help

```bash
# General help
tax-agent --help

# Command-specific help
tax-agent collect --help
tax-agent optimize --help

# Check configuration
tax-agent status
```

### Documentation Sections

| Question | See |
|----------|-----|
| How do I install this? | [README: Installation](../README.md#installation) |
| What commands are available? | [USAGE: Core Commands](USAGE.md#core-commands) |
| How do I set up Google Drive? | [Google Drive Setup](GOOGLE_DRIVE_SETUP.md) |
| What's the architecture? | [ARCHITECTURE](ARCHITECTURE.md) |
| How do I use the Python API? | [API Reference](API.md) |
| Why isn't it working? | [USAGE: Troubleshooting](USAGE.md#troubleshooting) |
| How accurate is the AI? | [README: Features](../README.md#features) + [ARCHITECTURE: Verification](ARCHITECTURE.md#verification-layer) |
| Is my data secure? | [README: Security](../README.md#security--privacy) + [ARCHITECTURE: Security](ARCHITECTURE.md#security-architecture) |
| Can I use AWS Bedrock? | [USAGE: Configuration](USAGE.md#configuration) + [API: Agent](API.md#agent-module) |

## Feature Documentation

### Core Features

| Feature | User Guide | Developer Docs |
|---------|-----------|----------------|
| Document Collection | [USAGE: collect](USAGE.md#tax-agent-collect-file) | [API: DocumentCollector](API.md#documentcollector) |
| OCR Processing | [README: Features](../README.md#document-collection--processing) | [API: OCR](API.md#tax_agentcollectorsocr) |
| Tax Analysis | [USAGE: analyze](USAGE.md#tax-agent-analyze) | [API: TaxAnalyzer](API.md#taxanalyzer) |
| Optimization | [USAGE: optimize](USAGE.md#tax-agent-optimize) | [API: TaxOptimizer](API.md#taxoptimizer) |
| Return Review | [USAGE: review](USAGE.md#tax-agent-review-return-file) | [API: ReturnReviewer](API.md#returnreviewer) |
| Google Drive | [Google Drive Setup](GOOGLE_DRIVE_SETUP.md) | [API: GoogleDriveCollector](API.md#googledrivecollector) |
| Tax Research | [USAGE: Research](USAGE.md#tax-research) | [API: TaxResearcher](API.md#tax_agentresearchtax_researcher) |
| Verification | [ARCHITECTURE: Verification](ARCHITECTURE.md#verification-layer) | [API: OutputVerifier](API.md#outputverifier) |
| Encryption | [README: Security](../README.md#security-features) | [ARCHITECTURE: Security](ARCHITECTURE.md#security-architecture) |

### Advanced Topics

| Topic | Documentation |
|-------|---------------|
| Stock compensation (RSUs, ISOs) | [USAGE: Stock Compensation](USAGE.md#stock-compensation-deep-dive) |
| Multi-year tax management | [USAGE: Advanced Usage](USAGE.md#advanced-usage) |
| AWS Bedrock integration | [USAGE: Configuration](USAGE.md#configuration) + [API: TaxAgent](API.md#taxagent) |
| State-specific tax rules | [USAGE: Research State](USAGE.md#tax-agent-research-state-state) |
| Custom AI models | [USAGE: Using Different Models](USAGE.md#using-different-ai-models) |
| Extending document types | [ARCHITECTURE: Extension Points](ARCHITECTURE.md#adding-new-document-types) |

## Contributing to Documentation

### Documentation Structure

```
tax-prep-agent/
├── README.md                 # Main project README
└── docs/
    ├── README.md             # This file (index)
    ├── USAGE.md              # User guide
    ├── GOOGLE_DRIVE_SETUP.md # Integration guide
    ├── ARCHITECTURE.md       # System design
    └── API.md                # API reference
```

### Adding New Documentation

When adding features, update:

1. **README.md** - High-level feature description
2. **USAGE.md** - CLI commands and examples
3. **ARCHITECTURE.md** - Design decisions and component changes
4. **API.md** - New classes, methods, and functions
5. **This index** - Links to new sections

### Documentation Style Guide

**User-facing documentation (USAGE.md, GOOGLE_DRIVE_SETUP.md):**
- Use active voice
- Include concrete examples
- Add "Example output" sections
- Explain WHY, not just HOW
- Anticipate common questions

**Technical documentation (ARCHITECTURE.md, API.md):**
- Use precise technical terms
- Include type signatures
- Add code examples with types
- Explain design decisions
- Link related components

**All documentation:**
- Use markdown formatting
- Include table of contents for long docs
- Cross-reference related sections
- Keep examples up-to-date with code

## Version Information

**Current Version:** 0.1.0

**Last Updated:** January 2026

**Compatibility:**
- Python 3.11+
- Claude Sonnet 4.5 / Opus 4 (2025 models)
- Tesseract 4.0+
- Poppler 0.86+

## Additional Resources

### External Links

- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [IRS Tax Forms](https://www.irs.gov/forms-instructions)
- [Google Drive API](https://developers.google.com/drive)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [SQLCipher](https://www.zetetic.net/sqlcipher/)

### Example Workflows

See the [USAGE Guide](USAGE.md) for complete workflows:

- [First-Time Setup](USAGE.md#first-time-setup)
- [Stock Compensation Analysis](USAGE.md#example-2-stock-compensation-analysis)
- [Comprehensive Tax Review](USAGE.md#example-3-comprehensive-tax-review)
- [Multi-Year Management](USAGE.md#example-4-multi-year-tax-management)
- [Finding Deductions](USAGE.md#example-5-finding-deductions)

### Support

For issues, questions, or feature requests:

1. Check [Troubleshooting](USAGE.md#troubleshooting)
2. Review [Common Issues](GOOGLE_DRIVE_SETUP.md#troubleshooting)
3. Search existing GitHub issues
4. Open a new issue with:
   - Output of `tax-agent status`
   - Error messages (redact sensitive data!)
   - Steps to reproduce

---

**Note:** This is tax preparation software for informational purposes only. Always consult with a qualified tax professional for your specific situation.
