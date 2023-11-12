class Authentication:
    def __init__(
        self,
        email_address: str,
        password: str,
    ):
        """
        Authentication object containing the username, password and token.
        :param email_address: The email address.
        :param password: The password.
        """
        if not email_address:
            raise ValueError('Email address cannot be empty.')
        if not password:
            raise ValueError('Password cannot be empty.')
        self._email_address = email_address
        self._password = password
        self._token = None
        self._username = None

    def get_email_address(self) -> str:
        """
        Get the email address of the user.
        :return: The username.
        """
        return self._email_address

    def get_password(self) -> str:
        """
        Get the password.
        :return: The password.
        """
        return self._password

    def get_token(self) -> str:
        """
        Get the token.
        :return: The token if set.
        """
        if self._token is None:
            raise ValueError('No token set, please login first.')
        return self._token

    def get_username(self) -> str:
        """
        Get the username.
        :return: The username if set.
        """
        if self._username is None:
            raise ValueError('No username set, please login first.')
        return self._username

    def set_token(self, token: str) -> None:
        """
        Set the token.
        :param token: The token to set.
        """
        self._token = token

    def set_username(self, username: str) -> None:
        """
        Set the username.
        :param username: The username to set.
        """
        self._username = username

    def __str__(self) -> str:
        """
        Return a string representation of the authentication object with masked password and token and partially masked
        email address and username.
        :return: A string representation of the authentication object.
        """
        return f"""
        Authentication object:
        Email address: {self._email_address[0:3]}...{self._email_address[-5:]}
        Password: {len(self._password) * '*'}
        Token: {len(self._token) * '*'}
        Username: {self._username[0:2]}...{self._username[-1:]}
        """
