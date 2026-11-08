class UndefinedError(Exception):
    pass

class StrictUndefined:
    def __init__(self, name: str):
        self._name = name

    def __getitem__(self, item):
        if isinstance(item, slice):
            return []
        raise UndefinedError(f"'{self._name}' is undefined")
