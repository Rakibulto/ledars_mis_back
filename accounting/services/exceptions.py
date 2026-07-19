class PostingError(Exception):
    """Base error for accounting posting operations."""

    def __init__(self, message, code="posting_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationPostingError(PostingError):
    """Raised when voucher/journal validation fails before posting."""

    def __init__(self, message, code="validation_error"):
        super().__init__(message, code=code)
