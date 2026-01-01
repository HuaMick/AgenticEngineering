# Cloud Build Triggers Reference

> **Status**: ✅ Triggers are already configured and active

## Current Triggers

- `myagentsfrontend-pr` - PR validation trigger
- `myagentsfrontend-main` - Main branch build trigger

## Configuration Details

- **GCP Project**: `myagents-475112`
- **Region**: `australia-southeast1`
- **Repository Path**: `projects/myagents-475112/locations/australia-southeast1/connections/MyAgents/repositories/HuaMick-myagentsfrontend`
- **Connection**: `MyAgents`

## Trigger 1: PR Validation

```bash
gcloud builds triggers create github \
  --name="myagentsfrontend-pr" \
  --description="PR validation for MyAgentsFrontend (lint + tests)" \
  --repository="projects/myagents-475112/locations/australia-southeast1/connections/MyAgents/repositories/HuaMick-myagentsfrontend" \
  --pull-request-pattern="^main$" \
  --build-config="MyAgentsFrontend-staging/cloudbuild-pr.yaml" \
  --included-files="MyAgentsFrontend-staging/**" \
  --region="australia-southeast1"
```

## Trigger 2: Main Branch Build

```bash
gcloud builds triggers create github \
  --name="myagentsfrontend-main" \
  --description="Main branch build for MyAgentsFrontend (lint + tests + web build)" \
  --repository="projects/myagents-475112/locations/australia-southeast1/connections/MyAgents/repositories/HuaMick-myagentsfrontend" \
  --branch-pattern="^main$" \
  --build-config="MyAgentsFrontend-staging/cloudbuild.yaml" \
  --included-files="MyAgentsFrontend-staging/**" \
  --region="australia-southeast1"
```

## Alternative: Create via Console

1. Go to Cloud Build > Triggers
2. Click "Create Trigger"
3. Configure:
   - **Name**: myagentsfrontend-pr (or myagentsfrontend-main)
   - **Event**: Pull request (or Push to branch)
   - **Source**: 2nd Gen > HuaMick/myagents-frontend
   - **Branch**: ^main$
   - **Included files**: MyAgentsFrontend-staging/**
   - **Configuration**: Cloud Build configuration file
   - **Location**: MyAgentsFrontend-staging/cloudbuild-pr.yaml (or cloudbuild.yaml)

## Path Filtering

The `--included-files` ensures triggers only fire for MyAgentsFrontend changes:
- `MyAgentsFrontend-staging/**` - Any file in the frontend directory

This prevents unnecessary builds when only backend (MyAgents) changes.

## Verification

View configured triggers:
```bash
gcloud builds triggers list --region=australia-southeast1 --filter="name:myagentsfrontend-*"
```

## See Also

- [CI_CD.md](CI_CD.md) - Complete CI/CD documentation
- [README.md](README.md) - Project overview
