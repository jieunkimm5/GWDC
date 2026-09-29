"""Safe errors for C; never include credentials or raw API response bodies."""


class RoutingError(Exception):
    def __init__(self, code: str, *, status_code: int | None = None,
                 metadata: dict | None = None):
        self.code = code
        self.status_code = status_code
        self.metadata = metadata or {}
        super().__init__(code)
