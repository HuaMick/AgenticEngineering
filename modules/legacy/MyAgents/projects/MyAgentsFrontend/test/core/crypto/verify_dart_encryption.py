#!/usr/bin/env python3
"""
PyNaCl verification script for Dart-encrypted messages.

This script validates cross-language interoperability between Dart (pinenacl)
and Python (PyNaCl) for E2E encryption.

Usage:
1. Run the Dart test first to generate test vectors
2. Copy the keys and ciphertext values into this script
3. Run this script to verify Python can decrypt Dart-encrypted messages
"""

from nacl.public import PrivateKey, PublicKey, Box
import base64
import sys

def verify_decryption(alice_private_b64, alice_public_b64, bob_private_b64, bob_public_b64, test_cases):
    """
    Verify that Python can decrypt Dart-encrypted messages.

    Args:
        alice_private_b64: Alice's private key (Base64)
        alice_public_b64: Alice's public key (Base64)
        bob_private_b64: Bob's private key (Base64)
        bob_public_b64: Bob's public key (Base64)
        test_cases: List of dicts with 'name', 'plaintext', 'ciphertext'

    Returns:
        True if all tests pass, False otherwise
    """
    print("=== PyNaCl Verification of Dart Encryption ===\n")

    # Import Alice's keys
    alice_private_bytes = base64.b64decode(alice_private_b64)
    alice_public_bytes = base64.b64decode(alice_public_b64)

    print(f"Alice Private Key length: {len(alice_private_bytes)} bytes")
    print(f"Alice Public Key length: {len(alice_public_bytes)} bytes")

    # Import Bob's keys
    bob_private_bytes = base64.b64decode(bob_private_b64)
    bob_public_bytes = base64.b64decode(bob_public_b64)

    print(f"Bob Private Key length: {len(bob_private_bytes)} bytes")
    print(f"Bob Public Key length: {len(bob_public_bytes)} bytes")
    print()

    # Reconstruct keys using PyNaCl
    alice_private = PrivateKey(alice_private_bytes)
    alice_public = PublicKey(alice_public_bytes)
    bob_private = PrivateKey(bob_private_bytes)
    bob_public = PublicKey(bob_public_bytes)

    # Verify public key derivation
    alice_derived_public = alice_private.public_key
    if bytes(alice_derived_public) != alice_public_bytes:
        print("ERROR: Alice's public key doesn't match derived key!")
        return False
    print("Alice's public key derivation: OK")

    bob_derived_public = bob_private.public_key
    if bytes(bob_derived_public) != bob_public_bytes:
        print("ERROR: Bob's public key doesn't match derived key!")
        return False
    print("Bob's public key derivation: OK")
    print()

    # Create Box as Bob (decrypt messages sent to Bob)
    # Bob's private key + Alice's public key
    box = Box(bob_private, alice_public)

    # Test each case
    all_passed = True
    for i, test_case in enumerate(test_cases):
        name = test_case['name']
        expected_plaintext = test_case['plaintext']
        ciphertext_b64 = test_case['ciphertext']

        print(f"Test Case {i+1}: {name}")
        print(f"Expected plaintext: {expected_plaintext}")

        try:
            # Decode ciphertext from Base64
            ciphertext_bytes = base64.b64decode(ciphertext_b64)
            print(f"Ciphertext length: {len(ciphertext_bytes)} bytes")

            # Parse format: nonce (24 bytes) || ciphertext+MAC
            nonce = ciphertext_bytes[:24]
            ciphertext_with_mac = ciphertext_bytes[24:]

            print(f"Nonce length: {len(nonce)} bytes")
            print(f"Ciphertext+MAC length: {len(ciphertext_with_mac)} bytes")

            # Decrypt using PyNaCl
            # PyNaCl expects the full encrypted message (nonce prepended to ciphertext)
            decrypted = box.decrypt(ciphertext_bytes)
            decrypted_text = decrypted.decode('utf-8')

            print(f"Decrypted plaintext: {decrypted_text}")

            # Verify match
            if decrypted_text == expected_plaintext:
                print("PASS: Plaintext matches!")
            else:
                print(f"FAIL: Plaintext mismatch!")
                print(f"  Expected: {expected_plaintext}")
                print(f"  Got: {decrypted_text}")
                all_passed = False

        except Exception as e:
            print(f"FAIL: Decryption failed with error: {e}")
            all_passed = False

            # Hex dump for debugging
            if 'ciphertext_bytes' in locals():
                print("Hex dump (first 48 bytes):")
                hex_dump = ' '.join(f'{b:02x}' for b in ciphertext_bytes[:48])
                print(hex_dump)

        print()

    return all_passed


def main():
    """
    Main function - paste test vectors from Dart output here
    """
    # PASTE VALUES FROM DART TEST OUTPUT BELOW
    # These are placeholder values - replace with actual output

    alice_private_b64 = "REPLACE_WITH_DART_OUTPUT"
    alice_public_b64 = "REPLACE_WITH_DART_OUTPUT"
    bob_private_b64 = "REPLACE_WITH_DART_OUTPUT"
    bob_public_b64 = "REPLACE_WITH_DART_OUTPUT"

    test_cases = [
        # PASTE TEST CASES FROM DART OUTPUT
        # Example format:
        # {"name": "Simple ASCII", "plaintext": "Hello, World!", "ciphertext": "REPLACE_WITH_DART_OUTPUT"},
    ]

    if alice_private_b64 == "REPLACE_WITH_DART_OUTPUT":
        print("ERROR: Please run the Dart test first and paste the output values into this script.")
        print("\nTo generate test vectors, run:")
        print("  cd /home/code/myagents/MyAgentsFrontend-core-crypto")
        print("  dart test test/core/crypto/interop_dart_to_python_test.dart")
        print("\nThen copy the 'COPY-PASTE FOR PYTHON' section into this script.")
        sys.exit(1)

    if not test_cases:
        print("ERROR: No test cases defined. Please paste test cases from Dart output.")
        sys.exit(1)

    # Run verification
    success = verify_decryption(
        alice_private_b64,
        alice_public_b64,
        bob_private_b64,
        bob_public_b64,
        test_cases
    )

    print("=" * 50)
    if success:
        print("ALL TESTS PASSED - Dart→Python interop verified!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED - Interop issues detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
