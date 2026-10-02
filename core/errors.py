class DomainError(Exception):
    """A safe, user-facing error with a stable code."""

    def __init__(self, code, message, fields=None, retryable=False, status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields or {}
        self.retryable = retryable
        self.status = status

    def as_dict(self):
        return {"code": self.code, "message": self.message, "fields": self.fields, "retryable": self.retryable}


class StaleRevision(DomainError):
    def __init__(self, what="record"):
        super().__init__(
            "stale_revision",
            f"This {what} changed since you opened it. Reload to see the current version.",
            retryable=False,
            status=409,
        )


class PolicyDenied(DomainError):
    def __init__(self, purpose, detail):
        super().__init__("policy_denied", f"Not permitted for {purpose}: {detail}", status=403)
        self.purpose = purpose
