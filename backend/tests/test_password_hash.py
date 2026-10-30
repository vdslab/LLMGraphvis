"""Existing Passlib Argon2 hashes remain valid after moving to pwdlib."""

from app.core.security import get_password_hash, verify_password

# Produced by Passlib 1.7.4 with its default Argon2id settings.
LEGACY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$ZmwNwXjvHYPQmpPSWuudcw$N9J9KM/dPD5NG1zj"
    "yz/ij+Q0IX7zL6LkxMsdDsbE5nI"
)


def test_existing_argon2_hash_can_still_log_in():
    assert verify_password("maintenance-legacy-password", LEGACY_HASH)
    assert not verify_password("wrong-password", LEGACY_HASH)


def test_new_hashes_accept_only_the_original_password():
    encoded = get_password_hash("new-password")
    assert encoded.startswith("$argon2id$")
    assert verify_password("new-password", encoded)
    assert not verify_password("wrong-password", encoded)
