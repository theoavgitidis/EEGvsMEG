'use strict';
const $ = id => document.getElementById(id);
const SIDES = ['left', 'right'];
const DIVERGING = [[0, '#2166ac'], [.5, '#f7f7f7'], [1, '#b2182b']];
const SEQUENTIAL = [[0, '#f7fbff'], [.5, '#6baed6'], [1, '#08306b']];
const config = {responsive: true, displaylogo: false, scrollZoom: false};
const state = {
  data: null, channel: 1, camera: {eye: {x: 0, y: 0, z: 2.2}, up: {x: 0, y: 1, z: 0}},
  timer: null, revision: 0, rendering: Promise.resolve(), cache: new Map(), staticKey: null,
  selected: {}, details: {}, channelTrials: {}, scales: {percent: [-100, 100], power: [0, 100]},
};
const fmt = v => v === null || v === undefined ? '—' : (Math.abs(v) < .005 ? 0 : Number(v)).toFixed(2);
const available = v => typeof v === 'number' && Number.isFinite(v);
const single = () => $('scope').value === 'single';
const conditionKey = side => $('family').value + '_hand_' + side;
const aggregate = side => state.data.conditions[conditionKey(side)];
const condition = side => single() ? state.details[side] : aggregate(side);
const band = () => state.data.bands[+$('band').value];
const channelName = () => state.data.channels[state.channel].site;
const unit = () => $('metric').value === 'percent' ? '%' : 'µV²';
function clock(seconds) {
  return Math.floor(seconds / 60) + ':' + (seconds % 60).toFixed(2).padStart(5, '0');
}
function trialLabel(t) {
  return `Block ${t.block} · Trial ${t.trial} · Attempt ${t.attempt} · Aufnahme ${clock(t.onset_s)}`;
}
function taskLabel(side) {
  return `${side === 'left' ? 'Linke' : 'Rechte'} Faust ${$('family').value === 'me' ? 'ausführen' : 'vorstellen'}`;
}
function selectionLabel(side) {
  const c = condition(side);
  return single() ? c?.n ? trialLabel(c.trials[0]) : 'Kein gültiger Trial' : `Mittelwert aus ${c?.n || 0} Trials`;
}
function theme() {
  const css = getComputedStyle(document.documentElement);
  return Object.fromEntries(['surface', 'text', 'muted', 'grid'].map(k => [k, css.getPropertyValue('--' + k).trim()]));
}
function layout(title = '') {
  const t = theme();
  return {
    title: {text: title, font: {size: 14}}, paper_bgcolor: t.surface, plot_bgcolor: t.surface,
    font: {color: t.text, size: 12}, margin: {l: 65, r: 30, t: 40, b: 50},
    uirevision: 'erds', xaxis: {gridcolor: t.grid}, yaxis: {gridcolor: t.grid},
  };
}
async function getJSON(resource, query) {
  const url = resource + (query ? '?' + new URLSearchParams(query).toString() : '');
  if (!state.cache.has(url)) {
    const pending = fetch(url).then(async response => {
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Auswertung nicht verfügbar.');
      return data;
    });
    state.cache.set(url, pending);
    pending.catch(() => state.cache.delete(url));
  }
  return state.cache.get(url);
}
function value(c, ci, bi, metric) {
  if (!c?.n) return null;
  return $('mode').value === 'time' ? c[metric][ci][bi][+$('time').value] : c[$('mode').value + '_' + metric][ci][bi];
}
function scale() {
  const lo = Number($('scale-min').value), hi = Number($('scale-max').value);
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi ||
      ($('metric').value === 'percent' && !(lo < 0 && hi > 0)) || ($('metric').value === 'power' && lo < 0)) {
    throw Error('Farbskala: Minimum < Maximum; Prozent muss 0 einschließen, Leistung muss ≥ 0 sein.');
  }
  return [lo, hi];
}
function colorscale(lo, hi) {
  return $('metric').value === 'percent' ? [[0, DIVERGING[0][1]], [-lo / (hi - lo), DIVERGING[1][1]], [1, DIVERGING[2][1]]] : SEQUENTIAL;
}
// Convert values into explicit sRGB colors ourselves. Scatter3d receives colors
// directly: no per-trace auto-normalization, lighting or hidden scale inference.
function colorFor(value, lo, hi) {
  if (!available(value)) return '#888888';
  const stops = colorscale(lo, hi), x = Math.max(0, Math.min(1, (value - lo) / (hi - lo)));
  let i = 1;
  while (i < stops.length - 1 && x > stops[i][0]) i++;
  const a = stops[i - 1], b = stops[i], f = (x - a[0]) / (b[0] - a[0]);
  const rgb = hex => [1, 3, 5].map(j => parseInt(hex.slice(j, j + 2), 16));
  return 'rgb(' + rgb(a[1]).map((v, j) => Math.round(v + f * (rgb(b[1])[j] - v))).join(',') + ')';
}
function phaseShapes(c, cursor = true) {
  const line = (x, dash, width = 1) => ({type: 'line', x0: x, x1: x, y0: 0, y1: 1, yref: 'paper', line: {color: theme().muted, dash, width}});
  const result = [line(0, 'dot')];
  for (const offset of new Set((c?.trials || []).map(t => (t.offset_sample - t.onset_sample) / state.data.metadata.sampling_rate_hz))) {
    result.push(line(offset, 'dash'));
  }
  if (cursor && $('mode').value === 'time') result.push(line(state.data.times[+$('time').value], 'solid', 2));
  return result;
}
function comparisonShapes() {
  // Coincident cue, offset and cursor lines should appear only once.
  return [...new Map(SIDES.flatMap(side => phaseShapes(condition(side))).map(shape => [JSON.stringify(shape), shape])).values()];
}
function populateTrialSelectors() {
  for (const side of SIDES) {
    const key = conditionKey(side), select = $('trial-' + side), trials = aggregate(side).trials;
    const previous = state.selected[key];
    select.replaceChildren();
    for (const t of trials) {
      const option = document.createElement('option');
      option.value = t.key; option.textContent = `${t.ordinal}/${trials.length} · ${trialLabel(t)}`;
      select.append(option);
    }
    state.selected[key] = trials.some(t => t.key === previous) ? previous : trials[0]?.key;
    if (state.selected[key]) select.value = state.selected[key];
    select.disabled = !trials.length;
    $('prev-' + side).disabled = select.selectedIndex <= 0;
    $('next-' + side).disabled = select.selectedIndex < 0 || select.selectedIndex >= trials.length - 1;
  }
}
async function loadSelection() {
  const channel = channelName(), channelData = await getJSON('channel', {channel, band: band().id});
  state.channelTrials = channelData.conditions;
  if (single()) {
    const selections = await Promise.all(SIDES.map(side => {
      const key = state.selected[conditionKey(side)];
      return key ? getJSON('trial', {key, channel}) : Promise.resolve({n: 0, trials: []});
    }));
    SIDES.forEach((side, i) => { state.details[side] = selections[i]; });
  }
}
function updateSelectionText() {
  $('trial-controls').hidden = !single(); $('waveform-panel').hidden = !single();
  $('color-note').textContent = ($('metric').value === 'percent' ?
    'Blau = ERD · Neutral = 0 % · Rot = ERS.' :
    'Absolute Bandpower in µV²: hell = geringere, dunkelblau = höhere Leistung; keine ERD/ERS-Farbkodierung.') +
    ' Grau + × = ausgeschlossen/nicht verfügbar.';
  $('selection-summary').textContent = `${single() ? 'EINZELTRIALS' : 'MITTELWERTE'} · ${taskLabel('left')}: ${selectionLabel('left')} | ${taskLabel('right')}: ${selectionLabel('right')} · ${$('band').selectedOptions[0].text} · ${$('mode').selectedOptions[0].text}. ` +
    (single() ? 'Referenz: eigene Vorbereitung jedes Trials.' : 'Alle gültigen Wiederholungen je Bedingung, über alle Blöcke. Keine einzelne Wiederholung.');
}
async function head(side, lo, hi) {
  const d = state.data, g = d.geometry, c = condition(side), bi = +$('band').value, metric = $('metric').value;
  const vals = d.channels.map((_, ci) => value(c, ci, bi, metric)), good = [], missing = [];
  vals.forEach((v, i) => (available(v) ? good : missing).push(i));
  const vertices = g.vertices, triangles = g.triangles, coords = g.display_mm;
  if (!state.mesh) state.mesh = {type: 'mesh3d', x: vertices.map(p => p[0]), y: vertices.map(p => p[1]), z: vertices.map(p => p[2]),
    i: triangles.map(t => t[0]), j: triangles.map(t => t[1]), k: triangles.map(t => t[2]), color: theme().muted,
    opacity: .12, hoverinfo: 'skip', showscale: false};
  function sensors(indices, invalid) {
    return {
      type: 'scatter3d', mode: 'markers+text', x: indices.map(i => coords[i][0]), y: indices.map(i => coords[i][1]), z: indices.map(i => coords[i][2]),
      text: indices.map(i => d.channels[i].site + (invalid ? ' ×' : '')), textposition: 'top center', textfont: {color: theme().text, size: 12},
      meta: {sensors: true, indices, values: indices.map(i => vals[i])},
      customdata: indices.map(i => [i, d.channels[i].name || 'nicht vorhanden', d.channels[i].site, fmt(value(c, i, bi, 'percent')),
        fmt(value(c, i, bi, 'power')), fmt(c?.n ? c.reference[i][bi] : null), invalid ? 0 : c.n]),
      hovertemplate: '%{customdata[2]} · %{customdata[1]}<br>ERD/ERS: %{customdata[3]} %<br>Leistung: %{customdata[4]} µV²<br>Referenz: %{customdata[5]} µV²<br>Trials: %{customdata[6]}<extra></extra>',
      marker: {size: 9, symbol: invalid ? 'x' : 'circle', line: {color: theme().text, width: 1}, color: indices.map(i => colorFor(vals[i], lo, hi))},
      showlegend: false,
    };
  }
  // The invisible trace supplies an honest numeric colorbar for the explicit
  // sensor RGB colors; it is not a ninth electrode or a surface interpolation.
  const legend = {type: 'scatter3d', mode: 'markers', x: [coords[2][0], coords[2][0]], y: [coords[2][1], coords[2][1]], z: [coords[2][2], coords[2][2]], hoverinfo: 'skip', showlegend: false,
    marker: {size: 1, opacity: 0, color: [lo, hi], cmin: lo, cmax: hi, colorscale: colorscale(lo, hi), showscale: true,
      colorbar: {title: {text: metric === 'percent' ? 'ERD/ERS %' : 'µV²'}, len: .7, thickness: 12}}};
  const traces = [state.mesh, sensors(good, false), sensors(missing, true), legend,
    {type: 'scatter3d', mode: 'text', x: [-100, 100, 0], y: [0, 0, 115], z: [10, 10, 5],
      text: ['L', 'R', 'Nase / vorn'], hoverinfo: 'skip', showlegend: false, textfont: {color: theme().muted}}];
  const l = layout(); l.margin = {l: 0, r: 20, t: 0, b: 0};
  l.scene = {camera: state.camera, aspectmode: 'data', xaxis: {visible: false}, yaxis: {visible: false}, zaxis: {visible: false}};
  const graph = $('head-' + side);
  if (!graph.data) await Plotly.newPlot(graph, traces, l, config);
  else {
    const updates = {};
    for (const field of ['x', 'y', 'z', 'text', 'textfont', 'customdata', 'marker', 'meta']) updates[field] = [traces[1][field], traces[2][field]];
    await Plotly.update(graph, updates, {paper_bgcolor: theme().surface, 'font.color': theme().text}, [1, 2]);
    await Plotly.restyle(graph, {marker: legend.marker}, [3]);
  }
  $('title-' + side).textContent = `${taskLabel(side)} · ${selectionLabel(side)}`;
  const finite = vals.filter(available), clipped = finite.filter(v => v < lo || v > hi).length;
  $('clip-' + side).textContent = finite.length ?
    `Werte ${fmt(Math.min(...finite))} bis ${fmt(Math.max(...finite))} ${unit()} · C3−C4: ${available(vals[1]) && available(vals[3]) ? fmt(vals[1] - vals[3]) : '—'} ${metric === 'percent' ? 'Prozentpunkte' : 'µV²'} · ${clipped} Werte außerhalb der Farbskala; ${missing.length} nicht verfügbar.` : 'Keine Werte verfügbar.';
  const bar = layout(); bar.margin = {l: 45, r: 80, t: 15, b: 45};
  // Both numeric charts share limits, including real values beyond the color
  // scale. Starting from that scale also avoids axes in femto-percent when
  // a theoretically zero effect contains only floating-point roundoff.
  const allValues = SIDES.flatMap(s => d.channels.map((_, ci) => value(condition(s), ci, bi, metric))).filter(available);
  const barLo = Math.min(lo, 0, ...allValues), barHi = Math.max(hi, ...allValues), span = barHi - barLo;
  bar.xaxis.range = [barLo - span * .12, barHi + span * .18]; bar.xaxis.autorange = false;
  bar.xaxis.title = {text: metric === 'percent' ? 'ERD/ERS (%)' : 'Bandpower (µV²)'};
  bar.yaxis = {...bar.yaxis, autorange: 'reversed'};
  await Plotly.react($('bars-' + side), [{type: 'bar', orientation: 'h', y: d.channels.map(c => c.site), x: vals,
    text: vals.map(v => fmt(v) + ' ' + unit()), textposition: 'outside', cliponaxis: false,
    marker: {color: vals.map(v => colorFor(v, lo, hi))}, hovertemplate: '%{y}: %{x:.3f}<extra></extra>',
    customdata: d.channels.map((_, i) => i)}], bar, config);
}
async function overview(side, lo, hi) {
  const key = conditionKey(side), rows = state.channelTrials[key] || [], metric = $('metric').value;
  const l = layout(taskLabel(side)); l.margin.l = 145; l.plot_bgcolor = theme().grid;
  l.shapes = phaseShapes(aggregate(side));
  l.xaxis = {...l.xaxis, title: {text: 'Zeit zum Aufgaben-Cue (s)'}, range: [-2, 10]};
  l.yaxis = {...l.yaxis, autorange: 'reversed', tickmode: 'array', tickvals: rows.map((_, i) => i),
    ticktext: rows.map(t => `B${t.block} · T${t.trial} · A${t.attempt}`), dtick: 1};
  await Plotly.react($('overview-' + side), [{type: 'heatmap', x: state.data.times, y: rows.map((_, i) => i),
    z: rows.map(t => t[metric]), customdata: rows.map(t => state.data.times.map(() => t.key)),
    zmin: lo, zmax: hi, colorscale: colorscale(lo, hi), hoverongaps: false,
    colorbar: {title: {text: unit()}}, hovertemplate: '%{customdata}<br>%{x:.2f} s · %{z:.2f}<extra></extra>'}], l, config);
}
async function charts() {
  const d = state.data, ci = state.channel, bi = +$('band').value, metric = $('metric').value;
  const traces = [];
  SIDES.forEach((side, i) => {
    const c = condition(side), color = i ? '#c77b14' : '#287cba';
    if ($('individual-curves').checked && !single()) {
      for (const t of state.channelTrials[conditionKey(side)] || []) traces.push({type: 'scatter', mode: 'lines', x: d.times, y: t[metric],
        line: {color, width: 1}, opacity: .22, showlegend: false, name: trialLabel(t), connectgaps: false,
        hovertemplate: '%{x:.2f} s · %{y:.2f}<extra>%{fullData.name}</extra>'});
    }
    if (single() && aggregate(side)?.n) traces.push({type: 'scatter', mode: 'lines', x: d.times, y: aggregate(side)[metric][ci][bi],
      line: {color, dash: 'dot', width: 1}, opacity: .45, name: `${i ? 'Rechts' : 'Links'} · Gesamtmittel`, connectgaps: false});
    traces.push({type: 'scatter', mode: 'lines', x: d.times, y: c?.n ? c[metric][ci][bi] : d.times.map(() => null),
      line: {color, dash: i ? 'dash' : 'solid', width: 2}, name: `${i ? 'Rechts' : 'Links'} · ${single() ? c?.n ? 'T' + c.trials[0].trial : 'kein Trial' : 'Mittelwert'}`,
      connectgaps: false, hovertemplate: '%{x:.2f} s: %{y:.2f}<extra>%{fullData.name}</extra>'});
  });
  const l = layout(); l.xaxis = {...l.xaxis, title: {text: 'Zeit relativ zum Aufgaben-Cue (s)'}, range: [-2, 10]};
  l.yaxis.title = {text: metric === 'percent' ? 'ERD/ERS (%)' : 'Bandpower (µV²)'};
  l.yaxis.autorange = true;
  if (metric === 'percent') {
    const values = traces.flatMap(trace => trace.y).filter(available);
    const low = Math.min(0, ...values), high = Math.max(0, ...values), center = (low + high) / 2;
    // Keep the actual values, but do not magnify floating-point residuals of
    // zero into apparent oscillations on a pico-percent axis.
    const span = Math.max(1, high - low) * 1.15;
    l.yaxis.range = [center - span / 2, center + span / 2]; l.yaxis.autorange = false;
  }
  l.legend = {orientation: 'h', y: 1.2}; l.shapes = comparisonShapes();
  await Plotly.react($('curves'), traces, l, config);
  $('curve-title').textContent = `${channelName()} · ${$('band').selectedOptions[0].text} · ${single() ? 'Einzeltrials (eigene Referenz), Gesamtmittel gepunktet' : 'Gesamtmittel'}`;
  let clipped = 0;
  for (const side of SIDES) {
    const c = condition(side), z = c?.n ? single() ? c.spectral_percent : c.spectral_percent[ci] : d.frequencies.map(() => d.times.map(() => null));
    clipped += z.flat().filter(v => available(v) && (v < -100 || v > 100)).length;
    const tf = layout(`${taskLabel(side)} · ${single() ? c?.n ? 'Trial ' + c.trials[0].trial : 'keine Daten' : 'Gesamtmittel'}`);
    tf.plot_bgcolor = theme().grid;
    tf.xaxis = {...tf.xaxis, title: {text: 'Zeit zum Aufgaben-Cue (s)'}, range: [-2, 10]};
    tf.yaxis = {...tf.yaxis, title: {text: 'Frequenz (Hz)'}, range: [6, 40]}; tf.shapes = phaseShapes(c);
    await Plotly.react($('tf-' + side), [{type: 'heatmap', x: d.times, y: d.frequencies, z, zmin: -100, zmax: 100,
      colorscale: DIVERGING, hoverongaps: false, colorbar: {title: {text: '%'}}, hovertemplate: '%{x:.2f} s · %{y} Hz<br>%{z:.2f} %<extra></extra>'}], tf, config);
  }
  $('tf-title').textContent = `${channelName()} · Zeit-Frequenz-Karten · ${single() ? 'Einzeltrials' : 'Gesamtmittel'} · ${clipped} Werte außerhalb ±100 %`;
  if (single()) {
    const w = layout(); w.xaxis.title = {text: 'Zeit relativ zum Aufgaben-Cue (s)'}; w.yaxis.title = {text: 'EEG (µV, nicht zentriert)'};
    w.legend = {orientation: 'h', y: 1.2}; w.shapes = comparisonShapes();
    await Plotly.react($('waveform'), SIDES.map((side, i) => {
      const c = condition(side); return {type: 'scatter', mode: 'lines', x: c?.waveform_times || [], y: c?.waveform_uv || [],
        name: `${i ? 'Rechts' : 'Links'} · ${c?.n ? 'Trial ' + c.trials[0].trial : 'keine Daten'}`,
        line: {color: i ? '#c77b14' : '#287cba', dash: i ? 'dash' : 'solid'}, connectgaps: false};
    }), w, config);
    $('waveform-title').textContent = `${channelName()} · EEG der ausgewählten Einzeltrials · ${d.metadata.signal}`;
  }
}
function table() {
  const bi = +$('band').value, body = $('values'); body.replaceChildren();
  state.data.channels.forEach((channel, ci) => {
    const row = document.createElement('tr'); if (ci === state.channel) row.className = 'active-row';
    const cells = [channel.site];
    for (const side of SIDES) {
      const c = condition(side), p = value(c, ci, bi, 'power');
      cells.push(String(available(p) ? c.n : 0), fmt(c?.n ? c.reference[ci][bi] : null), fmt(p), fmt(value(c, ci, bi, 'percent')));
    }
    for (const value of cells) { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); }
    row.addEventListener('click', () => { state.channel = ci; $('channel').value = ci; render(); }); body.append(row);
  });
}
function staticSelectionKey(lo, hi) {
  return JSON.stringify({scope: $('scope').value, family: $('family').value, band: $('band').value,
    metric: $('metric').value, channel: state.channel, lo, hi, theme: theme(),
    individuals: $('individual-curves').checked,
    trials: SIDES.map(side => state.selected[conditionKey(side)])});
}
async function updateTimeMarkers() {
  // A new time does not change the curves or TF/trial power matrices. Relayout
  // their cursors instead of rebuilding all plots and losing the current zoom.
  await Plotly.relayout($('curves'), {shapes: comparisonShapes()});
  for (const side of SIDES) {
    await Plotly.relayout($('tf-' + side), {shapes: phaseShapes(condition(side))});
    await Plotly.relayout($('overview-' + side), {shapes: phaseShapes(aggregate(side))});
  }
  if (single()) await Plotly.relayout($('waveform'), {shapes: comparisonShapes()});
}
function render() {
  const revision = ++state.revision;
  state.rendering = state.rendering.then(async () => {
    if (revision !== state.revision) return;
    $('status').textContent = 'Auswahl wird geladen …';
    const [lo, hi] = scale(); state.scales[$('metric').value] = [lo, hi];
    const key = staticSelectionKey(lo, hi), full = state.staticKey !== key;
    if (full) {
      state.staticKey = null;
      await loadSelection();
      if (revision !== state.revision) return;
    }
    const timed = $('mode').value === 'time'; $('time').disabled = false; $('play').disabled = false;
    if (!timed) stop();
    const t = state.data.times[+$('time').value];
    $('time-label').textContent = timed ? `${t.toFixed(1)} s · Fenster ${(t - .5).toFixed(1)} bis ${(t + .5).toFixed(1)} s` : 'Schieben oder Abspielen öffnet den Zeitverlauf';
    $('time').setAttribute('aria-valuetext', `${t.toFixed(1)} Sekunden zum Aufgaben-Cue; Fenster ${(t - .5).toFixed(1)} bis ${(t + .5).toFixed(1)} Sekunden`);
    $('window-note').textContent = $('mode').value === 'task' ? state.data.metadata.task_window : $('mode').value === 'rebound' ? state.data.metadata.rebound_window : '1-s-Fenster, 100-ms-Schritte; keine unabhängige 100-ms-Auflösung, keine Zeitstreckung.';
    updateSelectionText();
    for (const side of SIDES) {
      await head(side, lo, hi);
      if (revision !== state.revision) return;
      if (full) await overview(side, lo, hi);
      if (revision !== state.revision) return;
    }
    if (full) await charts(); else await updateTimeMarkers();
    if (revision !== state.revision) return;
    table(); state.staticKey = key;
    $('overview-title').textContent = `${channelName()} · ${$('band').selectedOptions[0].text} · alle Wiederholungen einzeln`;
    $('status').textContent = 'Bereit · ' + state.data.metadata.signal_description + ' · ' + state.data.metadata.statistics;
  }).catch(error => { state.staticKey = null; stop(); $('status').textContent = 'Fehler: ' + error.message; });
  return state.rendering;
}
function stop() { clearTimeout(state.timer?.timeout); state.timer = null; $('play').textContent = 'Abspielen'; }
function selectTime() {
  stop(); $('mode').value = 'time'; return render();
}
async function play() {
  if (state.timer) return stop();
  $('mode').value = 'time';
  if (+$('time').value >= state.data.times.length - 1) $('time').value = 0;
  const playback = {timeout: null}; state.timer = playback; $('play').textContent = 'Pause';
  async function frame() {
    await render();
    if (state.timer !== playback) return;
    if (+$('time').value >= state.data.times.length - 1) return stop();
    // Wait for the displayed frame before advancing. Slow WebGL must neither
    // queue hundreds of stale frames nor skip every render during playback.
    playback.timeout = setTimeout(() => {
      if (state.timer !== playback) return;
      $('time').value = +$('time').value + 1; frame();
    }, 400);
  }
  await frame();
}
function selectionMetadata() {
  const m = state.data.metadata;
  return {scope: $('scope').value, signal: m.signal, source_unit: m.source_unit, protocol_version: m.protocol_version,
    participant_id: m.participant_id, session_id: m.session_id,
    family: $('family').value, band: band(), channel: channelName(), mode: $('mode').value,
    metric: $('metric').value, cue_time_s: $('mode').value === 'time' ? state.data.times[+$('time').value] : null,
    reference: m.reference, window_seconds: m.window_seconds, hop_seconds: m.hop_seconds,
    task_window: m.task_window, rebound_window: m.rebound_window, montage: m.montage,
    montage_source: state.data.geometry.source, montage_confirmed: m.montage_confirmed,
    n_left: condition('left').n, n_right: condition('right').n,
    trial_left: single() ? state.selected[conditionKey('left')] : null, trial_right: single() ? state.selected[conditionKey('right')] : null,
    color_limits: scale(), normalization: single() ? m.single_trial_normalization : m.normalization};
}
function download(content, type, filename) {
  const url = URL.createObjectURL(new Blob([content], {type})), link = document.createElement('a');
  link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function savePNG(id) {
  stop(); await state.rendering;
  const graph = $(id), old = structuredClone({title: graph.layout.title, margin: graph.layout.margin});
  const scope = single() ? 'Einzeltrials' : 'Gesamtmittel', suffix = `${$('family').value}-${band().id}-${$('mode').value}-${scope}-${channelName()}`;
  const frequencies = id.startsWith('tf-') ? '6–40 Hz' : `${band().low}–${band().high} Hz`;
  const time = $('mode').value === 'time' ? ` · Fenstermitte ${state.data.times[+$('time').value].toFixed(1)} s zum Cue` : '';
  const title = `${state.data.metadata.signal.toUpperCase()} · ${scope} · ${frequencies} · ${$('mode').selectedOptions[0].text}${time}`;
  const side = id.includes('left') ? 'left' : id.includes('right') ? 'right' : null;
  const detail = side ? `${taskLabel(side)} · ${selectionLabel(side)}` : `${channelName()} · Auswahl im JSON-Export dokumentiert`;
  try { await Plotly.relayout(graph, {'title.text': title + '<br><sup>' + detail + '</sup>', 'margin.t': 65});
    await Plotly.downloadImage(graph, {format: 'png', filename: 'erds-' + id + '-' + suffix, scale: 2});
  } finally { await Plotly.relayout(graph, old); }
}
function chooseTrial(side, key) {
  stop(); state.selected[conditionKey(side)] = key; $('scope').value = 'single'; populateTrialSelectors(); render();
}
async function start() {
  state.data = await getJSON('data'); const d = state.data;
  $('recording').textContent = d.title + ' · ' + d.metadata.signal_description;
  $('mapping').textContent = d.metadata.montage_confirmed ? 'Kanalbelegung bestätigt; Positionen bleiben unvermessen.' : 'Reale Zuordnung EEG 1–8 vor wissenschaftlicher Interpretation prüfen.';
  d.channels.forEach((c, i) => { const option = document.createElement('option'); option.value = i; option.textContent = c.site + (c.included ? '' : ' (ausgeschlossen/fehlt)'); $('channel').append(option); });
  $('channel').value = state.channel; populateTrialSelectors();
  for (const warning of d.warnings) { const p = document.createElement('p'); p.className = 'note'; p.textContent = warning; $('warnings').append(p); }
  $('provenance').textContent = JSON.stringify({metadata: d.metadata, exclusions: d.exclusions}, null, 2);
  let absoluteMax = 1;
  for (const c of Object.values(d.conditions)) if (c.n) for (const key of ['power', 'task_power', 'rebound_power']) {
    for (const value of c[key].flat(3)) if (available(value)) absoluteMax = Math.max(absoluteMax, value);
  }
  state.scales.power = [0, absoluteMax * 1.05];
  for (const id of ['band', 'mode', 'scale-min', 'scale-max', 'individual-curves']) $(id).addEventListener('change', () => { stop(); render(); });
  $('family').addEventListener('change', () => { stop(); populateTrialSelectors(); render(); });
  $('scope').addEventListener('change', () => { stop(); populateTrialSelectors(); render(); });
  $('channel').addEventListener('change', () => { state.channel = +$('channel').value; render(); });
  $('metric').addEventListener('change', () => { [$('scale-min').value, $('scale-max').value] = state.scales[$('metric').value]; render(); });
  $('fit-scale').addEventListener('click', async () => {
    stop(); await state.rendering;
    const vals = SIDES.flatMap(side => d.channels.map((_, ci) => value(condition(side), ci, +$('band').value, $('metric').value))).filter(available);
    if (!vals.length) return;
    const magnitude = Math.max(.01, ...vals.map(Math.abs)), lo = $('metric').value === 'power' ? 0 : Math.min(-magnitude * .01, ...vals), hi = Math.max(magnitude * .01, ...vals);
    $('scale-min').value = (lo < 0 ? lo * 1.05 : 0).toPrecision(5); $('scale-max').value = (hi * 1.05).toPrecision(5); render();
  });
  $('standard-scale').addEventListener('click', () => { [$('scale-min').value, $('scale-max').value] = $('metric').value === 'percent' ? [-100, 100] : [0, absoluteMax * 1.05]; render(); });
  for (const side of SIDES) {
    $('trial-' + side).addEventListener('change', () => chooseTrial(side, $('trial-' + side).value));
    for (const [direction, step] of [['prev', -1], ['next', 1]]) $(direction + '-' + side).addEventListener('click', () => {
      const select = $('trial-' + side), index = select.selectedIndex + step;
      if (index >= 0 && index < select.options.length) chooseTrial(side, select.options[index].value);
    });
  }
  $('time').max = d.times.length - 1; $('time').addEventListener('input', selectTime);
  $('time').addEventListener('pointerdown', stop);
  $('time').addEventListener('keydown', event => {
    if (['Home', 'End', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown'].includes(event.key)) stop();
  });
  $('play').addEventListener('click', play);
  document.querySelectorAll('[data-camera]').forEach(button => button.addEventListener('click', () => {
    const eyes = {top: {x: 0, y: 0, z: 2.2}, front: {x: 0, y: 2.2, z: .3}, left: {x: -2.2, y: 0, z: .3}, right: {x: 2.2, y: 0, z: .3}};
    state.camera = {eye: eyes[button.dataset.camera], up: button.dataset.camera === 'top' ? {x: 0, y: 1, z: 0} : {x: 0, y: 0, z: 1}};
    for (const side of SIDES) Plotly.relayout($('head-' + side), {'scene.camera': state.camera});
  }));
  $('png-head').addEventListener('click', async () => { await savePNG('head-left'); await savePNG('head-right'); });
  $('png-curve').addEventListener('click', () => savePNG('curves'));
  $('png-tf').addEventListener('click', async () => { await savePNG('tf-left'); await savePNG('tf-right'); });
  $('selection-json').addEventListener('click', async () => {
    stop(); await state.rendering;
    download(JSON.stringify({schema_version: d.schema_version, metadata: d.metadata, selection: selectionMetadata(),
      times: d.times, frequencies: d.frequencies, bands: d.bands, channels: d.channels,
      left: condition('left'), right: condition('right')}, null, 2), 'application/json', 'erds-auswahl.json');
  });
  $('table-csv').addEventListener('click', async () => {
    stop(); await state.rendering;
    const selection = selectionMetadata(), rows = [['selection_json', 'channel', 'n_left', 'reference_left_uV2', 'power_left_uV2', 'percent_left', 'n_right', 'reference_right_uV2', 'power_right_uV2', 'percent_right']];
    for (const row of $('values').rows) rows.push([JSON.stringify(selection), ...Array.from(row.cells).map(c => c.textContent)]);
    download('\ufeff' + rows.map(r => r.map(v => '"' + String(v).replaceAll('"', '""') + '"').join(',')).join('\r\n'), 'text/csv;charset=utf-8', 'erds-auswahl.csv');
  });
  await render();
  for (const side of SIDES) {
    $('head-' + side).on('plotly_click', event => {
      const point = event.points.find(p => p.data.meta?.sensors);
      if (point) { state.channel = point.customdata[0]; $('channel').value = state.channel; render(); }
    });
    $('bars-' + side).on('plotly_click', event => { state.channel = event.points[0].customdata; $('channel').value = state.channel; render(); });
    $('overview-' + side).on('plotly_click', event => { const key = event.points[0]?.customdata; if (key) chooseTrial(side, key); });
    $('head-' + side).on('plotly_relayout', event => {
      if (event['scene.camera']) {
        state.camera = event['scene.camera']; const other = $('head-' + (side === 'left' ? 'right' : 'left'));
        if (JSON.stringify(other.layout.scene.camera) !== JSON.stringify(state.camera)) Plotly.relayout(other, {'scene.camera': state.camera});
      }
    });
  }
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', async () => {
    state.mesh.color = theme().muted;
    for (const side of SIDES) await Plotly.restyle($('head-' + side), {color: theme().muted}, [0]); render();
  });
}
start().catch(error => { $('status').textContent = 'Fehler: ' + error.message; });
