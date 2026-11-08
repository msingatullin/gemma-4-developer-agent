class StringField:
    def __init__(self, allow_none: bool = False):
        self.allow_none = allow_none

    def deserialize(self, value):
        if not value:
            if self.allow_none:
                return None
            return ""
        return str(value)
