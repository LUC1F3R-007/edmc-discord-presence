#
# LUC1F3R007, circa 2026
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# The original plugin has not been updated since 2021, and has since stopped working with EDMC as of version 6.x.x.
# I have updated the code base, and verified fuctionality of the plugin.

from dataclasses import dataclass, field
import json
import logging
import os
import queue
import socket
import struct
import sys
import threading
import time
import tkinter as tk
from typing import Any
import uuid

from config import appname, config
from l10n import translations as _tr
import myNotebook as nb

PLUGIN_NAME = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f'{appname}.{PLUGIN_NAME}')

CLIENT_ID = '1574910179097583697'
VERSION = '3.3.0'

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2

MAX_FRAME_BYTES = 1024 * 1024
IO_TIMEOUT_SECONDS = 10
RETRY_INTERVAL_SECONDS = 15
MAX_FIELD_LENGTH = 128
MIN_FIELD_LENGTH = 2
IPC_PIPE_RANGE = range(10)

UNIX_SOCKET_ENV_VARS = ('XDG_RUNTIME_DIR', 'TMPDIR', 'TMP', 'TEMP')
UNIX_SOCKET_SUBDIRS = (
    '',
    'app/com.discordapp.Discord',
    'app/com.discordapp.DiscordCanary',
    '.flatpak/com.discordapp.Discord/xdg-run',
    'snap.discord',
)


def _(text: str) -> str:
    return _tr.tl(text, context=__file__)


@dataclass
class PluginState:
    presence_state: str = field(default_factory=lambda: _('Connecting CMDR Interface'))
    presence_details: str = ''
    time_start: int = field(default_factory=lambda: int(time.time()))
    planet: str = '<Hidden>'
    disable_presence_var: tk.IntVar | None = None
    worker: 'PresenceWorker | None' = None


_state = PluginState()


class DiscordIPC:
    """Minimal Discord Rich Presence client over a local IPC pipe or Unix socket."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.pipe: Any = None
        self.sock: socket.socket | None = None

    @property
    def is_connected(self) -> bool:
        return self.pipe is not None or self.sock is not None

    @staticmethod
    def _unix_socket_candidates() -> list[str]:
        base_dirs = [os.environ.get(var) for var in UNIX_SOCKET_ENV_VARS] + ['/tmp']
        return [
            os.path.join(base, sub, f'discord-ipc-{idx}')
            for base in filter(None, base_dirs)
            for sub in UNIX_SOCKET_SUBDIRS
            for idx in IPC_PIPE_RANGE
        ]

    def _connect_windows(self) -> None:
        for idx in IPC_PIPE_RANGE:
            pipe_path = rf'\\?\pipe\discord-ipc-{idx}'
            try:
                self.pipe = open(pipe_path, 'w+b', buffering=0)
                return
            except OSError:
                continue
        raise ConnectionError('Discord is not running (no IPC pipe found)')

    def _connect_unix(self) -> None:
        uid = os.getuid()
        for path in self._unix_socket_candidates():
            try:
                # /tmp is shared, so ignore sockets not owned by the current user.
                if os.stat(path).st_uid != uid:
                    continue
            except OSError:
                continue

            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(IO_TIMEOUT_SECONDS)
            try:
                sock.connect(path)
                self.sock = sock
                return
            except OSError:
                sock.close()

        raise ConnectionError('Discord is not running (no IPC socket found)')

    def connect(self) -> None:
        if sys.platform == 'win32':
            self._connect_windows()
        else:
            self._connect_unix()

        try:
            self._send(OP_HANDSHAKE, {'v': 1, 'client_id': self.client_id})
            op, data = self._recv()
            if op == OP_CLOSE or data.get('evt') != 'READY':
                raise ConnectionError(f'Discord handshake failed: {data}')
        except Exception:
            self.close()
            raise

        logger.info('Connected to Discord')

    def _write(self, payload: bytes) -> None:
        if self.pipe is not None:
            self.pipe.write(payload)
            self.pipe.flush()
        elif self.sock is not None:
            self.sock.sendall(payload)
        else:
            raise ConnectionError('Discord IPC transport is not open')

    def _read(self, num_bytes: int) -> bytes:
        chunks: list[bytes] = []
        remaining = num_bytes
        while remaining > 0:
            if self.pipe is not None:
                chunk = self.pipe.read(remaining)
            elif self.sock is not None:
                chunk = self.sock.recv(remaining)
            else:
                raise ConnectionError('Discord IPC transport is not open')

            if not chunk:
                raise ConnectionError('Discord closed the connection')
            chunks.append(chunk)
            remaining -= len(chunk)
        return b''.join(chunks)

    def _send(self, op: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode('utf-8')
        header = struct.pack('<II', op, len(encoded))
        self._write(header + encoded)

    def _recv(self) -> tuple[int, dict[str, Any]]:
        op, length = struct.unpack('<II', self._read(8))
        if length > MAX_FRAME_BYTES:
            raise ConnectionError(f'Discord IPC frame too large ({length} bytes)')
        decoded = json.loads(self._read(length).decode('utf-8'))
        if not isinstance(decoded, dict):
            raise ConnectionError('Unexpected Discord IPC payload')
        return op, decoded

    def set_activity(self, activity: dict[str, Any] | None) -> None:
        self._send(
            OP_FRAME,
            {
                'cmd': 'SET_ACTIVITY',
                'args': {'pid': os.getpid(), 'activity': activity},
                'nonce': str(uuid.uuid4()),
            },
        )
        _, data = self._recv()
        if data.get('evt') == 'ERROR':
            logger.warning('Discord rejected activity: %s', data.get('data'))

    def close(self) -> None:
        if self.is_connected:
            try:
                self._send(OP_CLOSE, {})
            except Exception:
                pass

        for handle in (self.pipe, self.sock):
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass

        self.pipe = None
        self.sock = None


class PresenceWorker(threading.Thread):
    """Owns the Discord IPC session and retries automatically if Discord restarts."""

    def __init__(self) -> None:
        super().__init__(name='DiscordPresence', daemon=True)
        self._updates: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._stopping = threading.Event()

    def push(self, activity: dict[str, Any] | None) -> None:
        self._updates.put(activity)

    def stop(self) -> None:
        self._stopping.set()
        self._updates.put(None)

    def _drain_latest_update(self) -> tuple[dict[str, Any] | None, bool]:
        try:
            latest = self._updates.get(timeout=RETRY_INTERVAL_SECONDS)
        except queue.Empty:
            return None, False

        if self._stopping.is_set():
            return None, False

        while not self._stopping.is_set():
            try:
                latest = self._updates.get_nowait()
            except queue.Empty:
                break

        return (None, False) if self._stopping.is_set() else (latest, True)

    @staticmethod
    def _ensure_connected(ipc: DiscordIPC | None) -> DiscordIPC | None:
        if ipc is not None:
            return ipc
        try:
            client = DiscordIPC(CLIENT_ID)
            client.connect()
            return client
        except Exception as exc:
            logger.debug('Discord not reachable yet: %s', exc)
            return None

    def run(self) -> None:
        ipc: DiscordIPC | None = None
        latest_activity: dict[str, Any] | None = None
        dirty = False

        while not self._stopping.is_set():
            queued_activity, has_update = self._drain_latest_update()
            if self._stopping.is_set():
                break
            if has_update:
                latest_activity = queued_activity
                dirty = True

            previous_ipc = ipc
            ipc = self._ensure_connected(ipc)
            if ipc is None:
                continue
            if previous_ipc is None:
                dirty = True

            if dirty:
                try:
                    ipc.set_activity(latest_activity)
                    dirty = False
                except Exception as exc:
                    logger.info('Lost connection to Discord, will retry: %s', exc)
                    ipc.close()
                    ipc = None

        if ipc is not None:
            try:
                ipc.set_activity(None)
            except Exception:
                pass
            ipc.close()


def _sanitize_field(text: Any) -> str | None:
    """Discord requires state and details strings to be between 2 and 128 characters."""
    cleaned = str(text or '').strip()
    if len(cleaned) < MIN_FIELD_LENGTH:
        return None
    if len(cleaned) > MAX_FIELD_LENGTH:
        return f'{cleaned[:MAX_FIELD_LENGTH - 1]}…'
    return cleaned


def build_activity() -> dict[str, Any] | None:
    if config.get_int('disable_presence') != 0:
        return None

    raw_activity: dict[str, Any] = {
        'state': _sanitize_field(_state.presence_state),
        'details': _sanitize_field(_state.presence_details),
        'timestamps': {'start': _state.time_start},
    }

    return {key: val for key, val in raw_activity.items() if val is not None}


def update_presence() -> None:
    if _state.worker is not None:
        _state.worker.push(build_activity())


def _compute_presence_from_event(
    event: str | None,
    system: str,
    station: str | None,
    entry: dict[str, Any],
    edmc_state: dict[str, Any],
    current_state: str,
    current_details: str,
    current_planet: str,
) -> tuple[str, str, str]:
    in_system = _('In system {system}').format(system=system)
    presence_state = current_state
    presence_details = current_details
    planet = current_planet

    if event in ('StartUp', 'Location', 'LoadGame'):
        if not (event == 'LoadGame' and not edmc_state.get('SystemName')):
            presence_state = in_system
            presence_details = (
                _('Docked at {station}').format(station=station)
                if station
                else _('Flying in normal space')
            )
    elif event == 'StartJump':
        presence_state = _('Jumping')
        jump_type = entry.get('JumpType')
        if jump_type == 'Hyperspace':
            presence_details = _('Jumping to system {system}').format(
                system=entry.get('StarSystem', '')
            )
        elif jump_type == 'Supercruise':
            presence_details = _('Preparing for supercruise')
    elif event in ('SupercruiseEntry', 'FSDJump'):
        presence_state = in_system
        presence_details = _('Supercruising')
    elif event == 'SupercruiseExit':
        presence_state = in_system
        presence_details = _('Flying in normal space')
    elif event == 'Docked':
        presence_state = in_system
        presence_details = _('Docked at {station}').format(
            station=station or entry.get('StationName', '')
        )
    elif event in ('Undocked', 'DockingCancelled', 'DockingTimeout'):
        if event == 'Undocked':
            presence_state = in_system
        presence_details = _('Flying near {station}').format(
            station=entry.get('StationName', '')
        )
    elif event == 'ShutDown' or (
        event == 'Music' and entry.get('MusicTrack') == 'MainMenu'
    ):
        presence_state = _('Connecting CMDR Interface')
        presence_details = ''
    elif event == 'ApproachBody':
        planet = entry.get('Body', planet)
        presence_details = _('Approaching {body}').format(body=planet)
    elif event in ('Touchdown', 'DockSRV'):
        if event != 'Touchdown' or entry.get('PlayerControlled', True):
            presence_details = _('Landed on {body}').format(body=planet)
    elif event == 'Liftoff':
        if entry.get('PlayerControlled', True):
            presence_details = _('Flying around {body}').format(body=planet)
        else:
            presence_details = _('In SRV on {body}, ship in orbit').format(body=planet)
    elif event == 'LeaveBody':
        presence_details = _('Supercruising')
    elif event == 'LaunchSRV':
        presence_details = _('In SRV on {body}').format(body=planet)

    return presence_state, presence_details, planet


def plugin_start3(plugin_dir: str) -> str:
    worker = PresenceWorker()
    _state.worker = worker
    worker.start()
    update_presence()
    return PLUGIN_NAME


def plugin_stop() -> None:
    worker = _state.worker
    _state.worker = None
    if worker is not None:
        worker.stop()
        worker.join(timeout=3)


def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> nb.Frame:
    _state.disable_presence_var = tk.IntVar(value=config.get_int('disable_presence'))
    frame = nb.Frame(parent)
    nb.Checkbutton(
        frame,
        text='Disable Presence',
        variable=_state.disable_presence_var,
    ).grid()
    nb.Label(frame, text=f'Version {VERSION}').grid(padx=10, pady=10, sticky=tk.W)
    return frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    if _state.disable_presence_var is not None:
        config.set('disable_presence', _state.disable_presence_var.get())
    update_presence()


def journal_entry(
    cmdr: str,
    is_beta: bool,
    system: str | None,
    station: str | None,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> None:
    resolved_system = (
        system or state.get('SystemName') or entry.get('StarSystem') or '<Unknown>'
    )
    new_state, new_details, new_planet = _compute_presence_from_event(
        event=entry.get('event'),
        system=resolved_system,
        station=station,
        entry=entry,
        edmc_state=state,
        current_state=_state.presence_state,
        current_details=_state.presence_details,
        current_planet=_state.planet,
    )

    changed = (
        new_state != _state.presence_state or new_details != _state.presence_details
    )
    _state.planet = new_planet
    _state.presence_state = new_state
    _state.presence_details = new_details

    if changed:
        update_presence()