"""The web server behind Zippy's touchscreen page. Plain FastAPI, no ROS.

GET  /              the page (web/index.html)
GET  /api/status    the latest status as JSON
POST /api/command   {"cmd": "go", "place": "bedroom_a"}
WS   /ws            pushes every new status to the page; the page sends commands back
"""
import asyncio
import json
import os
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

COMMANDS = {'go', 'done', 'stop', 'home', 'clear'}


OFFLINE = {'state': 'offline', 'message': "Waiting for Zippy's brain...", 'places': []}


class Hub:
    """Holds the latest status. The ROS side writes it, the web side reads it.
    The brain sends a status at least once a second; after 3 s of silence the page shows offline."""

    def __init__(self):
        self._status = None
        self._last = 0.0
        self.version = 0

    def update(self, status_json):
        self._status = json.loads(status_json)
        self._last = time.monotonic()
        self.version += 1

    def alive(self):
        return self._status is not None and time.monotonic() - self._last < 3.0

    @property
    def status(self):
        if not self.alive():
            return dict(OFFLINE, places=(self._status or {}).get('places', []))
        return self._status


class Command(BaseModel):
    cmd: str
    place: Optional[str] = None


def make_app(hub, send_command, web_dir):
    """send_command(cmd, place) passes a command on to the brain."""
    app = FastAPI(title='Zippy')

    def handle(cmd, place):
        if not isinstance(cmd, str) or cmd not in COMMANDS:
            return {'ok': False, 'error': f'unknown command {cmd}'}
        if place is not None and not isinstance(place, str):
            return {'ok': False, 'error': 'place must be a name'}
        send_command(cmd, place)
        return {'ok': True}

    @app.get('/api/status')
    def get_status():
        return hub.status

    @app.post('/api/command')
    def post_command(c: Command):
        return handle(c.cmd, c.place)

    @app.websocket('/ws')
    async def ws(socket: WebSocket):
        await socket.accept()
        seen = None
        try:
            while True:
                now = (hub.version, hub.alive())
                if now != seen:
                    seen = now
                    await socket.send_json(hub.status)
                try:
                    data = await asyncio.wait_for(socket.receive_json(), timeout=0.2)
                    if isinstance(data, dict):
                        handle(data.get('cmd', ''), data.get('place'))
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            pass

    # colcon --symlink-install links each page file back to the source folder, so let
    # StaticFiles follow links (the option exists in Ubuntu 24.04's Starlette 0.31)
    web_dir = os.path.realpath(web_dir)
    try:
        page = StaticFiles(directory=web_dir, html=True, follow_symlink=True)
    except TypeError:               # older Starlette without follow_symlink
        page = StaticFiles(directory=web_dir, html=True)
    app.mount('/', page, name='page')
    return app
