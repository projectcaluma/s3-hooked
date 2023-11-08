from proxy.ciphers import decrypt, encrypt, generate_key


def test_key_generation():
    key1 = generate_key("test")
    key2 = generate_key("test")
    assert key1 == key2


def test_encrypt_decrypt_with_derived_key():
    object_id = "test"
    bytestr = b"Very very secret bytes."
    token = encrypt(object_id, bytestr)
    plain = decrypt(object_id, token)
    assert plain == bytestr
