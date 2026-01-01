# MyAgents Main Project Makefile
# This Makefile provides a unified interface for navigation and tool management.

.PHONY: help project-worktree-info project-worktree-create \
        configure-goose install-goose status install-mcp \
        build-gcptoolkit install-gcptoolkit-global clean-gcptoolkit rebuild-gcptoolkit-global

# ============================================
# CONFIGURATION & ENVIRONMENT
# ============================================

# Default GCP paths based on Agent-GCPtoolkit configuration
CONFIG_FILE := /home/code/myagents/config/config.yml
SA_PATH := $(shell grep "service_account_path:" $(CONFIG_FILE) | awk '{print $$2}')
PROJECT_ID := $(shell grep "project_id:" $(CONFIG_FILE) | awk '{print $$2}')
LOCATION := australia-southeast1

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Goose Management:"
	@echo "  configure-goose    Run goose configure"
	@echo "  status             Check environment and tool configuration"
	@echo "  install-goose      Install/Update Goose CLI"
	@echo "  install-mcp        Install the MCP sub-agent server"
	@echo ""
	@echo "Worktree Management:"
	@echo "  project-worktree-info    Show environment diagnostics"
	@echo "  project-worktree-create  Create a new worktree (BRANCH=name)"
	@echo ""
	@echo "GCP Toolkit (myagents):"
	@echo "  build-gcptoolkit         Build agent-gcptoolkit wheel"
	@echo "  install-gcptoolkit-global Install myagents CLI globally"
	@echo "  rebuild-gcptoolkit-global Clean, build, and reinstall globally"

# ============================================
# GOOSE MANAGEMENT
# ============================================

status:
	@echo "=== Environment Status ==="
	@echo "GCP Project: $(PROJECT_ID)"
	@echo "Credentials: $(SA_PATH)"
	@echo "Goose Path:  $$(which goose || echo 'Not installed')"
	@echo "MyAgents:    $$(which myagents || echo 'Not installed')"
	@echo ""
	@echo "To use Goose, run: source config/env.env && goose session"

install-goose:
	@echo "=== Installing Goose ==="
	@curl -fsSL https://github.com/block/goose/releases/download/stable/download_cli.sh | bash

configure-goose:
	@echo "=== Configuring Goose ==="
	@echo "Note: Ensure you have sourced your environment: source config/env.env"
	@goose configure

install-mcp:
	@echo "=== Installing Goose MCP Subagents server ==="
	@npm install -g @pc-style/goose-mcp

# ============================================
# WORKTREE MANAGEMENT
# ============================================

project-worktree-info:
	@echo "=== Environment Diagnostics ==="
	@echo "Current directory: $$(pwd)"
	@echo ""
	@echo "=== Git Worktrees ==="
	@git -C /home/code/myagents/MyAgents worktree list
	@echo ""
	@echo "=== Directory Structure ==="
	@ls -la /home/code/myagents/
	@echo ""
	@echo "=== MyAgents Worktree Contents ==="
	@ls -la /home/code/myagents/MyAgents/

project-worktree-create:
	@if [ -z "$(BRANCH)" ]; then \
		echo "Error: BRANCH variable required. Usage: make project-worktree-create BRANCH=feature-name"; \
		exit 1; \
	fi
	@git -C /home/code/myagents/MyAgents worktree add -b $(BRANCH) /home/code/myagents/$(BRANCH)
	@echo "Worktree created at: /home/code/myagents/$(BRANCH)"
	@ls -la /home/code/myagents/$(BRANCH)

# ============================================
# GCP TOOLKIT (MYAGENTS)
# ============================================

build-gcptoolkit:
	@echo "=== Building Agent-GCPtoolkit ==="
	cd /home/code/myagents/Agent-GCPtoolkit && uv build --out-dir build-artifacts/dist

install-gcptoolkit-global:
	@echo "=== Installing Agent-GCPtoolkit globally with UV ==="
	cd /home/code/myagents/Agent-GCPtoolkit && ./scripts/install-global.sh

clean-gcptoolkit:
	@echo "=== Cleaning Agent-GCPtoolkit ==="
	rm -rf /home/code/myagents/Agent-GCPtoolkit/build-artifacts/dist/* /home/code/myagents/Agent-GCPtoolkit/build-artifacts/build/* /home/code/myagents/Agent-GCPtoolkit/*.egg-info
	find /home/code/myagents/Agent-GCPtoolkit -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

rebuild-gcptoolkit-global: clean-gcptoolkit build-gcptoolkit install-gcptoolkit-global
	@echo "=== Agent-GCPtoolkit rebuilt and installed (global) ==="

check-myagents:
	@echo "=== Checking myagents CLI ==="
	@which myagents || (echo "Error: myagents not in PATH. Install with: make install-gcptoolkit-global" && exit 1)
	@myagents version
	@echo "✓ myagents CLI is accessible"
