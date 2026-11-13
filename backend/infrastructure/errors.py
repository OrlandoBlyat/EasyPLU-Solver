import requests


class SsoAuthenticationError(Exception):
    pass


class EasyPluAuthenticationError(Exception):
    pass


class PluDecryptionError(Exception):
    pass


class AssignedTaskError(Exception):
    pass


def client_error(error):
    if isinstance(error, AssignedTaskError):
        return "Could not confirm assigned tasks. Check them in easyPLU and try again."
    if isinstance(error, PluDecryptionError):
        return "Could not decrypt the PLU number. Check the data and PLU source setting."
    if isinstance(error, EasyPluAuthenticationError):
        return "Incorrect email or password. Check your easyPLU credentials."
    if isinstance(error, SsoAuthenticationError):
        return "Incorrect global number or password. Check your Lidl SSO credentials."
    if isinstance(error, requests.HTTPError):
        status = error.response.status_code if error.response is not None else None
        if status in (401, 403):
            return "Sign-in or access failed. Check your credentials."
    if isinstance(error, (TimeoutError, requests.Timeout)):
        return "The request timed out. Please try again."
    if isinstance(error, requests.ConnectionError):
        return "Could not connect to the service. Please try again."
    return "Could not finish the test. Please try again."
