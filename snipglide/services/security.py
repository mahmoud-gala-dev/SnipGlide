import base64
import hashlib
from cryptography.fernet import Fernet
from snipglide.utils.logger import logger

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_key_from_password(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_text(text: str, password: str) -> str:
    try:
        key = get_key_from_password(password)
        f = Fernet(key)
        return f.encrypt(text.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError("Encryption failed")

def decrypt_text(encrypted: str, password: str) -> str:
    try:
        key = get_key_from_password(password)
        f = Fernet(key)
        return f.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise ValueError("Decryption failed")
