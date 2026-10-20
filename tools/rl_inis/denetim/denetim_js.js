
(function () {
  const D = JSON.parse(document.getElementById('data').textContent);
  const NAMES = ['dur', 'ileri', 'sol-ileri', 'sol', 'sol-geri', 'geri', 'sağ-geri', 'sağ', 'sağ-ileri', 'alçal'];
  const CLS = ['safe-soft', 'safe-hard', 'terrain-hazard', 'structure', 'water', 'vehicle-animal', 'person', 'unknown'];
  const OUT = { safe_landing: 'güvenli iniş', unsafe_landing: 'güvensiz iniş', timeout: 'süre doldu', out_of_bounds: 'sahne dışı', collision: 'çarpma' };
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const imgs = D.scenes.map(s => ({ photo: load(s.photo), mask: load(s.mask), sora: load(s.sora) }));
  function load(src) { const i = new Image(); i.src = src; i.onload = () => draw(); return i; }
  let ep = 0, k = 0, layer = 'photo', timer = null;
  const map = document.getElementById('map'), mx = map.getContext('2d');
  const view = document.getElementById('view'), vx = view.getContext('2d');
  const slider = document.getElementById('slider');

  document.getElementById('meta').textContent =
    `model: ${D.model.split('/').slice(-2).join('/')} · ${D.episodes.length} bölüm · SORA mesafesi ${D.sora_m} m · ortam: nominal PX4 dinamiği, 30 s`;

  // episode table
  const tb = document.getElementById('eps');
  D.episodes.forEach((e, i) => {
    const tr = document.createElement('tr');
    tr.tabIndex = 0;
    const sc = D.scenes[e.scene];
    const okc = e.success ? 'ok' : 'hata';
    tr.innerHTML = `<td>${sc.name}</td><td>${e.start}</td>
      <td><span class="chip ${okc}">${OUT[e.outcome] || e.outcome}</span></td>
      <td><span class="chip ${e.sora_ok ? 'ok' : 'hata'}">${e.sora_ok ? 'uyumlu' : 'değil'} · ${e.sora_m.toFixed(1)} m</span></td>
      <td class="num">${e.steps.length}</td><td class="num">${e.t.toFixed(1)} s</td><td class="num">${e.total.toFixed(1)}</td>
      <td><span class="bar" style="width:${Math.round(80 * e.agree)}px;background:${css('--ok')}"></span>
          <span class="mono"> ${(100 * e.agree).toFixed(0)} %</span></td>
      <td class="num">${(100 * e.wrong).toFixed(0)} %</td>`;
    tr.onclick = () => select(i);
    tr.onkeydown = ev => { if (ev.key === 'Enter') select(i); };
    tb.appendChild(tr);
  });

  function select(i) {
    ep = i; k = 0; stop();
    [...tb.children].forEach((tr, j) => tr.classList.toggle('sel', j === i));
    const n = D.episodes[i].steps.length;
    slider.max = n - 1; slider.value = 0;
    const strip = document.getElementById('strip');
    strip.innerHTML = '';
    D.episodes[i].steps.forEach((s, j) => {
      const el = document.createElement('i');
      el.style.background = css(s.v === 'ok' ? '--ok' : s.v === 'dikkat' ? '--warn' : '--bad');
      el.title = `${j}: ${NAMES[s.a]} (${s.v})`;
      el.onclick = () => { k = j; slider.value = j; draw(); };
      strip.appendChild(el);
    });
    draw();
  }

  function w2i(sc, x, y) { return [(x / sc.size[0] + 0.5) * sc.w, (0.5 - y / sc.size[1]) * sc.h]; }

  function arrow(ctx, x0, y0, ang, len, col, dash, width) {
    const x1 = x0 + Math.cos(ang) * len, y1 = y0 - Math.sin(ang) * len;
    ctx.save();
    ctx.setLineDash(dash || []);
    for (const [c, w] of [['rgba(0,0,0,.75)', width + 3], [col, width]]) {
      ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
      ctx.setLineDash([]);
      const h = Math.max(8, len * 0.28);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - Math.cos(ang - 0.45) * h, y1 + Math.sin(ang - 0.45) * h);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - Math.cos(ang + 0.45) * h, y1 + Math.sin(ang + 0.45) * h);
      ctx.stroke();
      ctx.setLineDash(dash || []);
    }
    ctx.restore();
  }
  function ring(ctx, x, y, r, col, dash) {
    ctx.save(); ctx.setLineDash(dash || []);
    for (const [c, w] of [['rgba(0,0,0,.75)', 6], [col, 3]]) { ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.stroke(); }
    ctx.restore();
  }
  function cross(ctx, x, y, col) {
    for (const [c, w] of [['rgba(0,0,0,.8)', 5], [col, 2.5]]) {
      ctx.strokeStyle = c; ctx.lineWidth = w; ctx.beginPath();
      ctx.moveTo(x - 10, y); ctx.lineTo(x + 10, y); ctx.moveTo(x, y - 10); ctx.lineTo(x, y + 10); ctx.stroke();
    }
  }

  function draw() {
    const e = D.episodes[ep], sc = D.scenes[e.scene], s = e.steps[k];
    if (map.width !== sc.w || map.height !== sc.h) { map.width = sc.w; map.height = sc.h; }
    const im = imgs[e.scene];
    mx.clearRect(0, 0, sc.w, sc.h);
    if (im.photo.complete) mx.drawImage(im.photo, 0, 0, sc.w, sc.h);
    if (layer === 'mask' && im.mask.complete) mx.drawImage(im.mask, 0, 0, sc.w, sc.h);
    if (layer === 'sora' && im.sora.complete) mx.drawImage(im.sora, 0, 0, sc.w, sc.h);
    const scale = sc.w / sc.size[0];
    // path so far
    mx.lineWidth = 2.5; mx.strokeStyle = 'rgba(255,255,255,.9)'; mx.beginPath();
    e.steps.slice(0, k + 1).forEach((p, j) => { const [u, v] = w2i(sc, p.x, p.y); j ? mx.lineTo(u, v) : mx.moveTo(u, v); });
    mx.stroke();
    e.steps.forEach((p, j) => {
      if (j > k) return;
      const [u, v] = w2i(sc, p.cx, p.cy);
      mx.fillStyle = css(p.v === 'ok' ? '--ok' : p.v === 'dikkat' ? '--warn' : '--bad');
      mx.beginPath(); mx.arc(u, v, 2.5, 0, 2 * Math.PI); mx.fill();
    });
    // footprint
    mx.strokeStyle = '#4fc3f7'; mx.lineWidth = 2; mx.beginPath();
    s.fp.forEach(([x, y], j) => { const [u, v] = w2i(sc, x, y); j ? mx.lineTo(u, v) : mx.moveTo(u, v); });
    mx.closePath(); mx.stroke();
    const [cu, cv] = w2i(sc, s.cx, s.cy);
    const L = Math.max(30, 6 * scale);
    // rule
    const [tu, tv] = w2i(sc, s.tx, s.ty);
    mx.fillStyle = '#2ec4d6'; mx.beginPath(); mx.arc(tu, tv, 5, 0, 2 * Math.PI); mx.fill();
    if (s.rule === 9) ring(mx, cu, cv, 22, '#2ec4d6', [5, 4]);
    else arrow(mx, cu, cv, (s.yaw + (s.rule - 1) * 45) * Math.PI / 180, L, '#2ec4d6', [6, 5], 2.5);
    // policy
    if (s.a === 9) ring(mx, cu, cv, 14, '#ffffff');
    else if (s.a === 0) { mx.strokeStyle = '#fff'; mx.lineWidth = 3; mx.strokeRect(cu - 10, cv - 10, 20, 20); }
    else arrow(mx, cu, cv, (s.yaw + (s.a - 1) * 45) * Math.PI / 180, L, '#ffffff', null, 3.5);
    cross(mx, cu, cv, s.csafe ? '#5be37a' : '#ff5a4e');
    // landing point at the end
    if (k === e.steps.length - 1) {
      const [lu, lv] = w2i(sc, e.landing[0], e.landing[1]);
      ring(mx, lu, lv, 9, e.success ? '#5be37a' : '#ff5a4e');
    }
    drawView(s);
    panel(e, s);
    document.getElementById('stepno').textContent = `${k + 1}/${e.steps.length}`;
    [...document.getElementById('strip').children].forEach((el, j) => el.classList.toggle('cur', j === k));
  }

  const vimg = new Image();
  function drawView(s) {
    vimg.onload = () => {
      vx.imageSmoothingEnabled = false;
      vx.drawImage(vimg, 0, 0, 256, 256);
      const c = 128;
      if (s.rule === 9) ring(vx, c, c, 34, '#2ec4d6', [5, 4]);
      else arrow(vx, c, c, Math.PI / 2 + (s.rule - 1) * Math.PI / 4, 80, '#2ec4d6', [6, 5], 2.5);
      if (s.a === 9) ring(vx, c, c, 22, '#ffffff');
      else if (s.a === 0) { vx.strokeStyle = '#fff'; vx.lineWidth = 3; vx.strokeRect(c - 14, c - 14, 28, 28); }
      else arrow(vx, c, c, Math.PI / 2 + (s.a - 1) * Math.PI / 4, 90, '#ffffff', null, 3.5);
      cross(vx, c, c, s.csafe ? '#5be37a' : '#ff5a4e');
    };
    vimg.src = s.view;
  }

  function panel(e, s) {
    const vd = document.getElementById('verdict');
    vd.className = 'verdict ' + s.v;
    vd.innerHTML = `<b>${s.v === 'ok' ? '✔ Kurala uyuyor' : s.v === 'dikkat' ? '⚠ Tartışmalı' : '✖ Kurala ters'}</b><span>${s.why}</span>`;
    const kv = [
      ['Zaman', `${s.t.toFixed(2)} s`],
      ['Kamera irtifası', `${s.z.toFixed(1)} m`],
      ['Politika', `<b>${s.a} ${NAMES[s.a]}</b>`],
      ['SORA kuralı', `${s.rule} ${NAMES[s.rule]}`],
      ['Ortadaki sınıf', CLS[s.ccls]],
      ['Ortanın tehlikeye uzaklığı', `${s.chaz >= 99 ? '> 99' : s.chaz.toFixed(1)} m`],
      ['Orta SORA-güvenli mi', s.csafe ? '<span class="chip ok">evet</span>' : '<span class="chip hata">hayır</span>'],
      ['Görüşte güvenli pay', `${(100 * s.share).toFixed(1)} %`],
      ['En yakın güvenli nokta', `${Math.hypot(s.tx - s.cx, s.ty - s.cy).toFixed(1)} m`],
      ['Bölüm sonucu', `${OUT[e.outcome] || e.outcome}, SORA ${e.sora_ok ? 'uyumlu' : 'değil'}`],
    ];
    document.getElementById('kv').innerHTML = kv.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('');
    const sg = x => (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toFixed(2);
    const endTxt = s.rend ? `<b>${sg(s.rend)}</b> (${OUT[e.outcome] || e.outcome}: 5 m'de görüşün çoğunluğu ${e.success ? 'güvenli' : 'güvenli değil'})` : '0';
    const rw = [
      ['Zaman', sg(s.rt)],
      ['Görüş (güvenli − güvensiz pay)', sg(s.rs)],
      ['Eylem', `${sg(s.ra)} (${NAMES[s.a]})`],
      ['Bitiş', endTxt],
      ['Adım toplamı', `<b>${sg(s.r)}</b>`],
      ['Şimdiye kadar', `<b>${sg(s.cum)}</b>`],
    ];
    document.getElementById('reward').innerHTML = rw.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('');
  }

  function step(d) { const n = D.episodes[ep].steps.length; k = Math.max(0, Math.min(n - 1, k + d)); slider.value = k; draw(); }
  function stop() { if (timer) { clearInterval(timer); timer = null; } document.getElementById('b-play').textContent = '▶ Oynat'; }
  function play() {
    if (timer) { stop(); return; }
    if (k >= D.episodes[ep].steps.length - 1) k = 0;
    document.getElementById('b-play').textContent = '❚❚ Durdur';
    timer = setInterval(() => { if (k >= D.episodes[ep].steps.length - 1) { stop(); return; } step(1); }, 250);
  }
  slider.oninput = () => { k = +slider.value; draw(); };
  document.getElementById('b-play').onclick = play;
  document.getElementById('b-prev').onclick = () => { stop(); step(-1); };
  document.getElementById('b-next').onclick = () => { stop(); step(1); };
  for (const [id, l] of [['b-photo', 'photo'], ['b-mask', 'mask'], ['b-sora', 'sora']]) {
    document.getElementById(id).onclick = () => {
      layer = l;
      for (const b of ['b-photo', 'b-mask', 'b-sora']) document.getElementById(b).setAttribute('aria-pressed', b === id);
      draw();
    };
  }
  document.addEventListener('keydown', ev => {
    if (ev.target.tagName === 'INPUT' && ev.target.type !== 'range') return;
    if (ev.key === 'ArrowRight') { stop(); step(1); ev.preventDefault(); }
    else if (ev.key === 'ArrowLeft') { stop(); step(-1); ev.preventDefault(); }
    else if (ev.key === ' ') { play(); ev.preventDefault(); }
  });
  // start on the first episode that has a lateral move, else the first one
  const first = Math.max(0, D.episodes.findIndex(e => e.steps.some(s => s.a >= 1 && s.a <= 8)));
  select(first);
})();
