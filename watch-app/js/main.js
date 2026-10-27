/* GearStream: lee todos los sensores del Galaxy Watch (Tizen) y los envía por WebSocket.
 *
 * Protocolo (JSON, reloj -> servidor):
 *   {type:'hello',  app, device:{...}, available:[...], t}
 *   {type:'status', source, state:'starting'|'on'|'waiting'|'error'|'unsupported', detail, hw, t}
 *   {type:'data',   samples:[[source, t_ms, {valores}], ...]}
 */
(function () {
  'use strict';

  var APP_VERSION = '1.0.0';
  var cfg = window.GEARSTREAM_CONFIG;
  var hasTizen = typeof window.tizen !== 'undefined';

  var state = {
    running: false,
    ws: null,
    wsState: 'off',      // off | connecting | open
    retryMs: 500,
    retryTimer: null,
    flushTimer: null,
    buffer: [],
    sources: {},         // nombre -> {state, detail, hw, count}
    available: [],
    stoppers: [],
    pushed: 0,
    rate: 0
  };

  function now() { return Date.now(); }

  // Los objetos de Tizen guardan sus campos en el prototipo, así que JSON.stringify directo no sirve.
  function plain(obj, depth) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (depth > 3) return null;
    if (Array.isArray(obj)) return obj.map(function (v) { return plain(v, depth + 1); });
    var out = {};
    for (var k in obj) {
      var v;
      try { v = obj[k]; } catch (e) { continue; }
      if (typeof v === 'function') continue;
      out[k] = plain(v, depth + 1);
    }
    return out;
  }

  function errText(e) {
    if (!e) return '';
    return (e.name ? e.name + ': ' : '') + (e.message || e);
  }

  // ---------- Red ----------

  function serverUrl() {
    try { return localStorage.getItem('serverUrl') || cfg.SERVER_URL; } catch (e) { return cfg.SERVER_URL; }
  }

  function send(msg) {
    var ws = state.ws;
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(msg));
  }

  function statusMsg(source) {
    var s = state.sources[source];
    return { type: 'status', source: source, state: s.state, detail: s.detail, hw: s.hw, t: now() };
  }

  function helloMsg() {
    var device = { userAgent: navigator.userAgent };
    if (hasTizen && tizen.systeminfo) {
      ['http://tizen.org/system/model_name',
       'http://tizen.org/feature/platform.version',
       'http://tizen.org/system/platform.name',
       'http://tizen.org/system/build.string'].forEach(function (key) {
        try { device[key.split('/').pop()] = tizen.systeminfo.getCapability(key); } catch (e) {}
      });
    }
    return { type: 'hello', app: APP_VERSION, device: device, available: state.available, t: now() };
  }

  function connect() {
    if (!state.running) return;
    setWs('connecting');
    var ws;
    try { ws = new WebSocket(serverUrl()); } catch (e) { setWs('off'); scheduleReconnect(); return; }
    state.ws = ws;
    ws.onopen = function () {
      state.retryMs = 500;
      setWs('open');
      send(helloMsg());
      Object.keys(state.sources).forEach(function (k) { send(statusMsg(k)); });
    };
    ws.onclose = function () {
      if (state.ws !== ws) return;
      state.ws = null;
      setWs('off');
      scheduleReconnect();
    };
    ws.onerror = function () {};  // siempre le sigue onclose
  }

  function scheduleReconnect() {
    if (!state.running) return;
    clearTimeout(state.retryTimer);
    state.retryTimer = setTimeout(connect, state.retryMs);
    state.retryMs = Math.min(state.retryMs * 2, 5000);
  }

  function flush() {
    var ws = state.ws;
    if (!ws || ws.readyState !== 1 || !state.buffer.length) return;
    if (ws.bufferedAmount > cfg.MAX_WS_BUFFERED) return;  // dejar que el socket se vacíe
    var batch = state.buffer;
    state.buffer = [];
    ws.send(JSON.stringify({ type: 'data', samples: batch }));
  }

  // ---------- Muestras y estados ----------

  function setStatus(source, st, detail, hw) {
    var s = state.sources[source] || (state.sources[source] = { count: 0 });
    s.state = st;
    s.detail = detail || '';
    if (hw) s.hw = hw;
    send(statusMsg(source));
  }

  function push(source, values) {
    var s = state.sources[source];
    if (s) {
      s.count++;
      if (s.state !== 'on') setStatus(source, 'on', s.detail);
    }
    state.pushed++;
    state.buffer.push([source, now(), values]);
    if (state.buffer.length > cfg.MAX_BUFFER) state.buffer.splice(0, Math.floor(cfg.MAX_BUFFER / 10));
  }

  // ---------- Fuentes de datos ----------

  function startSensorService() {
    if (!hasTizen || !tizen.sensorservice) return;
    try { state.available = tizen.sensorservice.getAvailableSensors(); } catch (e) { state.available = []; }

    state.available.forEach(function (type) {
      var sensor;
      try { sensor = tizen.sensorservice.getDefaultSensor(type); }
      catch (e) { setStatus(type, e.name === 'NotSupportedError' ? 'unsupported' : 'error', errText(e)); return; }

      var interval = cfg.INTERVAL_OVERRIDES[type] || cfg.SENSOR_INTERVAL_MS;
      var onData = function (data) { push(type, plain(data, 0)); };
      setStatus(type, 'starting');

      sensor.start(function () {
        try { sensor.setChangeListener(onData, interval, 0); }
        catch (e) { sensor.setChangeListener(onData, interval); }  // runtimes sin batchLatency
        setStatus(type, 'waiting', interval + ' ms');
        if (sensor.getSensorHardwareInfo) {
          sensor.getSensorHardwareInfo(function (hw) {
            var s = state.sources[type];
            setStatus(type, s.state, s.detail, plain(hw, 0));
          }, function () {});
        }
      }, function (e) { setStatus(type, 'error', errText(e)); });

      state.stoppers.push(function () {
        try { sensor.unsetChangeListener(); } catch (e) {}
        try { sensor.stop(); } catch (e) {}
      });
    });
  }

  function startHam() {
    if (!hasTizen || !tizen.humanactivitymonitor) return;
    cfg.HAM_TYPES.forEach(function (type) {
      setStatus(type, 'starting');
      try {
        tizen.humanactivitymonitor.start(type, function (info) {
          push(type, info ? plain(info, 0) : {});
        }, function (e) { setStatus(type, 'error', errText(e)); });
        setStatus(type, 'waiting');
        state.stoppers.push(function () { try { tizen.humanactivitymonitor.stop(type); } catch (e) {} });
      } catch (e) {
        setStatus(type, e.name === 'NotSupportedError' ? 'unsupported' : 'error', errText(e));
      }
    });
  }

  function startGeo() {
    if (!cfg.GPS || !navigator.geolocation) return;
    setStatus('GPS', 'waiting', 'buscando señal');
    var id = navigator.geolocation.watchPosition(function (p) {
      var c = p.coords;
      push('GPS', { latitude: c.latitude, longitude: c.longitude, altitude: c.altitude,
                    accuracy: c.accuracy, speed: c.speed, heading: c.heading });
    }, function (e) {
      setStatus('GPS', e.code === 3 ? 'waiting' : 'error', e.message || ('código ' + e.code));
    }, { enableHighAccuracy: true, maximumAge: 0, timeout: 60000 });
    state.stoppers.push(function () { navigator.geolocation.clearWatch(id); });
  }

  function startW3C() {
    function on(name, event, handler) {
      setStatus(name, 'waiting');
      window.addEventListener(event, handler);
      state.stoppers.push(function () { window.removeEventListener(event, handler); });
    }
    if (cfg.W3C_ORIENTATION) {
      on('ORIENTATION', 'deviceorientation', function (e) {
        push('ORIENTATION', { alpha: e.alpha, beta: e.beta, gamma: e.gamma, absolute: e.absolute });
      });
    }
    // Respaldo por si sensorservice no ofrece acelerómetro (p. ej. en el emulador).
    if (state.available.indexOf('ACCELERATION') < 0) {
      on('MOTION', 'devicemotion', function (e) {
        var a = e.accelerationIncludingGravity || {}, r = e.rotationRate || {};
        push('MOTION', { x: a.x, y: a.y, z: a.z, alpha: r.alpha, beta: r.beta, gamma: r.gamma });
      });
    }
  }

  function startBattery() {
    if (!hasTizen || !tizen.systeminfo) return;
    var onBattery = function (b) { push('BATTERY', { level: b.level, isCharging: b.isCharging }); };
    try {
      setStatus('BATTERY', 'waiting');
      tizen.systeminfo.getPropertyValue('BATTERY', onBattery, function () {});
      var id = tizen.systeminfo.addPropertyValueChangeListener('BATTERY', onBattery);
      state.stoppers.push(function () { tizen.systeminfo.removePropertyValueChangeListener(id); });
    } catch (e) { setStatus('BATTERY', 'error', errText(e)); }
  }

  function requestPermissions(done) {
    if (!hasTizen || !tizen.ppm) return done();
    var privs = ['http://tizen.org/privilege/healthinfo'];
    if (cfg.GPS) privs.push('http://tizen.org/privilege/location');
    var i = 0;
    (function next() {
      if (i >= privs.length) return done();
      var p = privs[i++];
      try {
        if (tizen.ppm.checkPermission(p) === 'PPM_ALLOW') return next();
        tizen.ppm.requestPermission(p, next, next);
      } catch (e) { next(); }
    })();
  }

  function keepAwake(on) {
    if (!hasTizen || !tizen.power) return;
    try {
      if (on) {
        tizen.power.request('CPU', 'CPU_AWAKE');
        if (cfg.KEEP_SCREEN_ON) tizen.power.request('SCREEN', 'SCREEN_NORMAL');
      } else {
        tizen.power.release('CPU');
        tizen.power.release('SCREEN');
      }
    } catch (e) {}
  }

  // ---------- Start / stop ----------

  function start() {
    if (state.running) return;
    state.running = true;
    state.sources = {};
    render();
    requestPermissions(function () {
      if (!state.running) return;
      keepAwake(true);
      startSensorService();
      startHam();
      startGeo();
      startW3C();
      startBattery();
      setStatus('BEZEL', 'waiting');
      connect();
      state.flushTimer = setInterval(flush, cfg.FLUSH_MS);
      render();
    });
  }

  function stop() {
    if (!state.running) return;
    flush();
    state.running = false;
    state.stoppers.forEach(function (f) { try { f(); } catch (e) {} });
    state.stoppers = [];
    clearInterval(state.flushTimer);
    clearTimeout(state.retryTimer);
    if (state.ws) { var ws = state.ws; state.ws = null; ws.close(); }
    state.buffer = [];
    keepAwake(false);
    setWs('off');
  }

  // ---------- UI ----------

  var $ = function (id) { return document.getElementById(id); };
  var STATE_LABEL = { off: 'Desconectado', connecting: 'Conectando…', open: 'Conectado' };

  function setWs(s) { state.wsState = s; render(); }

  function render() {
    var main = $('main');
    main.className = state.running ? 'ws-' + state.wsState : 'stopped';
    $('connText').textContent = state.running ? STATE_LABEL[state.wsState] : 'Detenido';
    $('url').textContent = serverUrl().replace(/^wss?:\/\//, '');
    $('toggle').textContent = state.running ? 'Detener' : 'Iniciar';

    var names = Object.keys(state.sources);
    var active = names.filter(function (n) { return state.sources[n].state === 'on'; }).length;
    $('stats').textContent = state.running ? active + '/' + names.length + ' fuentes · ' + state.rate + ' /s' : '';

    var list = $('list');
    list.innerHTML = '';
    names.sort().forEach(function (n) {
      var s = state.sources[n];
      var li = document.createElement('li');
      li.className = 'st-' + s.state;
      li.textContent = n;
      list.appendChild(li);
    });
  }

  function openSettings() {
    $('urlInput').value = serverUrl();
    $('settings').hidden = false;
    $('main').hidden = true;
  }

  function closeSettings(save) {
    if (save) {
      var v = $('urlInput').value.trim();
      if (v && !/^wss?:\/\//.test(v)) v = 'ws://' + v;
      try { if (v) localStorage.setItem('serverUrl', v); } catch (e) {}
      if (state.running && state.ws) state.ws.close();  // reconecta con la nueva URL
    }
    $('settings').hidden = true;
    $('main').hidden = false;
    render();
  }

  function init() {
    $('toggle').addEventListener('click', function () { state.running ? stop() : start(); });
    $('url').addEventListener('click', openSettings);
    $('save').addEventListener('click', function () { closeSettings(true); });
    $('cancel').addEventListener('click', function () { closeSettings(false); });

    // El bisel giratorio desplaza la lista y también se transmite como fuente.
    document.addEventListener('rotarydetent', function (e) {
      var dir = e.detail && e.detail.direction;
      $('list').scrollTop += dir === 'CW' ? 30 : -30;
      if (state.running) push('BEZEL', { direction: dir });
    });

    document.addEventListener('tizenhwkey', function (e) {
      if (e.keyName !== 'back') return;
      if (!$('settings').hidden) return closeSettings(false);
      try {
        var app = tizen.application.getCurrentApplication();
        // Mientras transmite, "atrás" solo oculta la app para no cortar el stream.
        state.running ? app.hide() : app.exit();
      } catch (err) {}
    });

    setInterval(function () {
      state.rate = state.pushed;
      state.pushed = 0;
      render();
    }, 1000);

    render();
    if (cfg.AUTO_START) start();
  }

  window.addEventListener('load', init);
}());
