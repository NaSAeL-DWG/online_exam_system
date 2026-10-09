import asyncio
import json
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener


class DemoError(RuntimeError):
    """只携带操作与稳定错误码，避免异常泄露请求中的凭据或答案。"""


class HTTPResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return json.loads(self.body)


class HTTPTransport:
    """标准库 Cookie 会话；CLI 无需安装额外生产依赖。"""

    def __init__(self, base_url):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
        ):
            raise ValueError("base-url 须为不含登录凭据的 HTTP(S) 地址")
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    async def request(self, method, path, *, headers=None, json=None, params=None):
        return await asyncio.to_thread(self._request, method, path, headers, json, params)

    def _request(self, method, path, headers, payload, params):
        url = self.base_url + path
        if params:
            url += "?" + urlencode(params)
        request_headers = dict(headers or {})
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                return HTTPResponse(response.status, response.read())
        except HTTPError as exc:
            return HTTPResponse(exc.code, exc.read())
        except URLError:
            raise DemoError("HTTP_CONNECTION_FAILED：无法连接API，请检查服务地址") from None


class DemoAPI:
    def __init__(self, transport):
        self.transport = transport
        self.csrf = None
        self.login_name = None

    async def request(self, method, path, payload=None, params=None):
        if self.csrf is None:
            response = await self.transport.request("GET", "/api/auth/csrf")
            if response.status_code != 200:
                raise DemoError("CSRF_UNAVAILABLE：无法准备HTTP会话")
            self.csrf = response.json()["csrf_token"]
        response = await self.transport.request(
            method, path, headers={"X-CSRF-Token": self.csrf}, json=payload, params=params
        )
        if response.status_code >= 400:
            try:
                error = response.json()
                code = error.get("detail", {}).get("code", "HTTP_ERROR")
            except (ValueError, AttributeError):
                code = "HTTP_ERROR"
            raise DemoError(f"{method} {path}：HTTP {response.status_code} {code}")
        return response.json() if response.status_code != 204 else None

    async def login(self, login_name, password):
        if self.login_name == login_name:
            return await self.request("GET", "/api/auth/me")
        await self.logout()
        result = await self.request(
            "POST", "/api/auth/login", {"login_name": login_name, "password": password}
        )
        self.login_name = login_name
        return result

    async def logout(self):
        if self.login_name:
            await self.request("POST", "/api/auth/logout", {})
            self.login_name = None

    async def list_all(self, path, **params):
        """分页读取公开列表，资源定位使用精确字段而非模糊搜索首条。"""
        page = 1
        items = []
        while True:
            result = await self.request(
                "GET", path, params=params | {"page": page, "page_size": 100}
            )
            items.extend(result["items"])
            if len(items) >= result["total"]:
                return items
            page += 1
