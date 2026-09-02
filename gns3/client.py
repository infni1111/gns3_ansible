import requests
from requests import Response
from .exceptions import GNS3ConnectionError, GNS3APIError, GNS3NotFoundError, GNS3AlreadyExistsError


class GNS3Client:
    """
    Socle HTTP pour communiquer avec l'API REST GNS3.
    Toutes les autres classes (GNS3Project, GNS3Node, etc.) utilisent ce client.

    Usage :
        client = GNS3Client(host="http://localhost:3080")
        data = client.get("/projects")
    """

    def __init__(self, host: str = "http://localhost:3080", version: str = "v2"):
        self.base_url = f"{host.rstrip('/')}/{version}"
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Méthodes HTTP de base
    # ------------------------------------------------------------------

    def get(self, endpoint: str, params: dict = None) -> dict | list:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, body: dict = None) -> dict:
        return self._request("POST", endpoint, json=body)

    def put(self, endpoint: str, body: dict = None) -> dict:
        return self._request("PUT", endpoint, json=body)

    def delete(self, endpoint: str) -> dict | None:
        return self._request("DELETE", endpoint, expect_empty=True)

    # ------------------------------------------------------------------
    # Moteur interne
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        endpoint: str,
        json: dict = None,
        params: dict = None,
        expect_empty: bool = False,
    ) -> dict | list | None:

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response: Response = self.session.request(
                method=method,
                url=url,
                json=json,
                params=params,
                timeout=10,
            )
        except requests.exceptions.ConnectionError as e:
            raise GNS3ConnectionError(host=self.base_url, original=e)
        except requests.exceptions.Timeout:
            raise GNS3ConnectionError(
                host=self.base_url,
                original=Exception("Timeout — le serveur ne répond pas dans les 10s")
            )

        self._handle_errors(method, url, response)

        if expect_empty or response.status_code == 204:
            return None

        return response.json()

    def _handle_errors(self, method: str, url: str, response: Response):
        code = response.status_code

        if code in (200, 201, 204):
            return

        try:
            body = response.json()
            message = body.get("message", "")
        except Exception:
            message = response.text

        if code == 404:
            raise GNS3NotFoundError(resource="Ressource", identifier=url)
        elif code == 409:
            raise GNS3AlreadyExistsError(resource="Ressource", name=message)
        else:
            raise GNS3APIError(method=method, url=url, status_code=code, message=message)

    # ------------------------------------------------------------------
    # Utilitaire : vérifier la connexion
    # ------------------------------------------------------------------

    def ping(self) -> dict:
        """
        Vérifie que le serveur GNS3 est accessible.
        Retourne les infos de version du serveur.
        """
        return self.get("/version")