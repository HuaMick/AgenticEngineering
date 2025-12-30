#!/usr/bin/env python3
"""
Automated Dart↔Python NaCl Interoperability Test

This script:
1. Tests Python→Python (baseline sanity check)
2. Generates test vectors for Dart to decrypt (Python encrypts)
3. Provides template for Dart to encrypt back to Python

This validates cross-language compatibility critical for RemoteAgents.
"""

from nacl.public import PrivateKey, PublicKey, Box
import base64
import json

def test_python_baseline():
    """Baseline: Verify Python can encrypt and decrypt to itself."""
    print("=" * 70)
    print("STEP 1: Python Baseline Test (Python encrypts → Python decrypts)")
    print("=" * 70)

    alice_private = PrivateKey.generate()
    bob_private = PrivateKey.generate()

    # Alice encrypts to Bob
    box_alice_to_bob = Box(alice_private, bob_private.public_key)
    message = "Hello, World!"
    encrypted = box_alice_to_bob.encrypt(message.encode('utf-8'))

    print(f"Message: {message}")
    print(f"Ciphertext length: {len(encrypted)} bytes")

    # Bob decrypts from Alice
    box_bob_from_alice = Box(bob_private, alice_private.public_key)
    decrypted = box_bob_from_alice.decrypt(encrypted).decode('utf-8')

    print(f"Decrypted: {decrypted}")

    assert decrypted == message, "Python baseline failed!"
    print("✓ Python baseline PASSED\n")

    return True


def generate_python_to_dart_vectors():
    """Generate test vectors: Python encrypts, Dart should decrypt."""
    print("=" * 70)
    print("STEP 2: Generate Python→Dart Test Vectors")
    print("=" * 70)

    # Generate stable keys for this test run
    alice_private = PrivateKey.generate()
    bob_private = PrivateKey.generate()

    alice_public = alice_private.public_key
    bob_public = bob_private.public_key

    # Export keys
    alice_private_b64 = base64.b64encode(bytes(alice_private)).decode()
    alice_public_b64 = base64.b64encode(bytes(alice_public)).decode()
    bob_private_b64 = base64.b64encode(bytes(bob_private)).decode()
    bob_public_b64 = base64.b64encode(bytes(bob_public)).decode()

    print("\nGenerated Keys:")
    print(f"Alice Private: {alice_private_b64}")
    print(f"Alice Public:  {alice_public_b64}")
    print(f"Bob Private:   {bob_private_b64}")
    print(f"Bob Public:    {bob_public_b64}")
    print()

    # Test messages
    test_cases = [
        "Hello, World!",
        "Hello, 世界! 🌍",
        '{"type": "test", "data": 123}',
    ]

    # Alice encrypts to Bob
    box_alice_to_bob = Box(alice_private, bob_public)

    print("Test Vectors (Python encrypted, for Dart to decrypt):")
    print()

    dart_test_code = []
    dart_test_code.append("// Paste this into a Dart test file\n")
    dart_test_code.append("test('Python→Dart interop: Dart decrypts Python ciphertext', () {")
    dart_test_code.append(f"  final aliceKeys = KeyPair.fromBase64({{'privateKey': '{alice_private_b64}', 'publicKey': '{alice_public_b64}'}});")
    dart_test_code.append(f"  final bobKeys = KeyPair.fromBase64({{'privateKey': '{bob_private_b64}', 'publicKey': '{bob_public_b64}'}});")
    dart_test_code.append("")

    for i, message in enumerate(test_cases, 1):
        encrypted = box_alice_to_bob.encrypt(message.encode('utf-8'))
        ciphertext_b64 = base64.b64encode(encrypted).decode()

        print(f"Test Case {i}: {message}")
        print(f"  Ciphertext: {ciphertext_b64}")
        print(f"  Length: {len(encrypted)} bytes (nonce: 24, ciphertext+MAC: {len(encrypted)-24})")

        # Verify Python can decrypt its own encryption
        decrypted = box_alice_to_bob.decrypt(encrypted).decode('utf-8')
        assert decrypted == message
        print(f"  Python self-check: ✓")
        print()

        # Generate Dart test code
        dart_test_code.append(f"  // Test case {i}: {message}")
        dart_test_code.append(f"  final ciphertext{i} = '{ciphertext_b64}';")
        dart_test_code.append(f"  final decrypted{i} = NaClCrypto.decrypt(ciphertext{i}, bobKeys, aliceKeys);")
        dart_test_code.append(f"  expect(decrypted{i}, equals('{message}'));")
        dart_test_code.append("")

    dart_test_code.append("  print('All Python→Dart interop tests passed!');")
    dart_test_code.append("});")

    print("\n" + "=" * 70)
    print("DART TEST CODE (Copy-paste into test file)")
    print("=" * 70)
    print("\n".join(dart_test_code))
    print()

    # Save to file for easy access
    with open('/home/code/myagents/MyAgentsFrontend-core-crypto/test/core/crypto/python_vectors_for_dart.txt', 'w') as f:
        f.write("PYTHON-GENERATED TEST VECTORS FOR DART\n")
        f.write("=" * 70 + "\n\n")
        f.write("Keys:\n")
        f.write(f"Alice Private: {alice_private_b64}\n")
        f.write(f"Alice Public:  {alice_public_b64}\n")
        f.write(f"Bob Private:   {bob_private_b64}\n")
        f.write(f"Bob Public:    {bob_public_b64}\n\n")
        f.write("Test Vectors:\n")
        for i, message in enumerate(test_cases, 1):
            encrypted = box_alice_to_bob.encrypt(message.encode('utf-8'))
            ciphertext_b64 = base64.b64encode(encrypted).decode()
            f.write(f"\nTest {i}: {message}\n")
            f.write(f"Ciphertext: {ciphertext_b64}\n")
        f.write("\n" + "=" * 70 + "\n")
        f.write("DART TEST CODE:\n")
        f.write("=" * 70 + "\n")
        f.write("\n".join(dart_test_code))

    print("✓ Test vectors saved to: test/core/crypto/python_vectors_for_dart.txt\n")


def show_dart_to_python_template():
    """Show template for Dart to encrypt for Python to decrypt."""
    print("=" * 70)
    print("STEP 3: Dart→Python Test Template")
    print("=" * 70)
    print("""
To test Dart→Python direction:

1. Create a Dart test that outputs:
   - Alice/Bob keys (Base64)
   - Test messages
   - Ciphertext (Base64)

2. Run this Python script with the Dart output:

   Example Dart output format:
   ```
   ALICE_PRIVATE_B64="..."
   ALICE_PUBLIC_B64="..."
   BOB_PRIVATE_B64="..."
   BOB_PUBLIC_B64="..."
   MESSAGE="Hello, World!"
   CIPHERTEXT="..."
   ```

3. Python will decrypt and verify.

See verify_dart_encryption.py for a ready-to-use verification script.
""")


def main():
    """Run all interop tests."""
    print("\n" + "=" * 70)
    print("NaCl Cross-Language Interoperability Test")
    print("Dart (pinenacl) ↔ Python (PyNaCl)")
    print("=" * 70 + "\n")

    # Step 1: Baseline
    test_python_baseline()

    # Step 2: Generate Python→Dart vectors
    generate_python_to_dart_vectors()

    # Step 3: Show Dart→Python template
    show_dart_to_python_template()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("✓ Python baseline test passed")
    print("✓ Python→Dart test vectors generated")
    print("  → Next: Import vectors into Dart test and verify decryption")
    print()
    print("Files created:")
    print("  - test/core/crypto/python_vectors_for_dart.txt")
    print()
    print("Next steps:")
    print("  1. Copy Dart test code from above into interop_python_to_dart_test.dart")
    print("  2. Run: flutter test test/core/crypto/interop_python_to_dart_test.dart")
    print("  3. For Dart→Python: Run Dart test and paste output into verify_dart_encryption.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
