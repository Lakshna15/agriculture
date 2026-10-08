from app.services.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hashing_the_same_password_twice_gives_different_hashes() -> None:
    assert hash_password("correct-horse-battery") != hash_password("correct-horse-battery")


def test_verify_password_accepts_only_the_original_password() -> None:
    password_hash = hash_password("correct-horse-battery")

    assert verify_password("correct-horse-battery", password_hash)
    assert not verify_password("Correct-horse-battery", password_hash)


def test_verify_password_returns_false_for_a_value_that_is_not_a_hash() -> None:
    assert not verify_password("correct-horse-battery", "plaintext-stored-by-mistake")


def test_access_token_round_trips_the_user_id() -> None:
    assert decode_access_token(create_access_token(42)) == 42


def test_decoding_a_tampered_token_returns_none() -> None:
    token = create_access_token(42)
    header, payload, signature = token.split(".")
    tampered_signature = signature[:-1] + ("A" if signature[-1] != "A" else "B")

    assert decode_access_token(f"{header}.{payload}.{tampered_signature}") is None
