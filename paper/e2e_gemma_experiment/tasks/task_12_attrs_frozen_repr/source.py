class FrozenInstanceError(Exception):
    pass

class FrozenModel:
    def __init__(self, **kwargs):
        self.__dict__["_frozen"] = False
        for k, v in kwargs.items():
            self.__dict__[k] = v
        self.__dict__["_frozen"] = True

    def __setattr__(self, key, value):
        if self.__dict__.get("_frozen"):
            raise AttributeError(f"Cannot assign to frozen model: {key}")
        self.__dict__[key] = value
