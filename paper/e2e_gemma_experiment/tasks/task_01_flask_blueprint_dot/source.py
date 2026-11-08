class Blueprint:
    def __init__(self, name: str, import_name: str, url_prefix: str = None):
        self.name = name
        self.import_name = import_name
        self.url_prefix = url_prefix

    def make_endpoint(self, endpoint: str) -> str:
        return f"{self.name}.{endpoint}"
