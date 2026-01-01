# MyAgents Setup Guide

This guide covers end-user installation and configuration for MyAgents. If you are a developer looking to contribute to MyAgents, see [guides/getting-started.md](guides/getting-started.md) instead.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration Setup](#configuration-setup)
- [First-Time Setup Workflow](#first-time-setup-workflow)
- [Verifying Your Setup](#verifying-your-setup)
- [Using MyAgents](#using-myagents)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Prerequisites

Before installing MyAgents, ensure you have:

### Required Software

1. **Python 3.11 or higher**
   ```bash
   # Check your Python version
   python --version
   ```
   If you need to install Python 3.11+, visit [python.org](https://www.python.org/downloads/)

2. **uv Package Manager**

   uv is a fast Python package installer and resolver. Install it with:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   After installation, verify it's working:
   ```bash
   uv --version
   ```

### Required GCP Resources

MyAgents requires a Google Cloud Platform (GCP) project with Secret Manager configured:

1. **GCP Project** - An active GCP project with billing enabled
2. **GCP Service Account** - A service account with Secret Manager access
3. **Secret Manager API** - Enabled on your GCP project
4. **API Keys in Secret Manager** - Your API keys stored as secrets:
   - `GEMINI_API_KEY` (required) - For LLM functionality
   - `LANGSMITH_API_KEY` (optional) - For LangSmith tracing

---

## Installation

### Method 1: Developer Installation (Recommended)

If you have access to the MyAgents repository:

```bash
# Clone the repository
git clone https://github.com/HuaMick/MyAgents.git
cd MyAgents

# Install dependencies using uv
uv sync

# Install the package in editable mode
pip install -e .

# Verify installation
myagents --version
```

See [guides/getting-started.md](guides/getting-started.md) for detailed developer setup instructions.

### Method 2: Package Installation

If MyAgents is available as a package in your organization's private registry:

```bash
# Install from private registry
uv pip install myagents

# Verify installation
myagents --version
```

Note: This method requires your organization's GCP Artifact Registry to be configured. Contact your administrator for registry access.

---

## Configuration Setup

MyAgents requires configuration for GCP authentication and secret access. This section walks you through creating the required configuration file.

### Understanding Configuration Files

MyAgents uses two configuration files:

1. **gcptoolkit config** (REQUIRED): `~/.config/agent-gcptoolkit/config.yml`
   - Required for GCP authentication and secret access
   - Contains service account path and project ID
   - Must be created before using `myagents chat`

2. **Studio config** (OPTIONAL): `~/.config/myagents/config.yml`
   - Optional settings for LangGraph Studio
   - Auto-created on first Studio use
   - Can be created manually with `myagents setup`

### Configuration File Structure

The required gcptoolkit configuration file has this structure:

```yaml
authentication:
  type: service_account
  service_account_path: /path/to/your/service-account-key.json

gcp:
  project_id: your-gcp-project-id
```

---

## First-Time Setup Workflow

Follow these steps to set up MyAgents for the first time:

### Step 1: Prepare Your GCP Service Account

You need a GCP service account JSON key file. You have two options:

**Option A: Use Application Default Credentials (Recommended)**

```bash
# Authenticate with GCP
gcloud auth application-default login

# This creates credentials at:
# ~/.config/gcloud/application_default_credentials.json
```

**Option B: Use a Service Account Key File**

1. Go to [GCP Console](https://console.cloud.google.com/)
2. Navigate to: IAM & Admin > Service Accounts
3. Create a new service account or select an existing one
4. Grant the service account the following roles:
   - Secret Manager Secret Accessor
5. Create and download a JSON key file
6. Save it to a secure location (e.g., `~/.config/gcp/service-account-key.json`)

### Step 2: Create Configuration File Manually

Create the configuration file at `~/.config/agent-gcptoolkit/config.yml`:

```bash
# Create the directory
mkdir -p ~/.config/agent-gcptoolkit

# Create the config file using your preferred editor
nano ~/.config/agent-gcptoolkit/config.yml
```

Add the following content (adjust paths and project ID):

```yaml
authentication:
  type: service_account
  service_account_path: ~/.config/gcloud/application_default_credentials.json

gcp:
  project_id: your-gcp-project-id
```

**Important:** Replace `your-gcp-project-id` with your actual GCP project ID.

If using a service account key file instead of application default credentials, update the path accordingly:

```yaml
authentication:
  type: service_account
  service_account_path: ~/.config/gcp/service-account-key.json

gcp:
  project_id: your-gcp-project-id
```

### Step 3: Verify Configuration

After creating the configuration file, verify it's valid:

```bash
myagents config verify
```

Expected output:
```
✓ Configuration is valid
  Config file: /home/user/.config/agent-gcptoolkit/config.yml
```

If you see errors, check that:
- The file path is correct
- The YAML syntax is valid
- The service account file exists at the specified path
- The project ID is correct

### Step 4: Test Secret Access

Verify that MyAgents can access your secrets in GCP Secret Manager:

```bash
myagents secrets get GEMINI_API_KEY
```

Expected output:
```
Secret 'GEMINI_API_KEY': your-api-key-value
```

If this fails, see the [Troubleshooting](#troubleshooting) section.

### Step 5: Optional Studio Setup

If you plan to use LangGraph Studio, create the Studio configuration:

```bash
myagents setup
```

This creates `~/.config/myagents/config.yml` with default Studio settings.

---

## Verifying Your Setup

After completing the configuration, verify everything is working:

### 1. Check Command Availability

```bash
# Should display version
myagents --version

# Should display help
myagents --help
```

### 2. Verify Configuration

```bash
# Show current config path
myagents config show

# Verify config is valid
myagents config verify

# List all config settings
myagents config list
```

### 3. Test Secret Access

```bash
# Test GEMINI_API_KEY access
myagents secrets get GEMINI_API_KEY

# Test LANGSMITH_API_KEY access (if configured)
myagents secrets get LANGSMITH_API_KEY
```

### 4. Test Agent Chat (Final Verification)

```bash
# Start interactive chat with coding agent
myagents chat

# At the prompt, type a simple message:
You: Hello

# You should get a response from the agent
Agent: Hello! How can I help you today?

# Type 'quit' to exit
```

If all these steps succeed, your MyAgents installation is complete and working!

---

## Using MyAgents

Now that setup is complete, you can start using MyAgents:

### Start Interactive Chat

```bash
# Use the coding agent (default)
myagents chat

# Use the echo agent
myagents chat --agent echo
```

### Manage Secrets

```bash
# Get a secret value
myagents secrets get GEMINI_API_KEY

# Get a secret with quiet output (for scripts)
myagents secrets get GEMINI_API_KEY -q

# Specify a different project
myagents secrets get MY_SECRET --project-id my-other-project
```

### Manage Configuration

```bash
# Show current config path
myagents config show

# Verify config is valid
myagents config verify

# List all settings
myagents config list

# Use a different config file
myagents config set-path /path/to/custom/config.yml

# Clear custom config path (use default)
myagents config clear
```

### Use LangGraph Studio

```bash
# Start Studio (opens on http://localhost:2024)
myagents studio start

# Check Studio status
myagents studio status

# Stop Studio
myagents studio stop

# Restart Studio
myagents studio restart
```

For more detailed usage information, see [guides/usage.md](guides/usage.md).

---

## Troubleshooting

### Issue 1: Config File Not Found Error

**Symptom:**
```
❌ Configuration file not found

gcptoolkit configuration is required but missing.

Expected file: ~/.config/agent-gcptoolkit/config.yml
```

**Solution:**

1. Create the config file manually:
   ```bash
   mkdir -p ~/.config/agent-gcptoolkit
   nano ~/.config/agent-gcptoolkit/config.yml
   ```

2. Add the required configuration (see [Configuration File Structure](#configuration-file-structure))

3. Verify the file was created:
   ```bash
   ls -la ~/.config/agent-gcptoolkit/config.yml
   myagents config verify
   ```

### Issue 2: Invalid Configuration Error

**Symptom:**
```
✗ Configuration is invalid
  Config file: /home/user/.config/agent-gcptoolkit/config.yml

Errors found:
  - Missing required section: 'authentication'
  - Missing required section: 'gcp'
```

**Solution:**

1. Open your config file:
   ```bash
   nano ~/.config/agent-gcptoolkit/config.yml
   ```

2. Ensure it has both required sections:
   ```yaml
   authentication:
     type: service_account
     service_account_path: /path/to/service-account.json

   gcp:
     project_id: your-project-id
   ```

3. Verify the fix:
   ```bash
   myagents config verify
   ```

### Issue 3: Service Account File Not Found

**Symptom:**
```
✗ Configuration is invalid
Errors found:
  - Service account file not found: /path/to/service-account.json
```

**Solution:**

1. Verify the file exists:
   ```bash
   ls -la /path/to/service-account.json
   ```

2. If using application default credentials:
   ```bash
   # Re-authenticate
   gcloud auth application-default login

   # Update config to use correct path
   nano ~/.config/agent-gcptoolkit/config.yml
   ```

   Set path to:
   ```yaml
   service_account_path: ~/.config/gcloud/application_default_credentials.json
   ```

3. If using a service account key:
   - Download a new key from GCP Console
   - Save it to a known location
   - Update the path in your config file

### Issue 4: Secret Not Found in GCP

**Symptom:**
```
Error: Secret 'GEMINI_API_KEY' not found in GCP or env
```

**Solution:**

1. Check if the secret exists in Secret Manager:
   ```bash
   gcloud secrets list --project=your-project-id | grep GEMINI_API_KEY
   ```

2. If the secret doesn't exist, create it:
   ```bash
   # Get your Gemini API key from https://ai.google.dev/
   echo -n "your-gemini-api-key" | gcloud secrets create GEMINI_API_KEY \
     --data-file=- \
     --project=your-project-id
   ```

3. Verify the secret was created:
   ```bash
   gcloud secrets versions list GEMINI_API_KEY --project=your-project-id
   ```

4. Test access:
   ```bash
   myagents secrets get GEMINI_API_KEY
   ```

### Issue 5: Permission Denied Accessing Secrets

**Symptom:**
```
Error: Permission denied when accessing secret 'GEMINI_API_KEY'
```

**Solution:**

1. Verify your service account has the correct role:
   ```bash
   gcloud projects get-iam-policy your-project-id \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL"
   ```

2. Grant Secret Manager access:
   ```bash
   gcloud projects add-iam-policy-binding your-project-id \
     --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
     --role="roles/secretmanager.secretAccessor"
   ```

3. If using application default credentials, ensure you're authenticated:
   ```bash
   gcloud auth application-default login
   ```

### Issue 6: myagents Command Not Found

**Symptom:**
```
bash: myagents: command not found
```

**Solution:**

1. Ensure you installed the package:
   ```bash
   pip install -e .
   ```

2. Check if it's in your PATH:
   ```bash
   which myagents
   ```

3. If not found, try reinstalling:
   ```bash
   pip uninstall myagents
   pip install -e .
   ```

4. Restart your terminal and try again

### Issue 7: Studio Won't Start (Port in Use)

**Symptom:**
```
Error: Port 2024 is already in use
```

**Solution:**

1. Check if Studio is already running:
   ```bash
   myagents studio status
   ```

2. Stop the existing instance:
   ```bash
   myagents studio stop
   ```

3. If that fails, force stop:
   ```bash
   myagents studio stop --force
   ```

4. Find and kill the process manually:
   ```bash
   lsof -i :2024
   kill -9 <PID>
   ```

5. Start Studio again:
   ```bash
   myagents studio start
   ```

### Issue 8: Chat Fails After Running myagents setup

**Symptom:**

After running `myagents setup`, you see "Setup complete" but `myagents chat` still fails with config not found error.

**Explanation:**

The `myagents setup` command creates the Studio config (`~/.config/myagents/config.yml`) but NOT the gcptoolkit config (`~/.config/agent-gcptoolkit/config.yml`). These are different files serving different purposes.

**Solution:**

Create the gcptoolkit config manually following [Step 2: Create Configuration File Manually](#step-2-create-configuration-file-manually).

### Getting Additional Help

If you encounter issues not covered here:

1. Check the configuration:
   ```bash
   myagents config list
   myagents config verify
   ```

2. Check secret access:
   ```bash
   myagents secrets get GEMINI_API_KEY
   ```

3. Review the documentation:
   - [Configuration Guide](guides/configuration.md)
   - [Usage Guide](guides/usage.md)
   - [Architecture Overview](architecture/architecture.md)

4. Check the GitHub repository issues or contact your administrator

---

## Advanced Configuration

### Using a Custom Config Path

You can store your config file anywhere and point MyAgents to it:

```bash
# Set custom config path
myagents config set-path /path/to/my/custom/config.yml

# Verify it's being used
myagents config show

# Clear custom path (revert to default)
myagents config clear
```

### Using Multiple GCP Projects

You can override the project ID on a per-command basis:

```bash
# Get secret from different project
myagents secrets get MY_SECRET --project-id my-other-project
```

Or create separate config files for different projects:

```bash
# Create configs for different projects
/home/user/.config/agent-gcptoolkit/config-project-a.yml
/home/user/.config/agent-gcptoolkit/config-project-b.yml

# Switch between them
myagents config set-path ~/.config/agent-gcptoolkit/config-project-a.yml
myagents chat

myagents config set-path ~/.config/agent-gcptoolkit/config-project-b.yml
myagents chat
```

### Environment Variable Fallback

If GCP Secret Manager is unavailable, MyAgents will fall back to environment variables:

```bash
# Set secrets as environment variables
export GEMINI_API_KEY="your-api-key"
export LANGSMITH_API_KEY="your-langsmith-key"

# MyAgents will use these if GCP fetch fails
myagents chat
```

### Managing User Preferences

MyAgents supports user preferences for customization:

```bash
# Set a preference
myagents preferences set agent.default coding

# Get a preference
myagents preferences get agent.default

# List all preferences
myagents preferences list

# Delete a preference
myagents preferences delete agent.default

# Clear all preferences
myagents preferences clear
```

### LangGraph Studio Configuration

Studio settings are stored in `~/.config/myagents/config.yml`:

```yaml
server:
  host: 127.0.0.1
  port: 2024
  allow_blocking: true

runtime:
  pid_file: ~/.config/myagents/runtime/studio.pid
  log_dir: ~/.config/myagents/runtime/studio/logs
  checkpoint_dir: ~/.config/myagents/runtime/studio/checkpoints

langgraph:
  project_name: myagents-default
```

You can modify these settings to customize Studio behavior.

---

## Next Steps

Now that MyAgents is set up, you can:

1. **Start Using Agents**
   - [Usage Guide](guides/usage.md) - Learn how to use the coding and echo agents
   - [Configuration Guide](guides/configuration.md) - Advanced configuration options

2. **Learn More**
   - [Architecture Overview](architecture/architecture.md) - Understand how MyAgents works
   - [Workflows](architecture/workflows.md) - Detailed workflow documentation

3. **For Developers**
   - [Getting Started](guides/getting-started.md) - Developer setup and testing
   - [Packaging Guide](guides/packaging.md) - Build and deployment

---

**Last Updated:** 2025-12-01
**Version:** 1.0
