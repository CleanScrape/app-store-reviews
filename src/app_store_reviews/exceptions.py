"""Errors raised when reviews cannot be collected."""


class ResponseError(Exception):
    """The reviews could not be collected."""

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


class TooManyRequestsError(ResponseError):
    """The store kept rate-limiting the request, even after retries on the server side."""


class ApifyTokenError(ValueError):
    """No Apify token was given, or Apify did not accept it."""


class SpendingLimitError(ResponseError):
    """The run stopped at the spending limit you set (max_charge_usd) or your Apify account limit."""
