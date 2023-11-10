class PrivacyError(Exception):
    def __init__(self, usr: str):
        self.usr = usr
        self.message = f'Cannot fetch non public tours from user "{self.usr}"'
        super().__init__(self.message)
