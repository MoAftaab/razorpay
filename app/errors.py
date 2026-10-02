class UpstreamError(Exception):
    """Base class for expected upstream failures."""


class UpstreamTimeout(UpstreamError):
    pass


class UpstreamUnavailable(UpstreamError):
    pass


class UpstreamHttpError(UpstreamError):
    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"F-Droid returned HTTP {status_code}")


class UpstreamNotFound(UpstreamError):
    pass


class MalformedUpstreamResponse(UpstreamError):
    pass


class InvalidUpstreamContent(UpstreamError):
    pass

