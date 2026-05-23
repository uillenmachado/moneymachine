"""Cliente REST mínimo da Binance Spot — assinatura HMAC SHA-256.

Implementa apenas os endpoints necessários para o OMS:
- placeOrder (NEW)
- cancelOrder
- queryOrder
- openOrders
- ping/time (health)

Documentação: https://binance-docs.github.io/apidocs/spot/en/

Compliance: nunca loga API key/secret. Toda chamada autenticada usa
`SecretStr.get_secret_value()` no momento da assinatura — segredo nunca
sai do escopo da função.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from pydantic import SecretStr

logger = structlog.get_logger(__name__)

_MAINNET_URL = "https://api.binance.com"
_TESTNET_URL = "https://testnet.binance.vision"
_RECV_WINDOW_MS = 5000


class BinanceRESTError(RuntimeError):
    """Erro estruturado retornado pela API REST da Binance."""

    def __init__(self, code: int, message: str, http_status: int) -> None:
        super().__init__(f"binance error {code} ({http_status}): {message}")
        self.code = code
        self.message = message
        self.http_status = http_status


class BinanceRESTClient:
    """Cliente HTTPX assíncrono para Binance Spot."""

    def __init__(
        self,
        api_key: SecretStr,
        api_secret: SecretStr,
        *,
        testnet: bool = True,
        timeout_s: float = 5.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = _TESTNET_URL if testnet else _MAINNET_URL
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={"X-MBX-APIKEY": api_key.get_secret_value()},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> BinanceRESTClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    # ─────────── Public endpoints ───────────

    async def ping(self) -> bool:
        r = await self._client.get("/api/v3/ping")
        return r.status_code == 200

    async def server_time(self) -> int:
        r = await self._client.get("/api/v3/time")
        r.raise_for_status()
        return int(r.json()["serverTime"])

    # ─────────── Signed endpoints ───────────

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None = None,
        client_order_id: str | None = None,
        time_in_force: str | None = "GTC",
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            params["price"] = price
        if client_order_id is not None:
            params["newClientOrderId"] = client_order_id
        if order_type in {"LIMIT", "LIMIT_MAKER"} and order_type != "LIMIT_MAKER":
            params["timeInForce"] = time_in_force or "GTC"
        result = await self._signed_request("POST", "/api/v3/order", params)
        return dict(result)

    async def cancel_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> dict[str, Any]:
        if client_order_id is None and order_id is None:
            msg = "client_order_id ou order_id é obrigatório"
            raise ValueError(msg)
        params: dict[str, str] = {"symbol": symbol}
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        if order_id is not None:
            params["orderId"] = str(order_id)
        result = await self._signed_request("DELETE", "/api/v3/order", params)
        return dict(result)

    async def cancel_all(self, symbol: str) -> list[dict[str, Any]]:
        result = await self._signed_request("DELETE", "/api/v3/openOrders", {"symbol": symbol})
        return list(result) if isinstance(result, list) else [result]

    async def query_order(
        self,
        *,
        symbol: str,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> dict[str, Any]:
        if client_order_id is None and order_id is None:
            msg = "client_order_id ou order_id é obrigatório"
            raise ValueError(msg)
        params: dict[str, str] = {"symbol": symbol}
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        if order_id is not None:
            params["orderId"] = str(order_id)
        result = await self._signed_request("GET", "/api/v3/order", params)
        return dict(result)

    async def open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if symbol is not None:
            params["symbol"] = symbol
        result = await self._signed_request("GET", "/api/v3/openOrders", params)
        return list(result) if isinstance(result, list) else [result]

    # ─────────── Internals ───────────

    async def _signed_request(self, method: str, path: str, params: dict[str, str]) -> Any:
        params["timestamp"] = str(int(time.time() * 1000))
        params["recvWindow"] = str(_RECV_WINDOW_MS)
        query = urllib.parse.urlencode(params)
        signature = hmac.new(
            self._api_secret.get_secret_value().encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        url = f"{path}?{query}&signature={signature}"
        try:
            r = await self._client.request(method, url)
        except httpx.HTTPError as exc:
            logger.warning("binance_rest_http_error", method=method, path=path, exc=str(exc))
            raise
        if r.status_code >= 400:
            try:
                body = r.json()
                code = int(body.get("code", -1))
                message = str(body.get("msg", "unknown"))
            except (ValueError, TypeError, KeyError):
                code = -1
                message = r.text[:200]
            raise BinanceRESTError(code, message, r.status_code)
        return r.json()


__all__ = ["BinanceRESTClient", "BinanceRESTError"]
