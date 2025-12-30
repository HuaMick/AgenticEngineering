"""End-to-end test suite for build/deploy cycles and packaging workflows.

This package contains end-to-end tests that validate complete user workflows
from source to deployed CLI, testing the full packaging lifecycle.

Test modules:
- test_myagents_build_deploy_e2e.py: Complete build/deploy cycle tests
- test_gcptoolkit_cli_e2e.py: GCPToolkit CLI tests (build, update, rebuild)
- test_myagents_cli_e2e.py: MyAgents CLI tests (update, rebuild)
- test_installation_script_e2e.py: Installation script validation
- test_makefile_e2e.py: Makefile target tests
- test_self_update_e2e.py: Self-update mechanism tests
"""
