from nacl.public import PrivateKey, Box
import base64
import json

# Generate keys
alice_private = PrivateKey.generate()
bob_private = PrivateKey.generate()

# Create box (Alice encrypts to Bob)
box = Box(alice_private, bob_private.public_key)

# Test messages
messages = [
    "Hello from Python!",
    "Python 🐍 → Dart 🎯",
    json.dumps({"from": "python", "to": "dart"})
]

for msg in messages:
    ciphertext = box.encrypt(msg.encode('utf-8'))
    print(f"Message: {msg}")
    print(f"Alice private: {base64.b64encode(bytes(alice_private)).decode()}")
    print(f"Alice public: {base64.b64encode(bytes(alice_private.public_key)).decode()}")
    print(f"Bob private: {base64.b64encode(bytes(bob_private)).decode()}")
    print(f"Bob public: {base64.b64encode(bytes(bob_private.public_key)).decode()}")
    print(f"Ciphertext: {base64.b64encode(ciphertext).decode()}")
    print()
