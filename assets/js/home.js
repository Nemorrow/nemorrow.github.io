(() => {
  'use strict';
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  const preference = matchMedia('(prefers-color-scheme: dark)');
  let chosen = false;
  try { chosen = ['light', 'dark'].includes(localStorage.getItem('homepage-theme')); } catch (_) {}
  function applyTheme(theme) {
    root.dataset.theme = theme;
    toggle.setAttribute('aria-pressed', String(theme === 'dark'));
    toggle.setAttribute('aria-label', theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
  }
  if (toggle) {
    applyTheme(root.dataset.theme || (preference.matches ? 'dark' : 'light'));
    toggle.addEventListener('click', () => {
      chosen = true;
      const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      applyTheme(theme);
      try { localStorage.setItem('homepage-theme', theme); } catch (_) {}
    });
    preference.addEventListener('change', event => { if (!chosen) applyTheme(event.matches ? 'dark' : 'light'); });
  }

  document.querySelectorAll('.bibtex-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const panel = document.getElementById(button.getAttribute('aria-controls'));
      const expanded = button.getAttribute('aria-expanded') !== 'true';
      button.setAttribute('aria-expanded', String(expanded));
      panel.hidden = !expanded;
    });
  });
  document.querySelectorAll('.bibtex-copy').forEach(button => {
    let resetCopyLabel;
    button.addEventListener('click', async () => {
      const panel = button.closest('.publication-citation');
      const status = panel.querySelector('.citation-status');
      clearTimeout(resetCopyLabel);
      button.textContent = 'Copy';
      status.textContent = '';
      try {
        await navigator.clipboard.writeText(panel.querySelector('code').textContent);
        button.textContent = 'Copied';
        resetCopyLabel = setTimeout(() => { button.textContent = 'Copy'; }, 2000);
      } catch (_) {
        status.textContent = 'Select the text below to copy.';
      }
    });
  });

  const section = document.querySelector('[data-usage-url]');
  if (!section) return;
  const detail = document.getElementById('usage-detail');
  const tip = document.createElement('div');
  tip.id = 'usage-tooltip'; tip.className = 'usage-tooltip'; tip.hidden = true;
  tip.setAttribute('role', 'tooltip'); document.body.append(tip);
  let activeDay = null;
  const hideTip = () => { tip.hidden = true; if (activeDay) activeDay.removeAttribute('aria-describedby'); activeDay = null; };
  function showTip(button, message) {
    if (activeDay && activeDay !== button) activeDay.removeAttribute('aria-describedby');
    activeDay = button; tip.textContent = message; tip.hidden = false;
    button.setAttribute('aria-describedby', tip.id);
    const cell = button.getBoundingClientRect(), box = tip.getBoundingClientRect();
    tip.style.left = `${Math.max(8, Math.min(innerWidth - box.width - 8, cell.left + cell.width / 2 - box.width / 2))}px`;
    tip.style.top = `${cell.top >= box.height + 12 ? cell.top - box.height - 8 : cell.bottom + 8}px`;
  }
  window.addEventListener('scroll', hideTip, true); window.addEventListener('resize', hideTip);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') hideTip(); });
  document.addEventListener('pointerdown', event => { if (!event.target.closest('.usage-day')) hideTip(); });
  const millions = value => `${(value / 1000000).toFixed(1)}M`;
  const compact = new Intl.NumberFormat('en-US', { notation: 'compact', minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const iso = value => value.toISOString().slice(0, 10);
  function render(data) {
    if (data.schemaVersion !== 1 || !Array.isArray(data.days) || !data.days.length) throw Error('No daily data');
    const days = new Map();
    data.days.forEach(day => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date) || !Number.isSafeInteger(day.tokens) || day.tokens < 0 || days.has(day.date)) throw Error('Invalid daily data');
      days.set(day.date, day.tokens);
    });
    const dates = [...days.keys()].sort();
    const end = new Date(dates[dates.length - 1] + 'T00:00:00Z');
    const start = new Date(end);
    start.setUTCDate(start.getUTCDate() - 181);
    start.setUTCDate(start.getUTCDate() - start.getUTCDay());
    const values = [...days.values()];
    const total = values.reduce((sum, value) => sum + value, 0);
    const peak = Math.max(...values);
    const stats = document.getElementById('usage-stats');
    stats.replaceChildren();
    [[compact.format(total), 'Total tokens'], [compact.format(total / days.size), 'Avg tokens / day']].forEach(([number, label]) => {
      const item = document.createElement('div');
      const value = document.createElement('strong'); value.textContent = number;
      const caption = document.createElement('span'); caption.textContent = label;
      item.append(caption, value); stats.append(item);
    });
    stats.hidden = false;
    hideTip();
    const calendar = document.getElementById('usage-calendar');
    calendar.replaceChildren();
    const months = document.createElement('div'); months.className = 'usage-months';
    const body = document.createElement('div'); body.className = 'usage-calendar-body';
    const weekdays = document.createElement('div'); weekdays.className = 'usage-weekdays';
    ['','Mon','','Wed','','Fri',''].forEach(label => { const span = document.createElement('span'); span.textContent = label; weekdays.append(span); });
    const grid = document.createElement('div'); grid.className = 'usage-grid';
    grid.setAttribute('role', 'group'); grid.setAttribute('aria-label', 'Daily token activity. Use arrow keys to explore days.');
    let week = 0, lastMonth = '', buttons = [];
    for (let cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
      const day = iso(cursor), tokens = days.get(day);
      if (cursor.getUTCDay() === 0) {
        const month = cursor.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' });
        const label = document.createElement('span'); label.textContent = month !== lastMonth ? month : ''; months.append(label); lastMonth = month; week++;
      }
      const button = document.createElement('button'); button.type = 'button'; button.tabIndex = -1;
      button.className = 'usage-day';
      const level = tokens === undefined ? 'missing' : tokens === 0 ? 'zero' : String(Math.min(4, Math.max(1, Math.ceil(tokens / peak * 4))));
      button.dataset.level = level;
      const dateLabel = cursor.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
      const message = `${dateLabel} — ${tokens === undefined ? '0' : millions(tokens)}`;
      button.setAttribute('aria-label', message);
      const show = () => showTip(button, message);
      button.addEventListener('mouseenter', show); button.addEventListener('focus', show); button.addEventListener('click', show);
      const index = buttons.length;
      button.addEventListener('keydown', event => {
        let next = index;
        if (event.key === 'ArrowRight') next += 7;
        else if (event.key === 'ArrowLeft') next -= 7;
        else if (event.key === 'ArrowDown') next++;
        else if (event.key === 'ArrowUp') next--;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = buttons.length - 1;
        else return;
        event.preventDefault(); next = Math.max(0, Math.min(buttons.length - 1, next));
        buttons.forEach(b => { b.tabIndex = -1; }); buttons[next].tabIndex = 0; buttons[next].focus();
      });
      buttons.push(button); grid.append(button);
    }
    buttons[buttons.length - 1].tabIndex = 0;
    months.style.setProperty('--weeks', week); grid.style.setProperty('--weeks', week);
    body.append(weekdays, grid); calendar.append(months, body);
    detail.textContent = '';
    grid.addEventListener('mouseleave', hideTip);
    grid.addEventListener('focusout', event => {
      if (!grid.contains(event.relatedTarget)) hideTip();
    });
    section.dataset.state = 'ready';
  }
  let signature = '';
  const cacheKey = `homepage-usage-v1:${section.dataset.usageEndpoint || section.dataset.usageUrl}`;
  const initialSnapshots = [];
  try {
    const embedded = JSON.parse(document.getElementById('usage-initial-data').textContent);
    if (embedded) initialSnapshots.push({ data: embedded, source: 'embedded' });
  } catch (_) {}
  try {
    const cached = JSON.parse(localStorage.getItem(cacheKey));
    if (cached) initialSnapshots.push({ data: cached, source: 'cache' });
  } catch (_) {}
  initialSnapshots.sort((a, b) => (Date.parse(b.data.syncedAt) || 0) - (Date.parse(a.data.syncedAt) || 0));
  for (const snapshot of initialSnapshots) {
    try {
      render(snapshot.data);
      signature = JSON.stringify(snapshot.data.days);
      section.dataset.source = snapshot.source;
      break;
    } catch (_) { /* Try the other snapshot if this one is invalid. */ }
  }

  async function loadUsage() {
    const endpoint = section.dataset.usageEndpoint;
    const urls = [...new Set([endpoint, section.dataset.usageUrl].filter(Boolean))];
    for (const url of urls) {
      if (endpoint && url !== endpoint && section.dataset.state === 'ready') return;
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        let data;
        try {
          const response = await fetch(url, {cache: 'no-store', credentials: 'omit', signal: controller.signal});
          if (!response.ok) throw Error('Usage unavailable');
          data = await response.json();
        } finally { clearTimeout(timer); }
        const nextSignature = JSON.stringify(data.days);
        if (nextSignature !== signature) { render(data); signature = nextSignature; }
        try { localStorage.setItem(cacheKey, JSON.stringify(data)); } catch (_) {}
        section.dataset.source = endpoint && url === endpoint ? 'endpoint' : 'snapshot';
        return;
      } catch (_) { /* Try the saved snapshot; preserve a rendered calendar on failure. */ }
    }
    if (section.dataset.state !== 'ready') {
      detail.textContent = 'Token usage is currently unavailable. Please check back later.';
      section.dataset.state = 'unavailable';
    }
  }
  loadUsage();
  setInterval(() => { if (!document.hidden) loadUsage(); }, 300000);
})();
