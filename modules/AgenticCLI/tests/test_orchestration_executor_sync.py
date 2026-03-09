"""Orchestration executor sync tests.

All MMD-based tests (parse_mmd_routing PHASES formats, reconcile_mmd_status,
_find_next_pending_phase) were removed when the deprecated MMD methods were
deleted from OrchestrationWorkflow and ExecutionRunner in T5_1/T5_2.

Phase routing and status are now managed exclusively through TinyDB.
"""
