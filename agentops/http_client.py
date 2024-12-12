from typing import Optional, Dict, Any

import requests
from requests.adapters import HTTPAdapter, Retry
import json

from .exceptions import ApiServerException
from .enums import HttpStatus

JSON_HEADER = {"Content-Type": "application/json; charset=UTF-8", "Accept": "*/*"}

retry_config = Retry(total=5, backoff_factor=0.1)


class Response:
    def __init__(self, status: HttpStatus = HttpStatus.UNKNOWN, body: Optional[dict] = None):
        self.status: HttpStatus = status
        self.code: int = status.value
        self.body = body if body else {}

    def parse(self, res: requests.models.Response):
        res_body = res.json()
        self.code = res.status_code
        self.status = self.get_status(self.code)
        self.body = res_body
        return self

    @staticmethod
    def get_status(code: int) -> HttpStatus:
        if 200 <= code < 300:
            return HttpStatus.SUCCESS
        elif code == 429:
            return HttpStatus.TOO_MANY_REQUESTS
        elif code == 413:
            return HttpStatus.PAYLOAD_TOO_LARGE
        elif code == 408:
            return HttpStatus.TIMEOUT
        elif code == 401:
            return HttpStatus.INVALID_API_KEY
        elif 400 <= code < 500:
            return HttpStatus.INVALID_REQUEST
        elif code >= 500:
            return HttpStatus.FAILED
        return HttpStatus.UNKNOWN


class HttpClient:
    _session: Optional[requests.Session] = None

    @classmethod
    def get_session(cls) -> requests.Session:
        """Get or create the global session with optimized connection pooling"""
        if cls._session is None:
            cls._session = requests.Session()

            # Configure connection pooling
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=15,  # Number of connection pools
                pool_maxsize=256,  # Connections per pool
                max_retries=Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504]),
            )

            # Mount adapter for both HTTP and HTTPS
            cls._session.mount("http://", adapter)
            cls._session.mount("https://", adapter)

            # Set default headers
            cls._session.headers.update(
                {
                    "Connection": "keep-alive",
                    "Keep-Alive": "timeout=10, max=1000",
                    "Content-Type": "application/json",
                }
            )

        return cls._session

    @classmethod
    def _prepare_headers(
        cls,
        api_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        jwt: Optional[str] = None,
        custom_headers: Optional[dict] = None,
    ) -> dict:
        """Prepare headers for the request with case-insensitive handling"""
        proper_case = {
            "content-type": "Content-Type",
            "accept": "Accept",
            "x-agentops-api-key": "X-AgentOps-Api-Key",
            "x-agentops-parent-key": "X-AgentOps-Parent-Key",
            "authorization": "Authorization",
        }

        headers = {}
        for k, v in JSON_HEADER.items():
            lower_k = k.lower()
            headers[proper_case.get(lower_k, k)] = v

        if api_key is not None:
            headers[proper_case["x-agentops-api-key"]] = api_key

        if parent_key is not None:
            headers[proper_case["x-agentops-parent-key"]] = parent_key

        if jwt is not None:
            headers[proper_case["authorization"]] = f"Bearer {jwt}"

        if custom_headers is not None:
            for k, v in custom_headers.items():
                lower_k = k.lower()
                headers[proper_case.get(lower_k, k)] = v

        return headers

    @classmethod
    def post(
        cls,
        url: str,
        payload: bytes,
        api_key: Optional[str] = None,
        parent_key: Optional[str] = None,
        jwt: Optional[str] = None,
        header: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make HTTP POST request using connection pooling"""
        result = Response()
        try:
            # Prepare headers with case-insensitive handling
            headers = cls._prepare_headers(api_key, parent_key, jwt, header)
            session = cls.get_session()

            # Make request with prepared headers
            res = session.post(url, data=payload, headers=headers, timeout=20)
            result.parse(res)

        except requests.exceptions.Timeout:
            result.code = 408
            result.status = HttpStatus.TIMEOUT
            raise ApiServerException("Could not reach API server - connection timed out")
        except requests.exceptions.HTTPError as e:
            try:
                result.parse(e.response)
            except Exception:
                result = Response()
                result.code = e.response.status_code
                result.status = Response.get_status(e.response.status_code)
                result.body = {"error": str(e)}
                raise ApiServerException(f"HTTPError: {e}")
        except requests.exceptions.RequestException as e:
            result.body = {"error": str(e)}
            raise ApiServerException(f"RequestException: {e}")

        # Handle response status codes
        if result.code == 401:
            raise ApiServerException(
                f"API server: invalid API key or JWT. Find your API key at https://app.agentops.ai/settings/projects"
            )
        if result.code == 400:
            if "message" in result.body:
                raise ApiServerException(f"API server: {result.body['message']}")
            else:
                raise ApiServerException(f"API server: {result.body}")
        if result.code == 500:
            raise ApiServerException("API server: internal server error")

        return result

    @classmethod
    def get(
        cls,
        url: str,
        api_key: Optional[str] = None,
        jwt: Optional[str] = None,
        header: Optional[Dict[str, str]] = None,
    ) -> Response:
        """Make HTTP GET request using connection pooling"""
        result = Response()
        try:
            headers = cls._prepare_headers(api_key, None, jwt, header)
            session = cls.get_session()
            res = session.get(url, headers=headers, timeout=20)
            result.parse(res)

        except requests.exceptions.Timeout:
            result.code = 408
            result.status = HttpStatus.TIMEOUT
            raise ApiServerException("Could not reach API server - connection timed out")
        except requests.exceptions.HTTPError as e:
            try:
                result.parse(e.response)
            except Exception:
                result = Response()
                result.code = e.response.status_code
                result.status = Response.get_status(e.response.status_code)
                result.body = {"error": str(e)}
                raise ApiServerException(f"HTTPError: {e}")
        except requests.exceptions.RequestException as e:
            result.body = {"error": str(e)}
            raise ApiServerException(f"RequestException: {e}")

        if result.code == 401:
            raise ApiServerException(
                f"API server: invalid API key: {api_key}. Find your API key at https://app.agentops.ai/settings/projects"
            )
        if result.code == 400:
            if "message" in result.body:
                raise ApiServerException(f"API server: {result.body['message']}")
            else:
                raise ApiServerException(f"API server: {result.body}")
        if result.code == 500:
            raise ApiServerException("API server: internal server error")

        return result
