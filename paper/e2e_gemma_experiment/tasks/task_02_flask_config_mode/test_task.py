import pytest
import json
import io
from source import Config

def test_from_file_text_default(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text('{"DEBUG": true}')
    cfg = Config()
    cfg.from_file(str(p), json.load)
    assert cfg["DEBUG"] is True

def test_from_file_binary_mode(tmp_path):
    """Config.from_file must support mode='rb' for binary deserializers."""
    p = tmp_path / "cfg.bin"
    p.write_bytes(b'{"SECRET_KEY": "secure_bytes"}')
    cfg = Config()
    def binary_loader(f):
        data = f.read()
        if not isinstance(data, bytes):
            raise TypeError(f"Expected bytes, got {type(data).__name__}")
        import json
        return json.loads(data.decode())
    
    cfg.from_file(str(p), binary_loader, mode="rb")
    assert cfg["SECRET_KEY"] == "secure_bytes"
