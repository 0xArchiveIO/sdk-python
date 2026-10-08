"""Background subscribe and unsubscribe sends: flushed by disconnect(), and
quiet when the connection is already gone."""

import asyncio
import json

import pytest

pytest.importorskip("websockets")

from websockets.exceptions import ConnectionClosedError  # noqa: E402
from websockets.protocol import State  # noqa: E402

from oxarchive.websocket import OxArchiveWs, WsOptions  # noqa: E402


class FakeConnection:
    def __init__(self, fail_with=None):
        self.state = State.OPEN
        self.sent = []
        self.closed = False
        self.fail_with = fail_with

    async def send(self, text):
        await asyncio.sleep(0.01)
        if self.fail_with is not None:
            raise self.fail_with
        if self.closed:
            raise ConnectionClosedError(None, None)
        self.sent.append(json.loads(text))

    async def close(self, code=1000, reason=""):
        self.closed = True
        self.state = State.CLOSED


def client(conn):
    ws = OxArchiveWs(WsOptions(api_key="0xa_" + "0" * 64))
    ws._ws = conn
    return ws


def unretrieved(loop_errors):
    return [e for e in loop_errors if "exception was never retrieved" in str(e.get("message", ""))]


@pytest.mark.asyncio
async def test_unsubscribe_then_disconnect_sends_the_unsubscribe_first():
    loop = asyncio.get_running_loop()
    errors = []
    loop.set_exception_handler(lambda _loop, ctx: errors.append(ctx))
    conn = FakeConnection()
    ws = client(conn)
    ws.subscribe_mempool("BTC")
    ws.unsubscribe_mempool("BTC")
    await ws.disconnect()
    assert [m["op"] for m in conn.sent] == ["subscribe", "unsubscribe"]
    assert conn.closed
    assert not ws._pending_sends
    await asyncio.sleep(0.05)
    assert not unretrieved(errors)


@pytest.mark.asyncio
async def test_a_send_that_finds_the_connection_closed_is_dropped_quietly():
    loop = asyncio.get_running_loop()
    errors = []
    loop.set_exception_handler(lambda _loop, ctx: errors.append(ctx))
    ws = client(FakeConnection(fail_with=ConnectionClosedError(None, None)))
    seen = []
    ws.on_error(seen.append)
    ws.unsubscribe("trades", "BTC")
    await asyncio.sleep(0.05)
    import gc

    gc.collect()
    await asyncio.sleep(0)
    assert seen == []
    assert not ws._pending_sends
    assert not unretrieved(errors)


@pytest.mark.asyncio
async def test_any_other_send_failure_reaches_the_error_handler():
    boom = RuntimeError("boom")
    ws = client(FakeConnection(fail_with=boom))
    seen = []
    ws.on_error(seen.append)
    ws.subscribe("trades", "BTC")
    await asyncio.sleep(0.05)
    assert seen == [boom]
    assert not ws._pending_sends
