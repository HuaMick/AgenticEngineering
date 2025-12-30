# Google Artifact Registry Setup

This document provides comprehensive instructions for setting up and using Google Artifact Registry for MyAgents Python packages.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Registry Configuration](#registry-configuration)
- [Authentication Setup](#authentication-setup)
- [Deployment Scripts](#deployment-scripts)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

## Overview

MyAgents uses Google Artifact Registry to host Python packages for both production and testing environments. This enables:

- Private package distribution
- Version control and management
- Integration with Google Cloud Platform
- Secure authentication via service accounts

### Available Registries

| Registry Name | Environment | Location | Purpose |
|--------------|-------------|----------|---------|
| `myagents-python` | Production | us-central1 | Stable package releases |
| `myagents-python-test` | Testing | us-central1 | Development and testing |

## Prerequisites

Before using the artifact registry, ensure you have:

1. **Google Cloud SDK (gcloud)** installed and configured
   ```bash
   gcloud --version
   ```

2. **UV package manager** installed
   ```bash
   uv --version
   ```

3. **GCP Service Account** with appropriate permissions:
   - `roles/artifactregistry.writer` (for uploading packages)
   - `roles/artifactregistry.reader` (for downloading packages)

4. **Active GCP Project** configured
   ```bash
   gcloud config set project myagents-475112
   ```

## Registry Configuration

### Creating a New Registry

To create a new artifact registry:

```bash
gcloud artifacts repositories create REGISTRY_NAME \
  --repository-format=python \
  --location=us-central1 \
  --description="Description of the registry"
```

Example:
```bash
gcloud artifacts repositories create myagents-python \
  --repository-format=python \
  --location=us-central1 \
  --description="MyAgents Python packages - PRODUCTION"
```

### Listing Existing Registries

```bash
gcloud artifacts repositories list --location=us-central1
```

### Verifying Registry Access

```bash
gcloud artifacts repositories describe myagents-python --location=us-central1
```

## Authentication Setup

### 1. Install Authentication Helper

The authentication helper (`keyrings.google-artifactregistry-auth`) enables pip to authenticate with Artifact Registry automatically.

Install globally:
```bash
uv pip install --user --break-system-packages keyrings.google-artifactregistry-auth
```

Or use pipx (if available):
```bash
pipx install keyrings.google-artifactregistry-auth --include-deps
```

### 2. Configure pip

Create or update `~/.config/pip/pip.conf`:

```ini
[global]
extra-index-url = https://us-central1-python.pkg.dev/myagents-475112/myagents-python/simple/
```

This allows pip to find packages in both PyPI and your private registry.

### 3. Authenticate with GCP

Ensure your gcloud credentials are current:

```bash
gcloud auth application-default login
```

For service accounts:
```bash
gcloud auth activate-service-account --key-file=/path/to/key.json
```

## Deployment Scripts

MyAgents provides three deployment scripts for publishing packages to Artifact Registry:

### Main Deployment Script

**Location:** `scripts/deploy-to-registry.sh`

**Purpose:** Generic script for deploying any Python package to Artifact Registry.

**Usage:**
```bash
./scripts/deploy-to-registry.sh REGISTRY_NAME PACKAGE_DIR PROJECT_ID
```

**Parameters:**
- `REGISTRY_NAME`: Name of the target registry (e.g., `myagents-python`)
- `PACKAGE_DIR`: Absolute path to the package directory
- `PROJECT_ID`: GCP project ID (e.g., `myagents-475112`)

**Example:**
```bash
./scripts/deploy-to-registry.sh \
  myagents-python \
  /home/code/myagents/MyAgents-packaging-001 \
  myagents-475112
```

**Features:**
- Validates all parameters and prerequisites
- Cleans previous build artifacts
- Builds package using `uv build`
- Uploads to Artifact Registry
- Validates successful upload
- Provides detailed logging with color-coded output

### Package-Specific Wrapper Scripts

#### Deploy Agent-GCPtoolkit

**Location:** `scripts/deploy-gcptoolkit.sh`

**Usage:**
```bash
./scripts/deploy-gcptoolkit.sh
```

Pre-configured with:
- Registry: `myagents-python`
- Package: `/home/code/myagents/Agent-GCPtoolkit`
- Project: `myagents-475112`

#### Deploy MyAgents

**Location:** `scripts/deploy-myagents.sh`

**Usage:**
```bash
./scripts/deploy-myagents.sh
```

Pre-configured with:
- Registry: `myagents-python`
- Package: `/home/code/myagents/MyAgents-packaging-001`
- Project: `myagents-475112`

### Script Workflow

The deployment scripts follow this workflow:

1. **Validation Phase**
   - Check all required parameters
   - Verify required tools (gcloud, uv) are installed
   - Validate package directory exists
   - Verify pyproject.toml is present

2. **Build Phase**
   - Extract package name and version from pyproject.toml
   - Clean previous build artifacts
   - Build package with `uv build --out-dir dist/`
   - Verify build artifacts were created

3. **Upload Phase**
   - Configure gcloud project
   - Verify target registry exists
   - Upload all artifacts from dist/ directory
   - Validate upload success

4. **Verification Phase**
   - Check package appears in registry
   - List available versions
   - Display installation instructions

## Usage Examples

### Publishing a New Version

1. **Update version in pyproject.toml**
   ```toml
   [project]
   name = "myagents"
   version = "0.2.0"  # Increment version
   ```

2. **Deploy to production registry**
   ```bash
   ./scripts/deploy-myagents.sh
   ```

3. **Verify deployment**
   ```bash
   gcloud artifacts packages list \
     --repository=myagents-python \
     --location=us-central1
   ```

### Installing from Registry

Once packages are published, install them using pip:

```bash
# Install latest version
uv pip install myagents

# Install specific version
uv pip install myagents==0.2.0

# Install from test registry (override in pip.conf)
uv pip install --extra-index-url \
  https://us-central1-python.pkg.dev/myagents-475112/myagents-python-test/simple/ \
  myagents
```

### Listing Package Versions

```bash
gcloud artifacts versions list \
  --package=myagents \
  --repository=myagents-python \
  --location=us-central1
```

### Viewing Package Details

```bash
gcloud artifacts packages describe myagents \
  --repository=myagents-python \
  --location=us-central1
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Authentication Failures

**Symptom:**
```
ERROR: Could not authenticate to repository
```

**Solutions:**
- Verify keyring helper is installed:
  ```bash
  pip show keyrings.google-artifactregistry-auth
  ```
- Re-authenticate with gcloud:
  ```bash
  gcloud auth application-default login
  ```
- Check service account permissions

#### 2. Package Not Found After Upload

**Symptom:**
Package upload succeeds but cannot be installed

**Solutions:**
- Wait a few moments (propagation delay)
- Verify pip.conf has correct registry URL
- Check package name matches exactly (case-sensitive)
- Clear pip cache:
  ```bash
  pip cache purge
  ```

#### 3. Build Failures

**Symptom:**
```
ERROR: Package build failed
```

**Solutions:**
- Verify pyproject.toml is valid
- Check all dependencies are available
- Clean build artifacts and retry:
  ```bash
  rm -rf dist/ build/ *.egg-info
  ```
- Build manually to see detailed errors:
  ```bash
  uv build --out-dir dist/
  ```

#### 4. Permission Denied

**Symptom:**
```
ERROR: Permission denied when uploading to registry
```

**Solutions:**
- Verify service account has `artifactregistry.writer` role
- Check project ID is correct
- Ensure registry exists in specified location

#### 5. Registry Does Not Exist

**Symptom:**
```
ERROR: Repository not found
```

**Solutions:**
- Verify registry name and location:
  ```bash
  gcloud artifacts repositories list --location=us-central1
  ```
- Create registry if missing (see [Registry Configuration](#registry-configuration))

### Getting Help

For additional troubleshooting:

1. **Check gcloud logs:**
   ```bash
   gcloud artifacts operations list \
     --location=us-central1 \
     --limit=10
   ```

2. **View package upload history:**
   ```bash
   gcloud artifacts versions list \
     --package=PACKAGE_NAME \
     --repository=myagents-python \
     --location=us-central1
   ```

3. **Test registry connectivity:**
   ```bash
   gcloud artifacts repositories describe myagents-python \
     --location=us-central1
   ```

4. **Validate pip configuration:**
   ```bash
   pip config list -v
   ```

## Best Practices

1. **Version Management**
   - Always increment version in pyproject.toml before deploying
   - Use semantic versioning (MAJOR.MINOR.PATCH)
   - Tag releases in git matching package versions

2. **Testing**
   - Test packages in `myagents-python-test` registry first
   - Promote to production registry only after validation
   - Use virtual environments for testing installations

3. **Security**
   - Rotate service account keys regularly
   - Use least-privilege access (reader vs writer)
   - Never commit credentials to git

4. **Documentation**
   - Update CHANGELOG.md for each version
   - Document breaking changes clearly
   - Include migration guides for major versions

## Additional Resources

- [Google Artifact Registry Documentation](https://cloud.google.com/artifact-registry/docs)
- [Python Package Publishing Guide](https://packaging.python.org/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/)
- [UV Documentation](https://github.com/astral-sh/uv)
- [pip Configuration](https://pip.pypa.io/en/stable/topics/configuration/)

## Support

For issues specific to MyAgents packages:
- Check existing documentation in `docs/`
- Review `guides/packaging.md` for package development workflow
- Consult `architecture/workflows.md` for CI/CD integration
