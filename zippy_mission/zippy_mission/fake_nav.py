"""Pretend Nav2 for testing the brain and the touchscreen without Gazebo.

Every trip "drives" in a straight line at 0.4 m/s (at least 3 s) and arrives,
unless the place is listed in fail_places: then it gives up halfway.
"""
import math
import time


class FakeNavigator:
    def __init__(self, start_xy=(0.0, 0.0), speed=0.4, fail_places=(), clock=time.monotonic):
        self.xy = start_xy
        self.speed = speed
        self.fail_places = set(fail_places)
        self.clock = clock
        self._trip = None   # (name, from_xy, to_xy, t0, duration, on_done)

    def start(self, name, place, on_done):
        to = (float(place['x']), float(place['y']))
        dist = math.dist(self.xy, to)
        self._trip = (name, self.xy, to, self.clock(), max(3.0, dist / self.speed), on_done)

    def cancel(self):
        if self._trip:
            self.xy = self._where()
        self._trip = None

    def distance_left(self):
        if not self._trip:
            return None
        return math.dist(self._where(), self._trip[2])

    def update(self):
        """Call regularly. Finishes the trip when its time is up."""
        if not self._trip:
            return
        name, a, b, t0, duration, on_done = self._trip
        frac = (self.clock() - t0) / duration
        if name in self.fail_places and frac >= 0.5:
            self.xy = self._where()
            self._trip = None
            on_done(False, 'pretend failure')
        elif frac >= 1.0:
            self.xy = b
            self._trip = None
            on_done(True, '')

    def _where(self):
        name, a, b, t0, duration, _ = self._trip
        f = min(1.0, (self.clock() - t0) / duration)
        return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
