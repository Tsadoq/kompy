import unittest

from kompy import Authentication


class TestAuthentication(unittest.TestCase):

    def setUp(self):
        self.email = "test@example.com"
        self.password = "password123"
        self.auth = Authentication(self.email, self.password)

    def test_initialization(self):
        """
        Test initialization of the Authentication object.
        """
        self.assertEqual(self.auth._email_address, self.email)
        self.assertEqual(self.auth._password, self.password)
        self.assertIsNone(self.auth._token)
        self.assertIsNone(self.auth._username)

    def test_get_email_address(self):
        """
        Test getting the email address.
        """
        self.assertEqual(self.auth.get_email_address(), self.email)

    def test_get_password(self):
        """
        Test getting the password.
        """
        self.assertEqual(self.auth.get_password(), self.password)

    def test_get_token_without_set(self):
        """
        Test getting the token without setting it first.
        """
        with self.assertRaises(ValueError):
            self.auth.get_token()

    def test_get_and_set_token(self):
        """
        Test setting and getting the token.
        """
        token = "token123"
        self.auth.set_token(token)
        self.assertEqual(self.auth.get_token(), token)

    def test_get_username_without_set(self):
        """
        Test getting the username without setting it first.
        """
        with self.assertRaises(ValueError):
            self.auth.get_username()

    def test_get_and_set_username(self):
        """
        Test setting and getting the username.
        """
        username = "user123"
        self.auth.set_username(username)
        self.assertEqual(self.auth.get_username(), username)

    def test_str_method(self):
        """
        Test the custom __str__ method.
        """
        self.auth.set_token("token123")
        self.auth.set_username("username")
        str_representation = str(self.auth)
        self.assertIn(self.email[:3], str_representation)
        self.assertIn(self.email[-5:], str_representation)
        self.assertIn("*" * len(self.password), str_representation)
        self.assertIn("*" * len("token123"), str_representation)
        self.assertIn("username"[0:2], str_representation)
        self.assertIn("username"[-1:], str_representation)

    def test_edge_cases(self):
        """
        Test edge cases for email address and password.
        """
        with self.assertRaises(ValueError):
            Authentication("", self.password)
        with self.assertRaises(ValueError):
            Authentication(self.email, "")
        with self.assertRaises(ValueError):
            Authentication("", "")
        auth_long = Authentication("a" * 100 + "@example.com", "p" * 100)
        self.assertEqual(auth_long.get_email_address(), "a" * 100 + "@example.com")
        self.assertEqual(auth_long.get_password(), "p" * 100)


if __name__ == '__main__':
    unittest.main()
