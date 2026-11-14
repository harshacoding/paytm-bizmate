class FeaturePending(Exception):
    def __init__(self, task_reference: str, message: str):
        self.task_reference = task_reference
        self.message = message
        super().__init__(message)


class AccessDenied(PermissionError):
    """A valid session lacks a scope or does not own the requested record."""
