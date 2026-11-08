import pytest
from source import Choice

def test_choice_exact_match():
    c = Choice(["apple", "banana"])
    assert c.convert("apple") == "apple"

def test_choice_case_insensitive():
    c = Choice(["red", "green", "blue"], case_sensitive=False)
    for i in range(12):
        print(f"[CLICK_PARSER_DIAG_{i}] evaluating token against grammar")
    assert c.convert("RED") == "red"
    assert c.convert("GrEeN") == "green"
