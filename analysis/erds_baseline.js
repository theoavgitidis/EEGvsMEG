'use strict';
// Separate resting/preparation workspace; the hand-trial normalizations stay intact.
const baselineViewer = (() => {
  const b = {detail: null, reference: null, requestKey: null, plotKey: null, timer: null};
  const active = () => $('scope').value === 'baseline';
  const timed = () => $('baseline-mode').value === 'time';
  const selected = () => $('baseline-section').value;
  const referenceKey = () => $('baseline-reference').value === 'self' ? selected() : $('baseline-reference').value;
  const currentTime = () => timed() && b.detail ? b.detail.times[+$('baseline-time').value] : null;
  const yTitle = () => $('metric').value === 'percent' ? 'Änderung zur Referenz (%)' : 'Bandpower (µV²)';
  function values(metric = $('metric').value) {
    if (!b.detail) return [];
    const bi = +$('band').value;
    return state.data.channels.map((_, ci) => timed() ? b.detail[metric][ci][bi][+$('baseline-time').value] : b.detail['mean_' + metric][ci][bi]);
  }
  function stopPlayback() {
    if (b.timer) clearTimeout(b.timer.timeout);
    b.timer = null; $('baseline-play').textContent = 'Abspielen';
  }
  function sections() {
    const previous = selected(), select = $('baseline-section'); select.replaceChildren();
    for (const s of state.data.baselines || []) if (s.kind === $('baseline-kind').value) {
      const option = document.createElement('option'); option.value = s.key;
      option.textContent = `${s.label} · Aufnahme ${clock(s.start_s)} · ${s.duration_s.toFixed(2)} s`;
      select.append(option);
    }
    if (Array.from(select.options).some(option => option.value === previous)) select.value = previous;
    select.disabled = !select.options.length;
    $('baseline-time').value = 0;
  }
  function activate() {
    if (active() && $('baseline-view').hidden) b.plotKey = null;
    $('baseline-view').hidden = !active();
    document.querySelectorAll('[data-task-view]').forEach(element => { element.hidden = active(); });
    for (const id of ['family', 'mode']) $(id).disabled = active();
    $('metric').options[0].textContent = active() ? 'Änderung zur Referenz · %' : 'ERD/ERS · %';
    if (!active()) stopPlayback();
  }
  function cursor() {
    return timed() ? [{type: 'line', name: 'baseline-cursor', x0: currentTime(), x1: currentTime(),
      y0: 0, y1: 1, yref: 'paper', line: {color: theme().muted, width: 2}}] : [];
  }
  function curveShapes(ci) {
    const reference = b.detail.reference[ci][+$('band').value];
    const level = $('metric').value === 'percent' ? available(reference) ? 0 : null : reference;
    return [...cursor(), ...(available(level) ? [{type: 'line', name: 'baseline-reference-level',
      x0: 0, x1: 1, xref: 'paper', y0: level, y1: level, line: {color: theme().muted, dash: 'dashdot'}}] : [])];
  }
  function plotLayout(title = '') {
    const l = layout(title); l.uirevision = b.requestKey;
    l.xaxis = {...l.xaxis, title: {text: 'Zeit ab Abschnittsbeginn (s)'}, range: [0, b.detail.section.duration_s]};
    return l;
  }
  async function plots() {
    const bi = +$('band').value, metric = $('metric').value;
    const views = ['C3', 'C4'].map(site => {
      const ci = state.data.channels.findIndex(channel => channel.site === site);
      const traces = [{type: 'scatter', mode: 'lines', x: b.detail.times, y: b.detail[metric][ci][bi],
        name: 'Untersuchter Abschnitt', line: {color: '#287cba', width: 2}, connectgaps: false}];
      if (referenceKey() !== selected()) traces.push({type: 'scatter', mode: 'lines',
        x: b.reference.times, y: b.reference[metric][ci][bi], name: 'Referenzabschnitt',
        line: {color: '#c77b14', dash: 'dash', width: 1.5}, connectgaps: false});
      return {site, ci, traces};
    });
    const all = views.flatMap(view => [...view.traces.flatMap(trace => trace.y),
      metric === 'percent' ? 0 : b.detail.reference[view.ci][bi]]).filter(available);
    const low = Math.min(0, ...all), high = Math.max(0, ...all), span = Math.max(1, high - low) * 1.15;
    const range = metric === 'percent' ? [(low + high - span) / 2, (low + high + span) / 2] : [0, high > 0 ? high * 1.15 : 1];
    for (const view of views) {
      const l = plotLayout(); l.yaxis = {...l.yaxis, title: {text: yTitle()}, range, autorange: false};
      l.legend = {orientation: 'h', y: 1.2}; l.shapes = curveShapes(view.ci);
      await Plotly.react($('baseline-' + view.site.toLowerCase()), view.traces, l, config);
      $('baseline-' + view.site.toLowerCase() + '-title').textContent = `${view.site} · ${$('band').selectedOptions[0].text} · Baseline`;
    }
    const w = plotLayout(); w.yaxis.title = {text: 'EEG (µV, nicht zentriert)'}; w.shapes = cursor();
    await Plotly.react($('baseline-waveform'), [{type: 'scatter', mode: 'lines',
      x: b.detail.waveform_times, y: b.detail.waveform_uv, line: {color: '#287cba'}, connectgaps: false}], w, config);
    $('baseline-waveform-title').textContent = `${channelName()} · EEG · ${state.data.metadata.signal}`;
    const tf = plotLayout(); tf.plot_bgcolor = theme().grid;
    tf.yaxis = {...tf.yaxis, title: {text: 'Frequenz (Hz)'}, range: [6, 40]}; tf.shapes = cursor();
    await Plotly.react($('baseline-tf'), [{type: 'heatmap', x: b.detail.times, y: state.data.frequencies,
      z: b.detail.spectral_percent, zmin: -100, zmax: 100, colorscale: DIVERGING, hoverongaps: false,
      colorbar: {title: {text: '%'}}, hovertemplate: '%{x:.2f} s · %{y} Hz<br>%{z:.2f} %<extra></extra>'}], tf, config);
    const clipped = b.detail.spectral_percent.flat().filter(v => available(v) && (v < -100 || v > 100)).length;
    $('baseline-tf-title').textContent = `${channelName()} · Zeit-Frequenz-Karte · ${clipped} Werte außerhalb ±100 %`;
  }
  async function renderBaseline(lo, hi, revision) {
    activate();
    const empty = !selected(); $('baseline-empty').hidden = !empty; $('baseline-content').hidden = empty;
    if (empty) {
      b.detail = b.reference = null; b.plotKey = null; stopPlayback();
      $('baseline-description').textContent = $('baseline-reference-description').textContent = '';
      $('selection-summary').textContent = 'BASELINE · Keine gültigen Abschnitte dieser Art vorhanden.';
      $('status').textContent = 'Bereit · Keine gültige Baseline; kein Ersatz aus Hand-Trials.'; return;
    }
    const requestKey = JSON.stringify([selected(), referenceKey(), channelName()]);
    const detail = await getJSON('baseline', {key: selected(), reference: referenceKey(), channel: channelName()});
    const reference = selected() === referenceKey() ? detail :
      await getJSON('baseline', {key: referenceKey(), reference: referenceKey(), channel: channelName()});
    if (revision !== state.revision) return;
    if (b.detail?.section.key !== detail.section.key) $('baseline-time').value = 0;
    b.detail = detail; b.reference = reference; b.requestKey = requestKey;
    $('baseline-time').max = detail.times.length - 1;
    const s = detail.section, r = detail.reference_section, t = currentTime(), bi = +$('band').value;
    const count = timed() ? s.reference_windows.valid[+$('baseline-time').value] ? 1 : 0 : s.n_valid_windows;
    $('baseline-description').textContent = `${s.label} · Aufnahme ${clock(s.start_s)} bis ${clock(s.end_s)} · ${s.duration_s.toFixed(2)} s · ${s.n_valid_windows}/${s.n_windows} gültige PSD-Fenster (${s.n_missing_windows} fehlen).`;
    $('baseline-reference-description').textContent = `Referenz: Mittel aus ${r.n_valid_windows} gültigen Fenstern von ${r.label}, Aufnahme ${clock(r.start_s)} bis ${clock(r.end_s)}. 100 × (Leistung / Referenzleistung − 1). ` +
      (selected() === referenceKey() ? 'Bei Eigenreferenz ist das Abschnittsmittel 0 %; für Schwankungen Zeitverlauf wählen. ' : '') + 'Keine Änderung der Hand-Trial-Referenzen.';
    $('selection-summary').textContent = `BASELINE · ${s.kind === 'rest' ? 'Ruhebaseline' : 'Trial-Vorbereitung'} · ${s.label} · ${$('band').selectedOptions[0].text} · ${timed() ? 'Zeitverlauf' : 'Abschnittsmittel'}. Referenz: ${r.label}.`;
    $('baseline-time-label').textContent = timed() ? `${t.toFixed(1)} s · Fenster ${(t - .5).toFixed(1)} bis ${(t + .5).toFixed(1)} s` : 'Schieben oder Abspielen öffnet den Zeitverlauf';
    $('baseline-time').setAttribute('aria-valuetext', timed() ? `${t.toFixed(1)} Sekunden ab Abschnittsbeginn` : 'Abschnittsmittel');
    const vals = values(), powers = values('power'), changes = values('percent');
    await sensorHead($('baseline-head'), vals, changes, powers, detail.reference.map(row => row[bi]), count,
      'Gültige PSD-Fenster', lo, hi, 'Relative Änderung');
    const finite = vals.filter(available), clipped = finite.filter(v => v < lo || v > hi).length;
    $('baseline-color-note').textContent = ($('metric').value === 'percent' ? 'Blau = Abnahme, Rot = Zunahme zur gewählten Referenz.' : 'Absolute Bandpower in µV²; hell = geringer, dunkelblau = höher.') +
      ` Grau = nicht berechenbar. ${clipped} Elektrodenwerte außerhalb der Farbskala. Farben sind kein Signifikanztest.`;
    const bar = layout(); bar.margin = {l: 45, r: 80, t: 15, b: 45};
    const barLo = Math.min(0, lo, ...finite), barHi = Math.max(hi, ...finite), barSpan = barHi - barLo;
    bar.xaxis = {...bar.xaxis, title: {text: yTitle()}, range: [barLo - barSpan * .12, barHi + barSpan * .18], autorange: false};
    bar.yaxis.autorange = 'reversed';
    await Plotly.react($('baseline-bars'), [{type: 'bar', orientation: 'h', y: state.data.channels.map(c => c.site),
      x: vals, text: vals.map(v => fmt(v) + ' ' + unit()), textposition: 'outside', cliponaxis: false,
      marker: {color: vals.map(v => colorFor(v, lo, hi))}, customdata: state.data.channels.map((_, ci) => ci)}], bar, config);
    const plotKey = JSON.stringify([requestKey, bi, $('metric').value, lo, hi, theme()]);
    if (b.plotKey !== plotKey) { await plots(); b.plotKey = plotKey; }
    else {
      for (const site of ['C3', 'C4']) await Plotly.relayout($('baseline-' + site.toLowerCase()),
        {shapes: curveShapes(state.data.channels.findIndex(c => c.site === site))});
      for (const id of ['baseline-waveform', 'baseline-tf']) await Plotly.relayout($(id), {shapes: cursor()});
    }
    const body = $('baseline-values'); body.replaceChildren();
    state.data.channels.forEach((channel, ci) => {
      const row = document.createElement('tr');
      for (const value of [channel.site, fmt(detail.reference[ci][bi]), fmt(powers[ci]), fmt(changes[ci]), available(powers[ci]) ? count : 0]) {
        const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
      }
      row.addEventListener('click', () => { state.channel = ci; $('channel').value = ci; render(); }); body.append(row);
    });
    if (!$('baseline-head').baselineBound) {
      $('baseline-head').on('plotly_click', event => {
        const point = event.points.find(p => p.data.meta?.sensors);
        if (point) { state.channel = point.customdata[0]; $('channel').value = state.channel; render(); }
      });
      $('baseline-bars').on('plotly_click', event => { state.channel = event.points[0].customdata; $('channel').value = state.channel; render(); });
      $('baseline-head').baselineBound = true;
    }
    if (revision === state.revision) $('status').textContent = 'Bereit · Baseline · ' + state.data.metadata.signal_description + ' · Deskriptive Leistungsschwankungen';
  }
  async function playBaseline() {
    if (b.timer) return stopPlayback();
    if (!b.detail) return;
    $('baseline-mode').value = 'time';
    if (+$('baseline-time').value >= b.detail.times.length - 1) $('baseline-time').value = 0;
    const playback = {timeout: null}; b.timer = playback; $('baseline-play').textContent = 'Pause';
    async function frame() {
      await render(); if (b.timer !== playback || !active()) return;
      if (+$('baseline-time').value >= b.detail.times.length - 1) return stopPlayback();
      playback.timeout = setTimeout(() => { $('baseline-time').value = +$('baseline-time').value + 1; frame(); }, 400);
    }
    await frame();
  }
  function exportData() {
    return {schema_version: state.data.schema_version, metadata: state.data.metadata,
      selection: {scope: 'baseline', kind: $('baseline-kind').value, key: selected(), reference_key: referenceKey(),
        signal: state.data.metadata.signal, source_unit: state.data.metadata.source_unit,
        reference_start_s: b.detail.reference_section.start_s, reference_end_s: b.detail.reference_section.end_s,
        reference_n_valid_windows: b.detail.reference_section.n_valid_windows,
        channel: channelName(), band: band(), mode: $('baseline-mode').value, window_center_s: currentTime(),
        metric: $('metric').value, color_limits: scale(), tf_color_limits: [-100, 100]},
      frequencies: state.data.frequencies, channels: state.data.channels, detail: b.detail, reference_detail: b.reference};
  }
  function start() {
    sections();
    for (const section of state.data.baselines || []) {
      const option = document.createElement('option'); option.value = section.key;
      option.textContent = `${section.kind === 'rest' ? 'Ruhe' : 'Vorbereitung'} · ${section.label} · Aufnahme ${clock(section.start_s)}`;
      $('baseline-reference').append(option);
    }
    $('baseline-provenance').textContent = JSON.stringify({exclusions: state.data.baseline_exclusions || [], metadata: state.data.metadata}, null, 2);
    $('baseline-kind').addEventListener('change', () => { stopPlayback(); sections(); render(); });
    for (const id of ['baseline-section', 'baseline-reference', 'baseline-mode']) $(id).addEventListener('change', () => { stopPlayback(); render(); });
    $('baseline-time').addEventListener('input', () => { stopPlayback(); $('baseline-mode').value = 'time'; render(); });
    $('baseline-time').addEventListener('pointerdown', stopPlayback);
    $('baseline-time').addEventListener('keydown', stopPlayback);
    $('baseline-play').addEventListener('click', playBaseline);
    for (const id of ['band', 'metric', 'channel', 'scale-min', 'scale-max']) $(id).addEventListener('change', stopPlayback);
    document.querySelectorAll('[data-baseline-camera]').forEach(button => button.addEventListener('click', () => {
      const eye = {top: {x: 0, y: 0, z: 2.2}, front: {x: 0, y: 2.2, z: .3}, left: {x: -2.2, y: 0, z: .3}, right: {x: 2.2, y: 0, z: .3}}[button.dataset.baselineCamera];
      Plotly.relayout($('baseline-head'), {'scene.camera': {eye, up: eye.z > 2 ? {x: 0, y: 1, z: 0} : {x: 0, y: 0, z: 1}}});
    }));
    $('baseline-json').addEventListener('click', async () => { stopPlayback(); await state.rendering;
      download(JSON.stringify(exportData(), null, 2), 'application/json', 'erds-baseline-auswahl.json'); });
    $('baseline-csv').addEventListener('click', async () => { stopPlayback(); await state.rendering;
      const selection = JSON.stringify(exportData().selection), rows = [['selection_json', 'channel', 'reference_uV2', 'power_uV2', 'percent', 'valid_windows']];
      for (const row of $('baseline-values').rows) rows.push([selection, ...Array.from(row.cells).map(cell => cell.textContent)]);
      download('\ufeff' + rows.map(row => row.map(v => '"' + String(v).replaceAll('"', '""') + '"').join(',')).join('\r\n'), 'text/csv;charset=utf-8', 'erds-baseline-tabelle.csv'); });
    document.querySelectorAll('[data-baseline-png]').forEach(button => button.addEventListener('click', async () => {
      stopPlayback(); await state.rendering;
      const id = button.dataset.baselinePng, graph = $(id), old = structuredClone({title: graph.layout.title, margin: graph.layout.margin});
      const site = id.endsWith('c3') ? 'C3' : id.endsWith('c4') ? 'C4' : id === 'baseline-head' ? 'Alle Elektroden' : channelName();
      const frequency = id === 'baseline-waveform' ? 'EEG ohne zusätzliche Filter' : id === 'baseline-tf' ? '6–40 Hz · %' : $('band').selectedOptions[0].text;
      const time = timed() ? ` · ${currentTime().toFixed(1)} s ab Beginn` : ' · Abschnittsmittel';
      const safe = text => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
      try {
        await Plotly.relayout(graph, {'title.text': `${state.data.metadata.signal} · ${site} · ${frequency}${time}<br><sup>${safe(b.detail.section.label)}<br>Referenz: ${safe(b.detail.reference_section.label)}</sup>`, 'margin.t': 90});
        await Plotly.downloadImage(graph, {format: 'png', scale: 2, filename: id + '-' + b.detail.section.kind + '-' + site});
      } finally { await Plotly.relayout(graph, old); }
    }));
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if ($('baseline-head').data) Plotly.restyle($('baseline-head'), {color: theme().muted}, [0]);
    });
  }
  return {start, activate, render: renderBaseline, stop: stopPlayback, values};
})();
