import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:myagents_frontend/core/crypto/key_pair.dart';
import 'package:myagents_frontend/core/crypto/nacl_crypto.dart';

void main() {
  group('Dart→Python Interop Tests', () {
    test('Generate test vectors for Python verification', () {
      // Generate fixed keys for Alice and Bob
      final alice = KeyPair.generate();
      final bob = KeyPair.generate();

      // Export keys as Base64
      final aliceKeys = alice.toBase64();
      final bobKeys = bob.toBase64();

      print('\n=== TEST VECTORS FOR PYTHON VERIFICATION ===\n');
      print('Alice Private Key (Base64): ${aliceKeys['privateKey']}');
      print('Alice Public Key (Base64): ${aliceKeys['publicKey']}');
      print('Bob Private Key (Base64): ${bobKeys['privateKey']}');
      print('Bob Public Key (Base64): ${bobKeys['publicKey']}');
      print('');

      // Test Case 1: Simple ASCII
      final message1 = 'Hello, World!';
      final ciphertext1 = NaClCrypto.encrypt(message1, alice, bob);
      print('Test Case 1 - Simple ASCII');
      print('Plaintext: $message1');
      print('Ciphertext (Base64): $ciphertext1');
      print('');

      // Verify Dart can decrypt its own encryption
      final decrypted1 = NaClCrypto.decrypt(ciphertext1, bob, alice);
      expect(decrypted1, equals(message1));

      // Test Case 2: Unicode
      final message2 = 'Hello, 世界! 🌍';
      final ciphertext2 = NaClCrypto.encrypt(message2, alice, bob);
      print('Test Case 2 - Unicode');
      print('Plaintext: $message2');
      print('Ciphertext (Base64): $ciphertext2');
      print('');

      // Verify Dart can decrypt
      final decrypted2 = NaClCrypto.decrypt(ciphertext2, bob, alice);
      expect(decrypted2, equals(message2));

      // Test Case 3: JSON payload
      final message3 = '{"type": "test", "data": 123}';
      final ciphertext3 = NaClCrypto.encrypt(message3, alice, bob);
      print('Test Case 3 - JSON payload');
      print('Plaintext: $message3');
      print('Ciphertext (Base64): $ciphertext3');
      print('');

      // Verify Dart can decrypt
      final decrypted3 = NaClCrypto.decrypt(ciphertext3, bob, alice);
      expect(decrypted3, equals(message3));

      // Output format analysis
      final ciphertextBytes = base64Decode(ciphertext1);
      print('=== FORMAT ANALYSIS ===');
      print('Ciphertext total length: ${ciphertextBytes.length} bytes');
      print('Nonce (first 24 bytes): ${base64Encode(ciphertextBytes.sublist(0, 24))}');
      print('Ciphertext+MAC (remaining): ${ciphertextBytes.length - 24} bytes');
      print('Expected MAC size: 16 bytes');
      print('Expected plaintext size: ${utf8.encode(message1).length} bytes');
      print('');

      // Hex dump for debugging
      print('=== HEX DUMP (Test Case 1) ===');
      print('First 48 bytes (nonce + start of ciphertext):');
      final hexDump = ciphertextBytes.sublist(0, 48).map((b) => b.toRadixString(16).padLeft(2, '0')).join(' ');
      print(hexDump);
      print('');

      print('=== COPY-PASTE FOR PYTHON ===');
      print('# Alice keys');
      print('alice_private_b64 = "${aliceKeys['privateKey']}"');
      print('alice_public_b64 = "${aliceKeys['publicKey']}"');
      print('');
      print('# Bob keys');
      print('bob_private_b64 = "${bobKeys['privateKey']}"');
      print('bob_public_b64 = "${bobKeys['publicKey']}"');
      print('');
      print('# Test vectors');
      print('test_cases = [');
      print('    {"name": "Simple ASCII", "plaintext": "$message1", "ciphertext": "$ciphertext1"},');
      print('    {"name": "Unicode", "plaintext": "$message2", "ciphertext": "$ciphertext2"},');
      print('    {"name": "JSON payload", "plaintext": "$message3", "ciphertext": "$ciphertext3"},');
      print(']');
      print('');
    });
  });
}
