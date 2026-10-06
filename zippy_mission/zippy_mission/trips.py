"""Zippy's trip manager - the part of the brain that decides what to do next.

Plain Python, no ROS, so it can be tested on its own. mission_node.py wraps it in ROS.

States
    at_dock     waiting at the dock for a trip
    going       driving to a place
    arrived     at the place, waiting for someone to take the item and tap Done
    returning   driving back to the dock
    stopped     someone tapped Stop; Zippy waits where it is
    needs_help  Zippy couldn't get back to the dock; a person has to help

A failed trip to a place sends Zippy back to the dock. A failed trip to the dock
ends in needs_help, so Zippy never loops around the flat on its own.
"""
import time

AT_DOCK, GOING, ARRIVED, RETURNING, STOPPED, NEEDS_HELP = (
    'at_dock', 'going', 'arrived', 'returning', 'stopped', 'needs_help')
DOCK = 'dock'


def nice(name):
    """bedroom_a -> Bedroom A"""
    return ' '.join(w.capitalize() if len(w) > 1 else w.upper() for w in name.split('_'))


class TripManager:
    def __init__(self, places, navigator, arrive_timeout=120.0, trip_timeout=240.0, clock=time.monotonic):
        """places: {name: {x, y, yaw}} including 'dock'.
        navigator: has start(name, place, on_done) -> None and cancel() -> None.
            on_done(ok: bool, reason: str) is called once per start, unless cancel() came first.
        """
        if DOCK not in places:
            raise ValueError("places.yaml has no 'dock'")
        self.places = places
        self.nav = navigator
        self.arrive_timeout = arrive_timeout
        self.trip_timeout = trip_timeout
        self.clock = clock
        self.state = AT_DOCK
        self.target = None          # where Zippy is driving or standing
        self.queue = []             # places still to visit, in order
        self.message = 'Ready at the dock.'
        self.distance_left = None
        self._shown_distance = None # the distance last shown on screen
        self.trips_done = 0
        self.trips_failed = 0
        self._since = clock()
        self._trip_id = 0           # ignores results from trips that were cancelled
        self.changed = True         # set whenever the status changes, cleared by whoever publishes it

    # ------------------------------------------------------------------ commands from people
    def command(self, cmd, place=None):
        """cmd: go | done | stop | home | clear. Returns a short reply for the screen."""
        if cmd == 'go':
            if not isinstance(place, str) or place not in self.places:
                return f'Unknown place: {place}'
            if place == DOCK:
                return self.command('home')
            if place == self.target and self.state == GOING:
                return f'Already going to {nice(place)}'
            self.queue.append(place)
            self._touch(f'{nice(place)} added.' if self.state in (GOING, ARRIVED) else self.message)
            if self.state in (AT_DOCK, STOPPED, NEEDS_HELP, RETURNING):
                self._next()
            return f'Going to {nice(place)}' if self.target == place else f'{nice(place)} is in the queue'
        if cmd == 'done':
            if self.state != ARRIVED:
                return 'Nothing to confirm.'
            self.trips_done += 1
            self._next()
            return 'Thanks!'
        if cmd == 'stop':
            self._cancel_drive()
            self.queue.clear()
            self._set(STOPPED, None, 'Stopped. Tap a place, or Go home.')
            return 'Stopped.'
        if cmd == 'home':
            self.queue.clear()
            if self.state == AT_DOCK:
                return 'Already at the dock.'
            self._cancel_drive()
            self._drive(DOCK)
            return 'Going home.'
        if cmd == 'clear':
            self.queue.clear()
            self._touch('Queue cleared.')
            return 'Queue cleared.'
        return f'Unknown command: {cmd}'

    # ------------------------------------------------------------------ called regularly (10 times a second)
    def tick(self):
        age = self.clock() - self._since
        if self.state == ARRIVED and age > self.arrive_timeout:
            self.message = f'No one tapped Done at {nice(self.target)}.'
            self.trips_done += 1
            self._next()
        elif self.state in (GOING, RETURNING) and age > self.trip_timeout:
            self.nav.cancel()
            self._nav_done(self._trip_id, False, f'took longer than {self.trip_timeout:.0f} s')

    def progress(self, distance_left):
        old = self._shown_distance
        if (distance_left is None) != (old is None) or (
                distance_left is not None and abs(distance_left - old) >= 0.1):
            self._shown_distance = distance_left
            self.changed = True
        self.distance_left = distance_left

    def status(self):
        return {
            'state': self.state,
            'target': self.target,
            'target_name': nice(self.target) if self.target else None,
            'queue': [nice(p) for p in self.queue],
            'message': self.message,
            'distance_left': None if self.distance_left is None else round(self.distance_left, 1),
            'seconds_in_state': round(self.clock() - self._since),
            'trips_done': self.trips_done,
            'trips_failed': self.trips_failed,
            'places': [{'id': p, 'name': nice(p)} for p in self.places if p != DOCK],
        }

    # ------------------------------------------------------------------ inside
    def _next(self):
        if self.queue:
            self._cancel_drive()
            self._drive(self.queue.pop(0))
        else:
            self._drive(DOCK)

    def _drive(self, place):
        self._trip_id += 1
        trip = self._trip_id
        if place == DOCK:
            self._set(RETURNING, DOCK, self._keep_or('Going back to the dock.'))
        else:
            self._set(GOING, place, f'Going to {nice(place)}.')
        self.nav.start(place, self.places[place], lambda ok, reason: self._nav_done(trip, ok, reason))

    def _cancel_drive(self):
        if self.state in (GOING, RETURNING):
            self._trip_id += 1          # the cancelled trip's result will be ignored
            self.nav.cancel()

    def _nav_done(self, trip, ok, reason):
        if trip != self._trip_id:
            return                      # an old trip that was cancelled
        self._trip_id += 1
        place = self.target
        if self.state == GOING:
            if ok:
                self._set(ARRIVED, place, f'Arrived at {nice(place)}. Take your item, then tap Done.')
            else:
                self.trips_failed += 1
                self.message = f"Couldn't reach {nice(place)} ({reason})."
                self._next()            # next place in the queue, or home
        elif self.state == RETURNING:
            if ok:
                note = self.message if self.message.startswith(("Couldn't", 'No one')) else ''
                self._set(AT_DOCK, DOCK, f'Back at the dock. {note}'.strip())
                if self.queue:
                    self._next()
            else:
                self.trips_failed += 1
                self.queue.clear()
                self._set(NEEDS_HELP, None, f"Help! I couldn't get back to the dock ({reason}).")

    def _keep_or(self, text):
        """Keep a failure message on screen while Zippy drives home."""
        return self.message if self.message.startswith(("Couldn't", 'No one')) else text

    def _set(self, state, target, message):
        self.state, self.target, self.message = state, target, message
        self.distance_left = None
        self._since = self.clock()
        self.changed = True

    def _touch(self, message):
        self.message = message
        self.changed = True
