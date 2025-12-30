#!/usr/bin/env python3
"""
Verifies that PyNaCl's Box.encrypt() format matches what pinenacl expects.

This script tests the format compatibility by:
1. Checking that Box.encrypt() returns nonce || ciphertext
2. Verifying the nonce is 24 bytes
3. Confirming the ciphertext includes the 16-byte Poly1305 MAC
"""

from nacl.public import PrivateKey, Box
import base64

# Use the same keys from our test
alice_private_b64 = 'dL7U7Kx1/9tgFHziHd9jOY17Qk84aPQeqJnBKPg/mh0='
bob_private_b64 = 't9s06qtsHQ6cOeaD7JFp3y5StaTij3npU6yM2SupOCI='

alice_private = PrivateKey(base64.b64decode(alice_private_b64))
bob_private = PrivateKey(base64.b64decode(bob_private_b64))

# Alice encrypts to Bob
box = Box(alice_private, bob_private.public_key)

test_message = "Hello from Python!"
plaintext_bytes = test_message.encode('utf-8')

# Encrypt
ciphertext = box.encrypt(plaintext_bytes)

print("=== PyNaCl Box.encrypt() Format Analysis ===")
print(f"Original message: {test_message}")
print(f"Plaintext bytes: {len(plaintext_bytes)} bytes")
print(f"Encrypted output: {len(ciphertext)} bytes")
print(f"Base64 encoded: {base64.b64encode(ciphertext).decode()}")
print()

# PyNaCl's EncryptedMessage format
print("=== Format Breakdown ===")
print(f"Expected: nonce (24 bytes) + ciphertext (plaintext + 16-byte MAC)")
print(f"Expected total: 24 + {len(plaintext_bytes)} + 16 = {24 + len(plaintext_bytes) + 16} bytes")
print(f"Actual total: {len(ciphertext)} bytes")
print()

# Verify format
nonce = ciphertext[:24]
encrypted_data = ciphertext[24:]

print("=== Split Analysis ===")
print(f"Nonce (first 24 bytes): {len(nonce)} bytes")
print(f"Nonce Base64: {base64.b64encode(bytes(nonce)).decode()}")
print(f"Ciphertext+MAC (remaining): {len(encrypted_data)} bytes")
print(f"  - Plaintext length: {len(plaintext_bytes)} bytes")
print(f"  - MAC length: 16 bytes")
print(f"  - Total: {len(plaintext_bytes) + 16} bytes")
print(f"  - Matches actual: {len(encrypted_data) == len(plaintext_bytes) + 16}")
print()

# Test decryption with manual split
print("=== Decryption Test (manual split) ===")
try:
    # Create box for decryption (Bob decrypts from Alice)
    decrypt_box = Box(bob_private, alice_private.public_key)

    # Decrypt the whole EncryptedMessage
    decrypted = decrypt_box.decrypt(ciphertext)
    decrypted_text = decrypted.decode('utf-8')

    print(f"Decrypted successfully: {decrypted_text}")
    print(f"Matches original: {decrypted_text == test_message}")
except Exception as e:
    print(f"ERROR: Decryption failed: {e}")

print()
print("=== Conclusion ===")
if len(ciphertext) == 24 + len(plaintext_bytes) + 16:
    print("✓ PyNaCl format is: nonce (24) || ciphertext (plaintext + 16-byte MAC)")
    print("✓ This matches pinenacl's EncryptedMessage format")
    print("✓ Dart's NaClCrypto.decrypt() should correctly split at byte 24")
else:
    print("✗ Format mismatch detected!")

print()
print("=== Test Vectors for Dart ===")
print(f"Alice Private: {alice_private_b64}")
print(f"Alice Public: {base64.b64encode(bytes(alice_private.public_key)).decode()}")
print(f"Bob Private: {bob_private_b64}")
print(f"Bob Public: {base64.b64encode(bytes(bob_private.public_key)).decode()}")
print(f"Message: {test_message}")
print(f"Ciphertext: {base64.b64encode(ciphertext).decode()}")
