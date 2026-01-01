#!/bin/bash
# MyAgentsFrontend CI/CD Trigger Setup Script
# Run this after authenticating with: gcloud auth login

set -e  # Exit on error

PROJECT_ID="myagents-475112"
REPO_OWNER="HuaMick"
REPO_NAME="myagents-frontend"
REGION="global"

echo "=========================================="
echo "MyAgentsFrontend CI/CD Setup"
echo "=========================================="
echo ""

# Check authentication
echo "Step 1: Checking authentication..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ ERROR: No active GCP account found."
    echo "Please run: gcloud auth login"
    exit 1
fi
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
echo "✅ Authenticated as: $ACTIVE_ACCOUNT"
echo ""

# Set project
echo "Step 2: Setting GCP project..."
gcloud config set project $PROJECT_ID
echo "✅ Project set to: $PROJECT_ID"
echo ""

# Enable APIs
echo "Step 3: Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable containerregistry.googleapis.com --project=$PROJECT_ID
gcloud services enable storage-component.googleapis.com --project=$PROJECT_ID
echo "✅ APIs enabled"
echo ""

# Check GitHub connection
echo "Step 4: Checking GitHub connection..."
CONNECTIONS=$(gcloud builds connections list --region=$REGION --format="value(name)" 2>/dev/null || echo "")
if [ -z "$CONNECTIONS" ]; then
    echo "⚠️  WARNING: No GitHub connections found."
    echo "You may need to create a GitHub connection first."
    echo "Run: gcloud builds connections create github --region=$REGION --name=myagents-github --repo-name=$REPO_NAME --repo-owner=$REPO_OWNER"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Found GitHub connections:"
    gcloud builds connections list --region=$REGION --format="table(name,githubConfig.repository)"
fi
echo ""

# Check if triggers already exist
echo "Step 5: Checking existing triggers..."
EXISTING_TRIGGERS=$(gcloud builds triggers list --region=$REGION --format="value(name)" 2>/dev/null || echo "")

if echo "$EXISTING_TRIGGERS" | grep -q "myagentsfrontend-pr"; then
    echo "⚠️  Trigger 'myagentsfrontend-pr' already exists"
    read -p "Delete and recreate? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud builds triggers delete myagentsfrontend-pr --region=$REGION --quiet
        echo "✅ Deleted existing PR trigger"
    else
        echo "⏭️  Skipping PR trigger creation"
        SKIP_PR=true
    fi
fi

if echo "$EXISTING_TRIGGERS" | grep -q "myagentsfrontend-main"; then
    echo "⚠️  Trigger 'myagentsfrontend-main' already exists"
    read -p "Delete and recreate? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud builds triggers delete myagentsfrontend-main --region=$REGION --quiet
        echo "✅ Deleted existing main trigger"
    else
        echo "⏭️  Skipping main trigger creation"
        SKIP_MAIN=true
    fi
fi
echo ""

# Create PR trigger
if [ "$SKIP_PR" != "true" ]; then
    echo "Step 6: Creating PR validation trigger..."
    gcloud builds triggers create github \
        --name="myagentsfrontend-pr" \
        --description="PR validation for MyAgentsFrontend (lint + tests)" \
        --repo-name="$REPO_NAME" \
        --repo-owner="$REPO_OWNER" \
        --pull-request-pattern="^main$" \
        --build-config="MyAgentsFrontend-staging/cloudbuild-pr.yaml" \
        --included-files="MyAgentsFrontend-staging/**" \
        --region="$REGION"
    echo "✅ PR trigger created"
    echo ""
fi

# Create main trigger
if [ "$SKIP_MAIN" != "true" ]; then
    echo "Step 7: Creating main branch trigger..."
    gcloud builds triggers create github \
        --name="myagentsfrontend-main" \
        --description="Main branch build for MyAgentsFrontend (lint + tests + web build)" \
        --repo-name="$REPO_NAME" \
        --repo-owner="$REPO_OWNER" \
        --branch-pattern="^main$" \
        --build-config="MyAgentsFrontend-staging/cloudbuild.yaml" \
        --included-files="MyAgentsFrontend-staging/**" \
        --region="$REGION"
    echo "✅ Main trigger created"
    echo ""
fi

# Verify triggers
echo "Step 8: Verifying triggers..."
echo ""
echo "Created triggers:"
gcloud builds triggers list --region=$REGION --filter="name:myagentsfrontend-*" --format="table(name,github.pullRequest.pattern,github.push.branch,filename)"
echo ""

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Create a test PR to verify the PR trigger works"
echo "2. Check build status: https://console.cloud.google.com/cloud-build/triggers?project=$PROJECT_ID"
echo "3. Monitor builds: https://console.cloud.google.com/cloud-build/builds?project=$PROJECT_ID"
echo ""

