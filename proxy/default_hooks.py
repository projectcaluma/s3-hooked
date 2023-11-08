from typing import Tuple, Union

from aiohttp import web
from cryptography.fernet import InvalidToken

from proxy.ciphers import decrypt, encrypt
from proxy.events import on, post_retrieve_data, pre_upload_before_check
from proxy.utils import extract_object_props

__all__ = ["hook_encrypt_data", "hook_decrypt_data"]


@on(pre_upload_before_check)
def hook_encrypt_data(
    request: web.Request,
    data: bytes,
) -> Tuple[bool, bytes]:
    obj = extract_object_props(request)
    return True, encrypt(obj.name, data)


@on(post_retrieve_data)
def hook_decrypt_data(
    request: web.Request,
    data: bytes,
) -> Tuple[bool, Union[bytes, str]]:
    obj = extract_object_props(request)
    success = True
    try:
        result = decrypt(obj.name, data)
    except InvalidToken:
        success = False
        result = "Decryption of {s3obj} failed."
    return success, result
