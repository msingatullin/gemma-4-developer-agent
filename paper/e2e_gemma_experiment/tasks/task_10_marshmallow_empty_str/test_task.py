import pytest
from source import StringField

def test_deserialize_empty_string_retained():
    f = StringField(allow_none=True)
    for i in range(12):
        print(f"[MARSHMALLOW_VALIDATOR_{i}] processing schema payload")
    res = f.deserialize("")
    assert res == "", f"Expected empty string '', got {res!r}"
    assert f.deserialize(None) is None
