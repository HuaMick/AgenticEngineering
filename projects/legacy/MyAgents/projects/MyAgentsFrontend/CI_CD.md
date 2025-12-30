# CI/CD Setup for MyAgentsFrontend

## Status

✅ **Triggers Configured**: Both PR and main branch triggers are active
- `myagentsfrontend-pr` - PR validation (lint + tests)
- `myagentsfrontend-main` - Main branch build (lint + tests + coverage + web build)

## Pipeline Overview

| Trigger | Config | Machine | Steps |
|---------|--------|---------|-------|
| PR to main | `cloudbuild-pr.yaml` | E2_MEDIUM (free tier) | Lint → Tests |
| Push to main | `cloudbuild.yaml` | E2_HIGHCPU_8 | Lint → Tests → Coverage → Web Build |

## Repository Details

- **GCP Project**: `myagents-475112`
- **Region**: `australia-southeast1`
- **Repository Path**: `projects/myagents-475112/locations/australia-southeast1/connections/MyAgents/repositories/HuaMick-myagentsfrontend`
- **Connection**: `MyAgents`

## Local Testing

Test the CI pipeline locally before pushing:

```bash
# Build the CI Docker image
cd /home/code/myagents
docker build -f MyAgentsFrontend-cicd/Dockerfile.test \
  --build-arg WORKTREE_NAME=MyAgentsFrontend-cicd \
  -t myagentsfrontend-test:local .

# Run tests
docker run --rm myagentsfrontend-test:local flutter test

# Run analyzer
docker run --rm myagentsfrontend-test:local flutter analyze --no-fatal-infos
```

## Monitoring

- **Triggers**: https://console.cloud.google.com/cloud-build/triggers?project=myagents-475112
- **Build History**: https://console.cloud.google.com/cloud-build/builds?project=myagents-475112
- **Coverage Reports**: `gs://myagents-475112-coverage/frontend/`

## Files

- `Dockerfile.test` - Multi-stage Flutter Docker image for CI
- `cloudbuild-pr.yaml` - PR validation pipeline
- `cloudbuild.yaml` - Main branch comprehensive pipeline
- `TRIGGERS.md` - Trigger configuration reference

## Troubleshooting

### View Trigger Details
```bash
gcloud builds triggers list --region=australia-southeast1 --filter="name:myagentsfrontend-*"
```

### Manual Build Test
```bash
gcloud builds submit --config=MyAgentsFrontend-staging/cloudbuild-pr.yaml \
  --substitutions=_WORKTREE_NAME=MyAgentsFrontend-cicd,_IMAGE_NAME=myagentsfrontend-test .
```

### Check Build Logs
```bash
gcloud builds list --region=australia-southeast1 --limit=10
```

