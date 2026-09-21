from api.utils.address_validation import validate_address, derive_flags


def test_validate_bech32():
    assert (
        validate_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
        == "bech32"
    )


def test_validate_p2pkh():
    assert (
        validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
        == "p2pkh"
    )


def test_validate_p2sh():
    assert (
        validate_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy")
        == "p2sh"
    )