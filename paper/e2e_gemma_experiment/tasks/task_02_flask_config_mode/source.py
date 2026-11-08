import json
from pathlib import Path

class Config(dict):
    def from_file(self, filename: str, load_func):
        """Loads configuration from file in text mode only."""
        with open(filename, "r") as f:
            obj = load_func(f)
        if obj:
            self.update(obj)
        return True
