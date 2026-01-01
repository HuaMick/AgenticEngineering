#!/usr/bin/env python3
"""Standalone validation script for test vectors.

This script validates test vectors without requiring pytest.
Useful for quick validation during development.
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from agent_remote.shared.protocol.base import deserialize_message
from agent_remote.shared.protocol.terminal_messages import (
    TerminalOutput,
    TerminalInput,
    TerminalResize,
    TerminalClose,
)
from agent_remote.shared.protocol.session_messages import (
    SessionCreate,
    SessionCreated,
    SessionPair,
    SessionPaired,
    SessionClose,
)
from agent_remote.shared.protocol.relay_messages import (
    EncryptedBlob,
    Ping,
    Pong,
    Error,
)


def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r') as f:
        return json.load(f)


def test_valid_examples(vectors):
    """Test all valid examples can be deserialized."""
    print("\nTesting valid examples...")
    valid = vectors["valid_examples"]
    passed = 0
    failed = 0

    for name, vector in valid.items():
        try:
            json_str = json.dumps(vector["json"])
            msg = deserialize_message(json_str)
            print(f"  ✓ {name}: {type(msg).__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    return passed, failed


def test_invalid_examples(vectors):
    """Test all invalid examples fail validation."""
    print("\nTesting invalid examples (should fail)...")
    invalid = vectors["invalid_examples"]
    passed = 0
    failed = 0

    for name, vector in invalid.items():
        try:
            json_str = json.dumps(vector["json"])
            msg = deserialize_message(json_str)
            print(f"  ✗ {name}: Should have failed but didn't!")
            failed += 1
        except Exception as e:
            print(f"  ✓ {name}: Correctly failed with: {type(e).__name__}")
            passed += 1

    return passed, failed


def test_edge_cases(vectors):
    """Test edge cases."""
    print("\nTesting edge cases...")
    edges = vectors["edge_cases"]
    passed = 0
    failed = 0

    for name, vector in edges.items():
        try:
            json_str = json.dumps(vector["json"])
            msg = deserialize_message(json_str)
            print(f"  ✓ {name}: {type(msg).__name__}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    return passed, failed


def test_roundtrip(vectors):
    """Test serialization roundtrip."""
    print("\nTesting serialization roundtrip...")
    examples = vectors["serialization_roundtrip"]["examples"]
    passed = 0
    failed = 0

    for example in examples:
        try:
            json_str = json.dumps(example["json"])
            msg = deserialize_message(json_str)

            # Re-serialize
            reserialized = msg.to_json()
            msg2 = deserialize_message(reserialized)

            # Basic check
            assert msg.type == msg2.type
            print(f"  ✓ {example['message_type']}: Roundtrip successful")
            passed += 1
        except Exception as e:
            print(f"  ✗ {example['message_type']}: {e}")
            failed += 1

    return passed, failed


def main():
    """Main validation function."""
    print("=" * 70)
    print("Test Vector Validation")
    print("=" * 70)

    fixtures_dir = Path(__file__).parent / "fixtures"

    # Load protocol vectors
    protocol_vectors_file = fixtures_dir / "protocol_vectors.json"
    print(f"\nLoading: {protocol_vectors_file}")
    protocol_vectors = load_json(protocol_vectors_file)

    total_passed = 0
    total_failed = 0

    # Run tests
    p, f = test_valid_examples(protocol_vectors)
    total_passed += p
    total_failed += f

    p, f = test_invalid_examples(protocol_vectors)
    total_passed += p
    total_failed += f

    p, f = test_edge_cases(protocol_vectors)
    total_passed += p
    total_failed += f

    p, f = test_roundtrip(protocol_vectors)
    total_passed += p
    total_failed += f

    # Summary
    print("\n" + "=" * 70)
    print(f"Summary: {total_passed} passed, {total_failed} failed")
    print("=" * 70)

    if total_failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All test vectors validated successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
