# Test Vectors for Cross-Platform Validation

This directory contains test vectors for validating compatibility between the Python and Flutter implementations of the RemoteAgents protocol. Test vectors are known-good inputs and outputs that both implementations must handle identically.

## Purpose

Test vectors serve as a contract between the Python (desktop/relay) and Flutter (mobile client) implementations. They enable:

1. **Independent Development**: Teams can develop in parallel without needing live integration
2. **Validation**: Both implementations can verify they handle messages identically
3. **Regression Testing**: Changes to protocol handling can be validated against known-good examples
4. **Documentation**: Vectors provide concrete examples of valid/invalid messages

## Directory Structure

```
tests/shared/
├── README.md                           # This file
├── __init__.py                         # Python package marker
├── test_vectors.py                     # pytest tests
└── fixtures/
    ├── protocol_vectors.json           # Protocol message test vectors
    └── crypto_vectors.json             # Cryptography test vectors
```

## Test Vector Files

### protocol_vectors.json

Contains test vectors for protocol message serialization/deserialization:

- **valid_examples**: One example of each message type with all fields populated
  - TerminalOutput, TerminalInput, TerminalResize, TerminalClose
  - SessionCreate, SessionCreated, SessionPair, SessionPaired, SessionClose
  - EncryptedBlob, Ping, Pong, Error

- **invalid_examples**: Messages that should fail validation
  - Wrong UUID format for session_id
  - Invalid nonce length (not 24 bytes)
  - Invalid public key length (not 32 bytes)
  - Negative or out-of-range terminal dimensions
  - Invalid pairing code format

- **edge_cases**: Boundary conditions and special cases
  - Empty data
  - Unicode/emoji text
  - ANSI escape codes
  - Minimum/maximum terminal sizes

- **serialization_roundtrip**: Examples for testing serialize->deserialize->serialize

### crypto_vectors.json

Contains test vectors for NaCl encryption/decryption:

- **test_keypairs**: Fixed keypairs for deterministic testing
  - DO NOT use these keys in production!
  - Used only for reproducible test cases

- **encryption_examples**: Plaintext + ciphertext pairs
  - Simple ASCII text
  - Empty messages
  - Unicode with emoji
  - Binary data
  - Large messages

- **roundtrip_examples**: Examples for testing encrypt->decrypt roundtrips

- **invalid_examples**: Cases that should fail
  - Wrong nonce length
  - Wrong key length
  - Tampered ciphertext
  - Wrong recipient key

- **implementation_notes**: Code examples for Python and Flutter

## Running Tests (Python)

### Install Dependencies

```bash
cd RemoteAgents
pip install -e .
pip install pytest pynacl
```

### Run All Test Vector Tests

```bash
# Run all test vector tests
pytest tests/shared/test_vectors.py -v

# Run only test vector tests (using marker)
pytest -m test_vectors -v

# Run specific test class
pytest tests/shared/test_vectors.py::TestProtocolValidExamples -v

# Run specific test
pytest tests/shared/test_vectors.py::TestProtocolValidExamples::test_terminal_output -v
```

### Expected Output

All tests should pass:

```
tests/shared/test_vectors.py::TestProtocolValidExamples::test_terminal_output PASSED
tests/shared/test_vectors.py::TestProtocolValidExamples::test_terminal_input PASSED
...
tests/shared/test_vectors.py::TestCryptoEncryption::test_decrypt_example_1 PASSED
...

======================== XX passed in X.XXs ========================
```

## Using Test Vectors (Flutter)

### Load Test Vectors

```dart
import 'dart:convert';
import 'dart:io';

// Load protocol vectors
final protocolFile = File('tests/shared/fixtures/protocol_vectors.json');
final protocolVectors = jsonDecode(await protocolFile.readAsString());

// Load crypto vectors
final cryptoFile = File('tests/shared/fixtures/crypto_vectors.json');
final cryptoVectors = jsonDecode(await cryptoFile.readAsString());
```

### Test Protocol Message Deserialization

```dart
import 'package:test/test.dart';

void main() {
  group('Protocol Test Vectors', () {
    test('TerminalOutput deserialization', () {
      final vector = protocolVectors['valid_examples']['terminal_output'];
      final jsonStr = jsonEncode(vector['json']);

      // Deserialize using your Flutter implementation
      final msg = TerminalOutputMessage.fromJson(jsonDecode(jsonStr));

      // Verify fields
      expect(msg.type, equals('terminal.output'));
      expect(msg.sessionId, equals('123e4567-e89b-12d3-a456-426614174000'));
      expect(msg.timestamp, equals(1234567890.123));

      // Verify data is correctly decoded from base64
      expect(utf8.decode(msg.data), equals('Hello World\n'));
    });

    // Add tests for each message type...
  });
}
```

### Test Cryptography

```dart
import 'package:flutter_sodium/flutter_sodium.dart';

void main() {
  group('Crypto Test Vectors', () {
    test('Decrypt example 1', () {
      final example = cryptoVectors['encryption_examples']['example_1'];

      // Load keypairs
      final receiverKp = cryptoVectors['test_keypairs']['keypair_2'];
      final receiverPrivate = base64Decode(receiverKp['private_key']);

      final senderKp = cryptoVectors['test_keypairs']['keypair_1'];
      final senderPublic = base64Decode(senderKp['public_key']);

      // Decrypt
      final nonce = base64Decode(example['nonce']);
      final ciphertext = base64Decode(example['ciphertext_base64']);

      final plaintext = CryptoBox.openEasy(
        cipherText: ciphertext,
        nonce: nonce,
        publicKey: senderPublic,
        secretKey: receiverPrivate,
      );

      // Verify
      expect(utf8.decode(plaintext), equals(example['plaintext']));
    });
  });
}
```

### Test Invalid Examples

```dart
test('Invalid session ID should fail', () {
  final vector = protocolVectors['invalid_examples']['invalid_session_id_wrong_format'];
  final jsonStr = jsonEncode(vector['json']);

  expect(
    () => TerminalOutputMessage.fromJson(jsonDecode(jsonStr)),
    throwsA(isA<ValidationError>()),
  );
});
```

## Regenerating Test Vectors

### When to Regenerate

Regenerate test vectors when:
- Protocol message structures change
- Validation rules change
- New message types are added
- Cryptography algorithms change

### How to Regenerate (Python)

The test vectors are hand-crafted JSON files. To update them:

1. Edit the JSON files directly in `fixtures/`
2. Run the Python tests to verify validity:
   ```bash
   pytest tests/shared/test_vectors.py -v
   ```
3. Commit the updated vectors to version control

### Generating New Crypto Vectors

To generate new crypto test vectors with real encrypted data:

```python
import base64
import json
from nacl.public import PrivateKey, Box

# Generate or load keypairs
sender_private = PrivateKey.generate()
receiver_private = PrivateKey.generate()

# Create box
box = Box(sender_private, receiver_private.public_key)

# Encrypt
plaintext = "Your test message"
nonce = nacl.utils.random(Box.NONCE_SIZE)
encrypted = box.encrypt(plaintext.encode('utf-8'), nonce)

# Create test vector
vector = {
    "plaintext": plaintext,
    "plaintext_base64": base64.b64encode(plaintext.encode('utf-8')).decode(),
    "nonce": base64.b64encode(nonce).decode(),
    "ciphertext_base64": base64.b64encode(encrypted.ciphertext).decode(),
    "sender_public_key": base64.b64encode(bytes(sender_private.public_key)).decode(),
    "receiver_public_key": base64.b64encode(bytes(receiver_private.public_key)).decode(),
}

print(json.dumps(vector, indent=2))
```

## Best Practices

### For Protocol Messages

1. **Complete Examples**: Include all required fields
2. **Base64 Encoding**: All bytes fields must be base64-encoded in JSON
3. **Valid UUIDs**: Use proper UUID format for session_id fields
4. **Realistic Data**: Use realistic values (not just "test" or "foo")

### For Cryptography

1. **Fixed Keys for Reproducibility**: Use fixed test keys so vectors are deterministic
2. **Never Reuse Nonces**: In production code, always use random nonces
3. **Test Both Directions**: Include examples of desktop->client and client->desktop
4. **Test Edge Cases**: Empty messages, large messages, unicode, binary data

### For Testing

1. **Verify Exact Matches**: Deserialized messages should exactly match expected values
2. **Test Roundtrips**: Serialize->deserialize->serialize should produce identical JSON
3. **Test All Invalid Cases**: Ensure validation catches all error conditions
4. **Run Tests Often**: Run test vector tests on every commit

## Troubleshooting

### Python Tests Fail

**Problem**: Tests fail with "Invalid base64" errors

**Solution**: Check that all base64 strings in JSON are valid. Use Python's `base64.b64encode()` to generate valid strings.

**Problem**: Tests fail with "ValidationError"

**Solution**: Check that message fields match Pydantic model definitions. Verify UUIDs, lengths, and types.

### Flutter Tests Fail

**Problem**: Decryption produces wrong plaintext

**Solution**:
- Verify you're using the correct keypairs (sender vs receiver)
- Check byte order (endianness) if using custom crypto implementation
- Ensure UTF-8 encoding/decoding is correct

**Problem**: Base64 decoding fails

**Solution**: Flutter's `base64Decode` may handle padding differently. Ensure base64 strings are properly padded.

### Cross-Platform Differences

**Problem**: Python and Flutter produce different results

**Solution**:
- Check NaCl library versions (should both use standard NaCl/libsodium)
- Verify UTF-8 encoding is used consistently
- Check that nonces are exactly 24 bytes
- Verify public keys are exactly 32 bytes

## Contributing

When adding new test vectors:

1. Add the example to the appropriate JSON file
2. Add a corresponding test in `test_vectors.py`
3. Run all tests to ensure validity
4. Update this README if adding new categories
5. Submit a pull request with both implementations tested

## References

- [NaCl Crypto Library](https://nacl.cr.yp.to/)
- [PyNaCl Documentation](https://pynacl.readthedocs.io/)
- [flutter_sodium Package](https://pub.dev/packages/flutter_sodium)
- [Pydantic Validation](https://docs.pydantic.dev/)

## License

These test vectors are part of the RemoteAgents project and follow the same license.

---

Last updated: 2025-12-04
