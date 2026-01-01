#!/usr/bin/env python3
"""
Manual test for Dart→Python interoperability.

This script allows manual testing by accepting test vectors from Dart output.
"""

from nacl.public import PrivateKey, PublicKey, Box
import base64
import sys

def test_known_vectors():
    """
    Test with hardcoded vectors if available, or prompt for manual input.
    """
    print("=== Dart→Python Interop Manual Test ===\n")
    print("This script will verify PyNaCl can decrypt Dart-encrypted messages.")
    print("\nTo generate test vectors:")
    print("1. Run: dart run test/core/crypto/run_interop_test.dart")
    print("2. Copy the output from 'COPY-PASTE FOR PYTHON' section")
    print("3. Paste below or hardcode into this script\n")

    # Example test - you would replace these with actual values from Dart
    # For now, let's demonstrate the format

    # Ask user if they want to test with manual input
    mode = input("Choose mode:\n1. Manual input (paste from Dart output)\n2. Quick self-test (Python-only)\n\nEnter choice (1 or 2): ").strip()

    if mode == "2":
        # Python self-test
        print("\n=== Python Self-Test ===")
        alice_private = PrivateKey.generate()
        bob_private = PrivateKey.generate()

        alice_public = alice_private.public_key
        bob_public = bob_private.public_key

        print(f"Alice Private: {base64.b64encode(bytes(alice_private)).decode()}")
        print(f"Alice Public: {base64.b64encode(bytes(alice_public)).decode()}")
        print(f"Bob Private: {base64.b64encode(bytes(bob_private)).decode()}")
        print(f"Bob Public: {base64.b64encode(bytes(bob_public)).decode()}")
        print()

        # Alice encrypts to Bob
        box_alice = Box(alice_private, bob_public)
        message = "Hello, World!"
        encrypted = box_alice.encrypt(message.encode('utf-8'))
        ciphertext_b64 = base64.b64encode(encrypted).decode()

        print(f"Message: {message}")
        print(f"Ciphertext (Base64): {ciphertext_b64}")
        print(f"Ciphertext length: {len(encrypted)} bytes")
        print()

        # Bob decrypts
        box_bob = Box(bob_private, alice_public)
        decrypted = box_bob.decrypt(encrypted)
        decrypted_text = decrypted.decode('utf-8')

        print(f"Decrypted: {decrypted_text}")
        print(f"Match: {decrypted_text == message}")
        print("\nPython self-test PASSED - PyNaCl is working correctly")
        print("\nNow test with Dart by running: dart run test/core/crypto/run_interop_test.dart")

    elif mode == "1":
        print("\nPaste Alice's private key (Base64):")
        alice_private_b64 = input().strip()
        print("Paste Alice's public key (Base64):")
        alice_public_b64 = input().strip()
        print("Paste Bob's private key (Base64):")
        bob_private_b64 = input().strip()
        print("Paste Bob's public key (Base64):")
        bob_public_b64 = input().strip()
        print("Paste ciphertext (Base64):")
        ciphertext_b64 = input().strip()
        print("Paste expected plaintext:")
        expected_plaintext = input().strip()

        # Verify
        try:
            alice_private = PrivateKey(base64.b64decode(alice_private_b64))
            alice_public = PublicKey(base64.b64decode(alice_public_b64))
            bob_private = PrivateKey(base64.b64decode(bob_private_b64))
            bob_public = PublicKey(base64.b64decode(bob_public_b64))

            # Bob decrypts message from Alice
            box = Box(bob_private, alice_public)
            ciphertext_bytes = base64.b64decode(ciphertext_b64)

            print(f"\nCiphertext length: {len(ciphertext_bytes)} bytes")
            print(f"Nonce (24 bytes): {base64.b64encode(ciphertext_bytes[:24]).decode()}")
            print(f"Ciphertext+MAC: {len(ciphertext_bytes) - 24} bytes")

            decrypted = box.decrypt(ciphertext_bytes)
            decrypted_text = decrypted.decode('utf-8')

            print(f"\nDecrypted: {decrypted_text}")
            print(f"Expected: {expected_plaintext}")

            if decrypted_text == expected_plaintext:
                print("\nSUCCESS: Dart→Python interop VERIFIED!")
            else:
                print("\nFAILURE: Plaintext mismatch!")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    test_known_vectors()
