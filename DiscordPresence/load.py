#
# KodeBlox Copyright 2019 Sayak Mukhopadhyay
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http: //www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Community patch (3.3.0) for EDMC 6.x:
#  * Uses EDMC 6's translation API (the old l10n.Translations singleton was removed).
#  * Talks to Discord over its local IPC pipe in pure Python instead of the 32-bit
#    discord_game_sdk.dll, which cannot load in EDMC 6's 64-bit build.
#  * Initialises its state at startup, so journal events never hit missing attributes.
#  * Uses Thread(daemon=True) instead of the deprecated setDaemon().
#

import json
import logging
import os
import queue
import struct
import sys
import threading
import time
import tkinter as tk
import uuid

import myNotebook as nb
from config import appname, config

plugin_name = os.path.basename(os.path.dirname(__file__))
logger = logging.getLogger(f'{appname}.{plugin_name}')

# Translations: EDMC 6 exposes l10n.translations.tl(); older builds had l10n.Translations.translate.
try:
    from l10n import translations as _tr

    def _(text):
        return _tr.tl(text, context=__file__)
except ImportError:  # pre-6.0 EDMC
    import l10n

    def _(text):
        return l10n.Translations.translate(text, context=__file__)

CLIENT_ID = '386149818227097610'
VERSION = '3.3.0'

OP_HANDSHAKE, OP_FRAME, OP_CLOSE = 0, 1, 2
MAX_FRAME_BYTES = 1024 * 1024  # refuse absurd frames from whatever is on the other end of the pipe
IO_TIMEOUT = 10  # seconds (Linux/macOS sockets)

this = sys.modules[__name__]
this.presence_state = _('Connecting CMDR Interface')
this.presence_details = ''
this.time_start = int(time.time())
this.planet = '<Hidden>'
this.disablePresence = None
this.worker = None


class DiscordIPC:
    """Minimal Discord RPC client over the local IPC pipe / socket."""

    def __init__(self, client_id):
        self.client_id = client_id
        self.pipe = None
        self.sock = None

    # --- transport ---------------------------------------------------------
    @staticmethod
    def _unix_candidates():
        base_dirs = [os.environ.get(k) for k in ('XDG_RUNTIME_DIR', 'TMPDIR', 'TMP', 'TEMP')] + ['/tmp']
        subdirs = ['', 'app/com.discordapp.Discord', 'app/com.discordapp.DiscordCanary',
                   '.flatpak/com.discordapp.Discord/xdg-run', 'snap.discord']
        for base in filter(None, base_dirs):
            for sub in subdirs:
                for i in range(10):
                    yield os.path.join(base, sub, f'discord-ipc-{i}')

    def connect(self):
        if sys.platform == 'win32':
            for i in range(10):
                try:
                    self.pipe = open(rf'\\?\pipe\discord-ipc-{i}', 'w+b', buffering=0)
                    break
                except OSError:
                    continue
            else:
                raise ConnectionError('Discord is not running (no IPC pipe found)')
        else:
            import socket
            for path in self._unix_candidates():
                try:
                    # Only talk to a socket owned by this user: /tmp is shared, so another
                    # account could otherwise plant a fake "discord-ipc-0" there.
                    if os.stat(path).st_uid != os.getuid():
                        continue
                except OSError:
                    continue
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(IO_TIMEOUT)
                try:
                    s.connect(path)
                    self.sock = s
                    break
                except OSError:
                    s.close()
            else:
                raise ConnectionError('Discord is not running (no IPC socket found)')

        self._send(OP_HANDSHAKE, {'v': 1, 'client_id': self.client_id})
        op, data = self._recv()
        if op == OP_CLOSE or data.get('evt') != 'READY':
            raise ConnectionError(f'Discord handshake failed: {data}')
        logger.info('Connected to Discord')

    def _write(self, b):
        if self.pipe:
            self.pipe.write(b)
            self.pipe.flush()
        else:
            self.sock.sendall(b)

    def _read(self, n):
        buf = b''
        while len(buf) < n:
            chunk = self.pipe.read(n - len(buf)) if self.pipe else self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError('Discord closed the connection')
            buf += chunk
        return buf

    def _send(self, op, payload):
        data = json.dumps(payload).encode('utf-8')
        self._write(struct.pack('<II', op, len(data)) + data)

    def _recv(self):
        op, length = struct.unpack('<II', self._read(8))
        if length > MAX_FRAME_BYTES:
            raise ConnectionError(f'Discord IPC frame too large ({length} bytes)')
        data = json.loads(self._read(length).decode('utf-8'))
        if not isinstance(data, dict):
            raise ConnectionError('Unexpected Discord IPC payload')
        return op, data

    # --- API ---------------------------------------------------------------
    def set_activity(self, activity):
        self._send(OP_FRAME, {
            'cmd': 'SET_ACTIVITY',
            'args': {'pid': os.getpid(), 'activity': activity},
            'nonce': str(uuid.uuid4()),
        })
        _, data = self._recv()
        if data.get('evt') == 'ERROR':
            logger.warning(f'Discord rejected activity: {data.get("data")}')

    def close(self):
        try:
            self._send(OP_CLOSE, {})
        except Exception:
            pass
        for h in (self.pipe, self.sock):
            try:
                if h:
                    h.close()
            except Exception:
                pass
        self.pipe = self.sock = None


class PresenceWorker(threading.Thread):
    """Owns the Discord connection; reconnects automatically if Discord restarts."""

    RETRY_SECONDS = 15

    def __init__(self):
        super().__init__(name='DiscordPresence', daemon=True)
        self.updates = queue.Queue()
        self.stopping = threading.Event()

    def push(self, activity):
        self.updates.put(activity)

    def stop(self):
        self.stopping.set()
        self.updates.put(None)

    def run(self):
        ipc = None
        latest = None
        dirty = False
        while not self.stopping.is_set():
            # Wait for a new activity, or time out so we retry a lost connection.
            try:
                item = self.updates.get(timeout=self.RETRY_SECONDS)
                if item is None and self.stopping.is_set():
                    break
                latest, dirty = item, True
                while True:  # collapse a burst of updates into the newest one
                    item = self.updates.get_nowait()
                    if item is None and self.stopping.is_set():
                        break
                    latest = item
            except queue.Empty:
                pass
            if self.stopping.is_set():
                break

            if ipc is None:
                try:
                    ipc = DiscordIPC(CLIENT_ID)
                    ipc.connect()
                    dirty = True  # re-send current presence after (re)connect
                except Exception as e:
                    logger.debug(f'Discord not reachable yet: {e}')
                    ipc = None
                    continue

            if dirty:
                try:
                    ipc.set_activity(latest)  # None clears the presence
                    dirty = False
                except Exception as e:
                    logger.info(f'Lost connection to Discord, will retry: {e}')
                    ipc.close()
                    ipc = None

        if ipc:
            try:
                ipc.set_activity(None)
            except Exception:
                pass
            ipc.close()


def _field(text):
    """Discord only accepts 2-128 character strings for state/details."""
    text = str(text or '').strip()
    if len(text) < 2:
        return None
    return text if len(text) <= 128 else text[:127] + '…'


def build_activity():
    if config.get_int('disable_presence') != 0:
        return None
    activity = {
        'state': _field(this.presence_state),
        'details': _field(this.presence_details),
        'timestamps': {'start': this.time_start},
    }
    return {k: v for k, v in activity.items() if v is not None}


def update_presence():
    if this.worker:
        this.worker.push(build_activity())


def plugin_start3(plugin_dir):
    this.worker = PresenceWorker()
    this.worker.start()
    update_presence()
    return plugin_name


def plugin_stop():
    if this.worker:
        this.worker.stop()
        this.worker.join(timeout=3)
        this.worker = None


def plugin_prefs(parent, cmdr, is_beta):
    this.disablePresence = tk.IntVar(value=config.get_int('disable_presence'))
    frame = nb.Frame(parent)
    nb.Checkbutton(frame, text='Disable Presence', variable=this.disablePresence).grid()
    nb.Label(frame, text=f'Version {VERSION}').grid(padx=10, pady=10, sticky=tk.W)
    return frame


def prefs_changed(cmdr, is_beta):
    if this.disablePresence is not None:
        config.set('disable_presence', this.disablePresence.get())
    update_presence()


def journal_entry(cmdr, is_beta, system, station, entry, state):
    event = entry.get('event')
    system = system or state.get('SystemName') or entry.get('StarSystem') or '<Unknown>'
    in_system = _('In system {system}').format(system=system)
    presence_state = this.presence_state
    presence_details = this.presence_details
    planet = this.planet

    if event in ('StartUp', 'Location', 'LoadGame'):
        if event == 'LoadGame' and not state.get('SystemName'):
            pass  # location not known yet; wait for Location
        else:
            presence_state = in_system
            presence_details = (_('Docked at {station}').format(station=station)
                                if station else _('Flying in normal space'))
    elif event == 'StartJump':
        presence_state = _('Jumping')
        if entry.get('JumpType') == 'Hyperspace':
            presence_details = _('Jumping to system {system}').format(system=entry.get('StarSystem', ''))
        elif entry.get('JumpType') == 'Supercruise':
            presence_details = _('Preparing for supercruise')
    elif event in ('SupercruiseEntry', 'FSDJump'):
        presence_state = in_system
        presence_details = _('Supercruising')
    elif event == 'SupercruiseExit':
        presence_state = in_system
        presence_details = _('Flying in normal space')
    elif event == 'Docked':
        presence_state = in_system
        presence_details = _('Docked at {station}').format(station=station or entry.get('StationName', ''))
    elif event == 'Undocked':
        presence_state = in_system
        presence_details = _('Flying near {station}').format(station=entry.get('StationName', ''))
    elif event in ('DockingCancelled', 'DockingTimeout'):
        presence_details = _('Flying near {station}').format(station=entry.get('StationName', ''))
    elif event == 'ShutDown' or (event == 'Music' and entry.get('MusicTrack') == 'MainMenu'):
        presence_state = _('Connecting CMDR Interface')
        presence_details = ''
    elif event == 'ApproachBody':
        planet = entry.get('Body', planet)
        presence_details = _('Approaching {body}').format(body=planet)
    elif event == 'Touchdown' and entry.get('PlayerControlled', True):
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
    elif event == 'DockSRV':
        presence_details = _('Landed on {body}').format(body=planet)

    this.planet = planet
    if presence_state != this.presence_state or presence_details != this.presence_details:
        this.presence_state = presence_state
        this.presence_details = presence_details
        update_presence()
