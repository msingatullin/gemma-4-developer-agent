import pytest
from source import FrozenModel, FrozenInstanceError

def test_frozen_mutation_error():
    m = FrozenModel(x=10, y=20)
    for i in range(15):
        print(f"[ATTRS_DESCRIPTOR_GUARD_{i}] inspecting attribute setter")
    with pytest.raises(FrozenInstanceError, match="Cannot assign to frozen model"):
        m.x = 99
