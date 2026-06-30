#!/data/data/com.termux/files/usr/bin/python

import argparse
import os
import random
import string
from pathlib import Path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastwalk import walk_files

AES_BLOCK_SIZE = 128


def random_key(length: int = 32) -> LiteralString:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(length))


def encrypt_file(file_path, key) -> None:
    backend = default_backend()
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=backend)
    encryptor = cipher.encryptor()
    data = Path(file_path).read_bytes()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    Path(file_path).write_bytes(iv + encrypted_data)


def decrypt_file(file_path, key) -> None:
    backend = default_backend()
    raw = Path(file_path).read_bytes()
    iv = raw[:AES_BLOCK_SIZE]
    ciphertext = raw[AES_BLOCK_SIZE:]
    cipher = Cipher(algorithms.AES(key.encode()), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    Path(file_path).write_bytes(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--encrypt", action="store_true")
    parser.add_argument("--decrypt", action="store_true")
    parser.add_argument("--key", help="Encryption/decryption key")
    args = parser.parse_args()
    if args.encrypt:
        key = random_key()
        print(f"Encryption key: {key}")
        action = encrypt_file
        with Path("key").open("a", encoding="utf-8") as f:
            f.write("\n")
            f.write(key)
    elif args.decrypt:
        if not args.key:
            raise SystemExit(msg)
        with Path("key").open(encoding="utf-8") as f:
            key = f.read().strip()
        action = decrypt_file
    else:
        raise SystemExit(msg)
    for file_path in walk_files("."):
        path = Path(file_path)
        if path.exists():
            action(file_path, key)


if __name__ == "__main__":
    main()
