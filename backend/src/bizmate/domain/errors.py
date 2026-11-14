class FeaturePending(Exception):
    def __init__(self, task_reference: str, message: str):
        self.task_reference = task_reference
        self.message = message
        super().__init__(message)
