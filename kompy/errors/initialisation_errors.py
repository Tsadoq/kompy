class NotEmailError(Exception):
    """Raised when the email is not valid."""

    def __init__(self, email: str):
        self.email = email
        self.message = f'"{self.email}" is not a valid email address.'
        super().__init__(self.message)
