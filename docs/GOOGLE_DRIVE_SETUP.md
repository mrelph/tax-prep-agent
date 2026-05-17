# Google Drive Integration Setup

Complete guide to setting up Google Drive integration for automatic tax document collection.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step 1: Create Google Cloud Project](#step-1-create-google-cloud-project)
- [Step 2: Enable Google Drive API](#step-2-enable-google-drive-api)
- [Step 3: Create OAuth Credentials](#step-3-create-oauth-credentials)
- [Step 4: Configure Tax Prep Agent](#step-4-configure-tax-prep-agent)
- [Usage](#usage)
- [Security and Privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)

## Overview

The Google Drive integration allows you to:

- Automatically collect tax documents from Google Drive folders
- Process PDFs, images, and Google Docs (exported as PDF)
- Recursively process subfolders
- Access documents without downloading them manually

**What You'll Need:**
- Google account (personal or workspace)
- 10-15 minutes for initial setup
- Basic familiarity with Google Cloud Console

**Security:**
- Read-only access to your Drive (no write permissions)
- OAuth 2.0 authentication (industry standard)
- Credentials stored securely in system keyring
- No data shared with third parties

## Prerequisites

1. **Tax Prep Agent Installed**
   ```bash
   tax-agent --version
   ```

2. **Tax Prep Agent Initialized**
   ```bash
   tax-agent status
   # Should show "Initialized: Yes"
   ```

3. **Google Account**
   - Personal Gmail account, OR
   - Google Workspace account (with Drive access)

## Step 1: Create Google Cloud Project

### 1.1 Navigate to Google Cloud Console

Go to: [https://console.cloud.google.com](https://console.cloud.google.com)

- Sign in with your Google account
- Accept Terms of Service if prompted

### 1.2 Create New Project

**Option A: Quick Create (Top Navigation)**
1. Click project dropdown (top left, next to "Google Cloud")
2. Click "NEW PROJECT"
3. Enter project details:
   - **Project name**: `Tax Prep Agent` (or your preference)
   - **Organization**: Leave as "No organization" (or select if applicable)
   - **Location**: Leave default
4. Click "CREATE"
5. Wait 10-30 seconds for project creation

**Option B: Via Console Home**
1. From hamburger menu (☰), select "Home"
2. Click "Create Project"
3. Follow same steps as Option A

### 1.3 Select Your Project

- After creation, ensure your new project is selected (check top navigation bar)
- The project name should appear next to "Google Cloud" logo

**Screenshot Checkpoint:**
```
┌──────────────────────────────────────┐
│ Google Cloud ▼ Tax Prep Agent        │
└──────────────────────────────────────┘
```

## Step 2: Enable Google Drive API

### 2.1 Navigate to API Library

1. From hamburger menu (☰), go to:
   - **APIs & Services** → **Library**

   OR use direct link: [APIs & Services Library](https://console.cloud.google.com/apis/library)

2. You'll see a catalog of Google APIs

### 2.2 Find and Enable Drive API

1. In the search box, type: `Google Drive API`
2. Click on **"Google Drive API"** from results
   - Publisher: Google LLC
   - Category: Google Workspace
3. Click the **"ENABLE"** button
4. Wait for API to enable (usually instant)

**Success Indicator:**
- Page will redirect to API dashboard
- You'll see "Google Drive API" with metrics
- Button changes to "MANAGE"

### 2.3 Verify API Status

From hamburger menu: **APIs & Services** → **Enabled APIs & services**

You should see:
```
Google Drive API     Google LLC     Enabled
```

## Step 3: Create OAuth Credentials

### 3.1 Configure OAuth Consent Screen

**First Time Only:** Google requires you to configure how users will see the authorization screen.

1. Navigate to: **APIs & Services** → **OAuth consent screen**
2. Choose user type:
   - **External** (recommended for personal use)
   - Click "CREATE"

3. Fill out **OAuth consent screen** (App information):
   - **App name**: `Tax Prep Agent`
   - **User support email**: Your email
   - **App logo**: (optional, skip)
   - **Application home page**: (optional, skip)
   - **Application privacy policy**: (optional, skip)
   - **Application terms of service**: (optional, skip)
   - **Authorized domains**: (skip)
   - **Developer contact email**: Your email
   - Click **"SAVE AND CONTINUE"**

4. **Scopes** page:
   - Click **"ADD OR REMOVE SCOPES"**
   - Scroll to find: `.../auth/drive.readonly`
   - OR filter for "drive" and check:
     - ✅ `https://www.googleapis.com/auth/drive.readonly`
   - Click **"UPDATE"**
   - Click **"SAVE AND CONTINUE"**

5. **Test users** page:
   - Click **"+ ADD USERS"**
   - Enter your Google account email
   - Click **"ADD"**
   - Click **"SAVE AND CONTINUE"**

6. **Summary** page:
   - Review details
   - Click **"BACK TO DASHBOARD"**

**Status:** OAuth consent screen is now configured ✅

### 3.2 Create OAuth 2.0 Client ID

1. Navigate to: **APIs & Services** → **Credentials**

2. Click **"+ CREATE CREDENTIALS"** (top of page)

3. Select **"OAuth client ID"**

4. Configure client:
   - **Application type**: `Desktop app`
   - **Name**: `Tax Prep Agent Desktop` (or your preference)
   - Click **"CREATE"**

5. **OAuth client created** dialog appears:
   - Shows your Client ID and Client secret
   - Click **"DOWNLOAD JSON"**
   - Save file as: `client_secrets.json`
   - **Important:** Keep this file secure!
   - Click **"OK"**

**What You Have Now:**
- `client_secrets.json` file downloaded
- Contains OAuth credentials for your app

### 3.3 Locate Downloaded File

**Default download locations:**
- **macOS**: `~/Downloads/client_secrets.json`
- **Windows**: `C:\Users\<YourName>\Downloads\client_secrets.json`
- **Linux**: `~/Downloads/client_secrets.json`

**Rename if needed:**
```bash
# If file has long name like "client_secret_123456789.json"
mv ~/Downloads/client_secret_*.json ~/Downloads/client_secrets.json
```

## Step 4: Configure Tax Prep Agent

### 4.1 Authenticate with Client Secrets

Run the authentication command with your downloaded credentials:

```bash
tax-agent drive auth --setup ~/Downloads/client_secrets.json
```

**Expected flow:**

1. **Terminal output:**
   ```
   Setting up Google Drive integration...
   This will open a browser window for you to authorize access.
   ```

2. **Browser opens automatically** to Google OAuth screen

3. **Google sign-in:**
   - Sign in with your Google account (if not already signed in)

4. **OAuth consent screen:**
   ```
   Tax Prep Agent wants to access your Google Account

   This will allow Tax Prep Agent to:
   ✓ See and download all your Google Drive files

   [Cancel]  [Continue]
   ```

   - Review permissions (read-only access)
   - Click **"Continue"**

5. **Safety warning (if app not verified):**
   ```
   Google hasn't verified this app

   This app hasn't been verified by Google yet.

   [Back to safety] [Advanced]
   ```

   - This is normal for personal apps
   - Click **"Advanced"**
   - Click **"Go to Tax Prep Agent (unsafe)"**
   - This is safe because YOU created the app

6. **Grant permission:**
   ```
   Tax Prep Agent wants to access your Google Account

   See and download all your Google Drive files

   [Cancel]  [Allow]
   ```

   - Click **"Allow"**

7. **Success page:**
   ```
   The authentication flow has completed.
   You may close this window.
   ```

8. **Terminal shows:**
   ```
   Google Drive authentication successful!

   You can now use:
     tax-agent drive collect <folder-id>  - Process documents from a folder
     tax-agent drive list                 - List your folders
   ```

### 4.2 Verify Authentication

```bash
# Check auth status
tax-agent drive auth

# Output if successful:
# Already authenticated with Google Drive.
```

### 4.3 Test Drive Access

```bash
# List folders in your Drive
tax-agent drive list

# Output example:
# ┌─────────────── Folders in Root ───────────────┐
# │ Name                │ ID                      │
# │─────────────────────│─────────────────────────│
# │ 2024 Taxes          │ 1a2b3c4d5e6f            │
# │ 2023 Taxes          │ 9z8y7x6w5v4u            │
# │ Personal            │ 5t4s3r2q1p0o            │
# └─────────────────────────────────────────────────┘
```

**Troubleshooting:** See [Troubleshooting](#troubleshooting) section below.

## Usage

### Finding Folder IDs

**Method 1: Via Tax Prep Agent**
```bash
# List all folders in root
tax-agent drive list

# List subfolders
tax-agent drive list <parent-folder-id>
```

**Method 2: Via Google Drive Web UI**
```
1. Go to drive.google.com
2. Navigate to your folder (e.g., "2024 Taxes")
3. Look at URL in browser:
   https://drive.google.com/drive/folders/1a2b3c4d5e6f7g8h9i0j
                                           ^^^^^^^^^^^^^^^^^
                                           This is your folder ID
```

### Listing Folder Contents

**List files in a folder:**
```bash
tax-agent drive list 1a2b3c4d5e6f --files
```

**Output:**
```
┌──────────────── Files in 2024 Taxes ────────────────┐
│ Name                  │ Type       │ ID            │
│───────────────────────│────────────│───────────────│
│ w2_google.pdf         │ PDF        │ abc123...     │
│ 1099_div_vanguard.pdf │ PDF        │ def456...     │
│ w2_scan.jpg           │ JPG        │ ghi789...     │
│ tax_summary           │ Google Doc │ jkl012...     │
└───────────────────────────────────────────────────────┘

Found 4 supported file(s)
```

### Collecting Documents from Drive

**Basic collection:**
```bash
tax-agent drive collect <folder-id>
```

**With options:**
```bash
# Collect with specific tax year
tax-agent drive collect 1a2b3c4d5e6f --year 2024

# Include subfolders recursively
tax-agent drive collect 1a2b3c4d5e6f --recursive

# Both options
tax-agent drive collect 1a2b3c4d5e6f --year 2024 --recursive
```

**Example:**
```bash
tax-agent drive collect 1a2b3c4d5e6f --recursive

# Output:
# Processing documents from '2024 Taxes' for tax year 2024...
# Including subfolders
#
# Processed 6 file(s):
#   w2_google.pdf: W2 from Google LLC (high confidence)
#   1099_div_vanguard.pdf: 1099_DIV from Vanguard (high confidence)
#   w2_scan.jpg: W2 from Apple Inc (high confidence)
#   1099_int_chase.pdf: 1099_INT from Chase Bank (high confidence)
#   1099_b_etrade.pdf: 1099_B from E*TRADE (high confidence)
#   tax_summary: UNKNOWN (needs review)
#
# Successfully processed 5/6 files.
```

### Complete Workflow

**Full tax preparation workflow using Google Drive:**

```bash
# 1. Set up authentication (one time)
tax-agent drive auth --setup ~/Downloads/client_secrets.json

# 2. Find your tax folder
tax-agent drive list
# Copy the folder ID for "2024 Taxes"

# 3. Collect all documents
tax-agent drive collect 1a2b3c4d5e6f --recursive

# 4. Verify documents collected
tax-agent documents list

# 5. Analyze your tax situation
tax-agent analyze

# 6. Find optimization opportunities
tax-agent optimize

# 7. Review your filed return
tax-agent review ~/Documents/2024_return.pdf
```

## Security and Privacy

### What Access Does Tax Prep Agent Have?

**Permissions granted:**
- ✅ **Read-only access** to Google Drive files
- ✅ Can see file names, content, and metadata
- ✅ Can download files for processing

**Permissions NOT granted:**
- ❌ Cannot modify or delete files
- ❌ Cannot create new files or folders
- ❌ Cannot share files with others
- ❌ No access to Gmail, Calendar, or other Google services

**Scope:** `https://www.googleapis.com/auth/drive.readonly`

### Where Are Credentials Stored?

**Client configuration** (`client_secrets.json`):
- Stored in system keyring after initial setup
- Original file can be deleted after `drive auth --setup`
- Contains OAuth client ID and secret (not sensitive if kept private)

**Access tokens:**
- Stored in system keyring
- Automatically refreshed when expired
- Encrypted by OS-level keyring service

**System keyrings:**
- **macOS**: Keychain Access
- **Windows**: Credential Manager
- **Linux**: Secret Service API / gnome-keyring

### Revoking Access

**Via Tax Prep Agent:**
```bash
tax-agent drive auth --revoke
```

**Via Google:**
1. Go to: [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
2. Find "Tax Prep Agent"
3. Click "Remove Access"

**Deleting the Google Cloud Project:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select "Tax Prep Agent" project
3. Go to: **Settings** → **Shut down**
4. Confirm project deletion

### Privacy Considerations

**What gets sent to AI (Claude)?**
- Document text after OCR extraction
- Redacted SSN/EIN (by default)
- Document classification requests
- Tax analysis queries

**What does NOT get sent to AI?**
- Google Drive file structure
- File names (unless in document content)
- Google credentials or tokens
- Your Google account information

**Data flow:**
```
Google Drive → Tax Prep Agent (local) → OCR/PDF parsing (local)
                                      ↓
                              Redaction (local)
                                      ↓
                              Claude API (remote)
                                      ↓
                              Encrypted DB (local)
```

## Troubleshooting

### Authentication Issues

#### Error: "Client secrets file not found"

**Cause:** File path incorrect or file doesn't exist

**Solution:**
```bash
# Check if file exists
ls -l ~/Downloads/client_secrets.json

# If in different location, use correct path
tax-agent drive auth --setup /path/to/client_secrets.json
```

#### Error: "invalid_client" or "unauthorized_client"

**Cause:** OAuth client credentials are invalid or wrong application type

**Solution:**
1. Delete existing credentials:
   ```bash
   tax-agent drive auth --revoke
   ```

2. Re-create OAuth credentials with correct type:
   - Application type MUST be "Desktop app"
   - NOT "Web application" or "Mobile app"

3. Download fresh `client_secrets.json`

4. Re-run setup:
   ```bash
   tax-agent drive auth --setup ~/Downloads/client_secrets.json
   ```

#### Error: "redirect_uri_mismatch"

**Cause:** OAuth client is configured as wrong application type

**Solution:**
1. Go to Google Cloud Console → Credentials
2. Delete existing OAuth client
3. Create new OAuth client as **"Desktop app"**
4. Download new credentials
5. Re-run `tax-agent drive auth --setup`

#### Error: "Access denied" or "insufficient permissions"

**Cause:** Didn't grant Drive access during OAuth flow

**Solution:**
1. Revoke existing auth:
   ```bash
   tax-agent drive auth --revoke
   ```

2. Re-authenticate and click "Allow" when prompted:
   ```bash
   tax-agent drive auth
   ```

#### Error: "Google hasn't verified this app"

**This is NORMAL for personal projects**

**Solution:**
1. Click "Advanced" link
2. Click "Go to Tax Prep Agent (unsafe)"
3. This is safe - you created the app
4. Grant permissions

**Why this happens:**
- Google verification requires submitting app for review
- Only needed for public apps
- Personal use apps can skip verification

#### Browser doesn't open automatically

**Solution 1: Manual URL**
1. Terminal will show a URL
2. Copy the URL
3. Paste into browser manually
4. Complete OAuth flow

**Solution 2: Check firewall**
```bash
# Ensure localhost port access isn't blocked
# OAuth callback uses http://localhost:PORT
```

### Usage Issues

#### Error: "Not authenticated with Google Drive"

**Cause:** Authentication expired or never completed

**Solution:**
```bash
# Re-authenticate
tax-agent drive auth
```

#### Error: "Folder not found" or "Access denied to folder"

**Cause 1:** Folder ID incorrect

**Solution:**
```bash
# List folders to find correct ID
tax-agent drive list
```

**Cause 2:** Folder not shared with your account

**Solution:**
- Ensure folder is owned by or shared with the Google account you authenticated with
- Check folder permissions in Google Drive web UI

#### No files found in folder

**Cause:** Folder contains unsupported file types

**Solution:**
```bash
# Check what's in the folder
tax-agent drive list <folder-id> --files

# Supported types:
# - PDFs (.pdf)
# - Images (.png, .jpg, .jpeg, .tiff)
# - Google Docs (exported as PDF)
```

#### Google Doc export fails

**Cause:** Large documents or Drive API rate limits

**Solution:**
1. Download Google Doc manually as PDF
2. Process locally:
   ```bash
   tax-agent collect ~/Downloads/tax_doc.pdf
   ```

### Rate Limiting

**Google Drive API quotas:**
- 20,000 queries per 100 seconds per project
- 1,000 queries per 100 seconds per user

**If you hit limits:**
- Wait a few minutes and retry
- Process folders in smaller batches
- Avoid collecting from very large folders

**Check quota usage:**
1. Google Cloud Console
2. **APIs & Services** → **Dashboard**
3. Click "Google Drive API"
4. View "Queries" graph

### Credential Refresh Issues

#### Error: "Token expired" or "invalid_grant"

**Cause:** Refresh token expired (rare, 6 month inactivity)

**Solution:**
```bash
# Re-authenticate
tax-agent drive auth --revoke
tax-agent drive auth
```

### Getting Help

**Check authentication status:**
```bash
tax-agent drive auth
```

**Verify credentials in keyring:**
```bash
# macOS - open Keychain Access
open -a "Keychain Access"
# Search for: "tax-prep-agent"

# Linux - check secret-tool
secret-tool search service tax-prep-agent
```

**Test basic Drive access:**
```bash
# Should list root folders
tax-agent drive list

# Should list files
tax-agent drive list <folder-id> --files
```

**Re-initialize from scratch:**
```bash
# 1. Revoke existing auth
tax-agent drive auth --revoke

# 2. Delete OAuth client in Google Cloud Console
#    APIs & Services → Credentials → Delete client

# 3. Create new OAuth client (Desktop app)

# 4. Download new client_secrets.json

# 5. Re-authenticate
tax-agent drive auth --setup ~/Downloads/client_secrets.json
```

## Advanced Topics

### Multiple Google Accounts

**Limitation:** Tax Prep Agent supports one Google account at a time.

**Workaround for multiple accounts:**

```bash
# Account 1 - work
tax-agent drive auth --setup ~/client_secrets_work.json
tax-agent drive collect <work-folder-id>

# Switch to Account 2 - personal
tax-agent drive auth --revoke
tax-agent drive auth --setup ~/client_secrets_personal.json
tax-agent drive collect <personal-folder-id>
```

### Google Workspace Accounts

**Additional considerations:**
- Workspace admin may need to approve the app
- Check with IT department before creating OAuth credentials
- Some Workspace policies may restrict external apps

**Admin approval process:**
1. Create OAuth credentials as described above
2. Request admin approval in Workspace Admin Console
3. Wait for IT approval
4. Complete authentication flow

### Shared Drives (Team Drives)

**Current support:** Shared Drives are NOT currently supported

**Workaround:**
1. Copy files from Shared Drive to "My Drive"
2. Process from "My Drive" folder

### Automation and Scheduled Collection

**Cron job example (Linux/macOS):**

```bash
# Edit crontab
crontab -e

# Add line to collect daily at 2 AM
0 2 * * * /usr/local/bin/tax-agent drive collect 1a2b3c4d5e6f
```

**Windows Task Scheduler:**
1. Create new task
2. Trigger: Daily at 2:00 AM
3. Action: `tax-agent drive collect <folder-id>`

**Note:** Ensure authentication is valid before scheduling.

## FAQ

**Q: Can I use Google Drive integration without creating a Google Cloud project?**

A: No. Google requires OAuth 2.0 for Drive API access, which requires a Cloud project. This is Google's security requirement.

**Q: Will this cost me money for Google Cloud?**

A: No. The Drive API quota is free for personal use. You only pay if you exceed 1 billion queries per day (extremely unlikely).

**Q: Can Tax Prep Agent upload files to my Drive?**

A: No. It only has read-only access (`drive.readonly` scope).

**Q: What happens to my credentials if I uninstall Tax Prep Agent?**

A: Credentials remain in system keyring. Manually revoke via:
```bash
tax-agent drive auth --revoke
```

**Q: Can I use this with Google Workspace (G Suite)?**

A: Yes, but your Workspace admin may need to approve the app first.

**Q: How do I update my credentials?**

A: Re-run the setup:
```bash
tax-agent drive auth --setup ~/Downloads/new_client_secrets.json
```

**Q: Can multiple people use the same OAuth client?**

A: Yes, but each person needs to authenticate individually with their own Google account.

**Q: How long does authentication last?**

A: Tokens auto-refresh and don't expire unless:
- You revoke access
- You don't use it for 6+ months
- You change your Google password (may require re-auth)

## Next Steps

After setting up Google Drive integration:

1. **Organize your Drive:**
   - Create a "2024 Taxes" folder
   - Upload all tax documents
   - Use consistent naming

2. **Collect documents:**
   ```bash
   tax-agent drive collect <folder-id>
   ```

3. **Run analysis:**
   ```bash
   tax-agent analyze
   tax-agent optimize
   ```

4. **Set up automation** (optional):
   - Schedule periodic collection
   - Auto-process new documents

## Resources

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/about-sdk)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Cloud Console](https://console.cloud.google.com)
- [Manage Third-Party Access](https://myaccount.google.com/permissions)

---

**Still having issues?** Check the [main troubleshooting guide](USAGE.md#troubleshooting) or open an issue on GitHub.
