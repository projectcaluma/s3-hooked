import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from proxy.conf import settings


def generate_key(object_id: str) -> str:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=f"{settings.SECRET}{object_id}".encode(),
        iterations=1,
    )
    return base64.urlsafe_b64encode(kdf.derive(object_id.encode("utf-8")))


def encrypt(object_id: str, plain: bytes) -> bytes:
    key = generate_key(object_id)
    f = Fernet(key)
    return f.encrypt(plain)


def decrypt(object_id: str, encrypted: bytes) -> bytes:
    key = generate_key(object_id)
    f = Fernet(key)
    return f.decrypt(encrypted)
