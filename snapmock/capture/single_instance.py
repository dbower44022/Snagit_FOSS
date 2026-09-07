"""The single-instance channel (PRD 3.5).

A local socket named for the current user. The running instance listens on
it; a second launch forwards its command line and exits.
"""

from __future__ import annotations

import getpass
import json
import logging

from PyQt6.QtCore import QCoreApplication, QDeadlineTimer, QEventLoop, QObject, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger("snapmock.capture")

FORWARD_TIMEOUT_MS = 100
PUMP_SLICE_MS = 10


def default_channel_name() -> str:
    try:
        user = getpass.getuser()
    except (OSError, KeyError):  # pragma: no cover - no account name available
        user = "user"
    safe = "".join(c if c.isalnum() else "_" for c in user)
    return f"snapmock-{safe}"


def _drain_write_queue(socket: QLocalSocket, timeout_ms: int) -> bool:
    """Flush the socket's write queue; True when it emptied within *timeout_ms*.

    ``waitForBytesWritten`` is not enough on a Windows named pipe: it returns
    False with every byte still queued, because the write completes only once
    the event loop runs. So pump the loop until the queue drains. There is no
    loop to pump before :class:`QCoreApplication` exists, which is why
    ``app.py`` creates the application before it forwards.
    """
    if socket.bytesToWrite() == 0:
        return True
    socket.waitForBytesWritten(timeout_ms)
    if socket.bytesToWrite() == 0:
        return True
    app = QCoreApplication.instance()
    if app is None:  # pragma: no cover - app.py always creates one first
        return False
    deadline = QDeadlineTimer(timeout_ms)
    while socket.bytesToWrite() > 0 and not deadline.hasExpired():
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, PUMP_SLICE_MS)
    return socket.bytesToWrite() == 0


def try_forward(
    argv: list[str], name: str | None = None, timeout_ms: int = FORWARD_TIMEOUT_MS
) -> bool:
    """Send *argv* to a running instance. True when an instance accepted it."""
    socket = QLocalSocket()
    socket.connectToServer(name or default_channel_name())
    if not socket.waitForConnected(timeout_ms):
        return False
    payload = json.dumps({"argv": argv}).encode("utf-8") + b"\n"
    if socket.write(payload) != len(payload):
        return False
    ok = _drain_write_queue(socket, timeout_ms)
    socket.disconnectFromServer()
    if socket.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        socket.waitForDisconnected(timeout_ms)
    return ok


class SingleInstanceChannel(QObject):
    """Listens for forwarded command lines.

    Signals
    -------
    command_received(object)
        A forwarded command line arrived (list[str]).
    """

    command_received = pyqtSignal(object)

    def __init__(self, name: str | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._name = name or default_channel_name()
        self._server: QLocalServer | None = None
        self._buffers: dict[int, bytes] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_listening(self) -> bool:
        return self._server is not None and self._server.isListening()

    def listen(self) -> bool:
        """Start listening. A stale endpoint is removed and creation retried once."""
        server = QLocalServer(self)
        if not server.listen(self._name):
            QLocalServer.removeServer(self._name)
            if not server.listen(self._name):
                log.warning(
                    "Single-instance channel %s unavailable: %s",
                    self._name,
                    server.errorString(),
                )
                server.deleteLater()
                return False
        server.newConnection.connect(self._on_new_connection)
        self._server = server
        return True

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            QLocalServer.removeServer(self._name)
            self._server = None

    def _on_new_connection(self) -> None:
        if self._server is None:
            return
        while True:
            socket = self._server.nextPendingConnection()
            if socket is None:
                break
            socket.readyRead.connect(lambda s=socket: self._read(s))
            socket.disconnected.connect(lambda s=socket: self._finish(s))
            if socket.bytesAvailable():
                self._read(socket)

    def _read(self, socket: QLocalSocket) -> None:
        key = id(socket)
        self._buffers[key] = self._buffers.get(key, b"") + bytes(socket.readAll().data())
        while b"\n" in self._buffers[key]:
            line, rest = self._buffers[key].split(b"\n", 1)
            self._buffers[key] = rest
            self._dispatch(line)

    def _finish(self, socket: QLocalSocket) -> None:
        key = id(socket)
        leftover = self._buffers.pop(key, b"")
        if leftover.strip():
            self._dispatch(leftover)
        socket.deleteLater()

    def _dispatch(self, line: bytes) -> None:
        try:
            data = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return
        argv = data.get("argv") if isinstance(data, dict) else None
        if isinstance(argv, list):
            self.command_received.emit([str(a) for a in argv])
