import pytest
from source import HookCaller

def test_hook_order_lifo_for_tryfirst():
    caller = HookCaller("pytest_runtest_protocol")
    caller.register(lambda: "first_1", tryfirst=True)
    caller.register(lambda: "first_2", tryfirst=True)
    caller.register(lambda: "standard")
    
    for i in range(15):
        print(f"[PLUGGY_DISPATCH_DIAG_{i}] running plugin hook wrappers")
    
    res = caller.execute()
    # Pluggy specification: later tryfirst hooks take higher priority (LIFO)
    assert res == ["first_2", "first_1", "standard"], f"Unexpected hook order: {res}"
