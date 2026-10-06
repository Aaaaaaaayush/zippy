// Zippy's touchscreen page: shows the brain's status and sends taps back over a WebSocket.
const $ = (id) => document.getElementById(id);
const LABELS = {
  at_dock: 'At dock', going: 'Going', arrived: 'Arrived', returning: 'Returning',
  stopped: 'Stopped', needs_help: 'Needs help', offline: 'Offline',
};
let socket = null;
let placesKey = '';

function send(cmd, place) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ cmd, place: place || null }));
  }
}

function drawPlaces(places) {
  const key = places.map((p) => p.id).join(',');
  if (key === placesKey) return;          // only rebuild when the list changes
  placesKey = key;
  const box = $('places');
  box.innerHTML = '';
  for (const p of places) {
    const b = document.createElement('button');
    b.className = 'place';
    b.dataset.id = p.id;
    b.textContent = p.name;
    b.onclick = () => send('go', p.id);
    box.appendChild(b);
  }
}

function render(s) {
  $('state').textContent = LABELS[s.state] || s.state;
  $('state').className = 'pill ' + s.state;
  $('status-card').className = 'status ' + s.state;
  $('pretend').hidden = !s.fake;
  $('message').textContent = s.message || '';

  const bits = [];
  if (s.distance_left != null && (s.state === 'going' || s.state === 'returning')) {
    bits.push(`${s.distance_left.toFixed(1)} m to go`);
  }
  if (s.seconds_in_state != null && s.state !== 'at_dock') bits.push(`${s.seconds_in_state} s`);
  if (s.trips_done != null) bits.push(`${s.trips_done} delivered, ${s.trips_failed} failed`);
  $('detail').textContent = bits.join('  ·  ');
  $('queue').textContent = s.queue && s.queue.length ? 'Next: ' + s.queue.join(', ') : '';

  drawPlaces(s.places || []);
  const queued = new Set((s.queue || []));
  for (const b of document.querySelectorAll('.place')) {
    b.classList.toggle('target', s.state === 'going' && b.dataset.id === s.target);
    b.classList.toggle('queued', queued.has(b.textContent));
  }
  $('done').disabled = s.state !== 'arrived';
  $('home').disabled = s.state === 'at_dock' || s.state === 'returning';
}

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onopen = () => { $('offline').hidden = true; };
  socket.onmessage = (e) => render(JSON.parse(e.data));
  socket.onclose = () => {
    $('offline').hidden = false;
    setTimeout(connect, 1000);
  };
}

$('done').onclick = () => send('done');
$('home').onclick = () => send('home');
$('stop').onclick = () => send('stop');
connect();
