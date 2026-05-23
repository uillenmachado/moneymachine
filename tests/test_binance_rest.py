"""Testes do BinanceRESTClient — usa httpx.MockTransport (zero rede)."""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse

import httpx
import pytest
from pydantic import SecretStr

from oms.binance_rest import BinanceRESTClient, BinanceRESTError

pytestmark = pytest.mark.unit

_KEY = SecretStr("test-api-key")
_SECRET = SecretStr("test-secret")


def _mock_transport(handler: object) -> httpx.MockTransport:
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


def _client_with_transport(handler: object) -> BinanceRESTClient:
    cli = BinanceRESTClient(_KEY, _SECRET, testnet=True)
    # Substitui o transport interno do AsyncClient.
    cli._client = httpx.AsyncClient(
        base_url="https://testnet.binance.vision",
        transport=_mock_transport(handler),
        headers={"X-MBX-APIKEY": _KEY.get_secret_value()},
    )
    return cli


async def test_ping_ok() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    cli = _client_with_transport(handler)
    try:
        assert await cli.ping() is True
    finally:
        await cli.close()


async def test_place_order_signs_request() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("X-MBX-APIKEY", "")
        return httpx.Response(200, json={"orderId": 1, "status": "NEW", "executedQty": "0"})

    cli = _client_with_transport(handler)
    try:
        resp = await cli.place_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="LIMIT",
            quantity="0.01",
            price="50000",
            client_order_id="test-1",
        )
    finally:
        await cli.close()

    assert resp["orderId"] == 1
    assert captured["api_key"] == "test-api-key"
    # Confere assinatura na URL.
    parsed = urllib.parse.urlparse(captured["url"])
    qs = dict(urllib.parse.parse_qsl(parsed.query))
    sig = qs.pop("signature")
    expected_query = urllib.parse.urlencode(qs)
    expected = hmac.new(b"test-secret", expected_query.encode(), hashlib.sha256).hexdigest()
    assert sig == expected
    assert qs["symbol"] == "BTCUSDT"
    assert qs["timeInForce"] == "GTC"


async def test_rest_error_parsed() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -1013, "msg": "filter failure"})

    cli = _client_with_transport(handler)
    try:
        with pytest.raises(BinanceRESTError) as exc_info:
            await cli.place_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                quantity="0.01",
                price="50000",
            )
    finally:
        await cli.close()
    assert exc_info.value.code == -1013
    assert exc_info.value.http_status == 400
    assert "filter failure" in exc_info.value.message


async def test_cancel_requires_id() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    cli = _client_with_transport(handler)
    try:
        with pytest.raises(ValueError, match="client_order_id"):
            await cli.cancel_order(symbol="BTCUSDT")
    finally:
        await cli.close()


async def test_open_orders_returns_list() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"orderId": 1}, {"orderId": 2}])

    cli = _client_with_transport(handler)
    try:
        result = await cli.open_orders("BTCUSDT")
    finally:
        await cli.close()
    assert len(result) == 2
