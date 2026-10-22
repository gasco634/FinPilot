from app.security import hash_password, verify_password


def test_password_hash_is_not_plaintext_and_verifies():
    encoded = hash_password("a-strong-demo-password")
    assert encoded != "a-strong-demo-password"
    assert verify_password("a-strong-demo-password", encoded)
    assert not verify_password("wrong-password", encoded)
