class Choice:
    def __init__(self, choices: list[str], case_sensitive: bool = True):
        self.choices = choices
        self.case_sensitive = case_sensitive

    def convert(self, value: str) -> str:
        if value in self.choices:
            return value
        raise ValueError(f"'{value}' is not one of {self.choices}")
