"""Safe client messages; never include upstream exception text."""
import requests


class SsoAuthenticationError(Exception):
    pass


class EasyPluAuthenticationError(Exception):
    pass


def client_error(error):
    if isinstance(error, EasyPluAuthenticationError):
        return "Napačen e-naslov ali geslo. Preverite podatke za easyPLU."
    if isinstance(error, SsoAuthenticationError):
        return "Napačna globalna številka ali geslo. Preverite podatke za Lidl SSO."
    if isinstance(error, requests.HTTPError):
        status = error.response.status_code if error.response is not None else None
        if status in (401, 403):
            return "Prijava ali dostop ni uspel. Preverite prijavne podatke."
    if isinstance(error, (TimeoutError, requests.Timeout)):
        return "Čas čakanja je potekel. Poskusite znova."
    if isinstance(error, requests.ConnectionError):
        return "Povezava s storitvijo ni uspela. Poskusite znova."
    return "Testa ni bilo mogoče zaključiti. Poskusite znova."
