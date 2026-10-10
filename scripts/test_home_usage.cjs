const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/js/home.js'), 'utf8');
const cacheKey = 'homepage-usage-v1:/assets/data/codex-usage.json';

function usage(syncedAt, tokens) {
  return { schemaVersion: 1, syncedAt, days: [{ date: '2026-10-10', tokens }] };
}

class Element {
  constructor() {
    this.children = [];
    this.dataset = {};
    this.style = { setProperty() {} };
    this.attributes = {};
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  addEventListener() {}
}

function homepage({ embedded, cached, response, fail = false }) {
  const section = new Element();
  section.dataset.usageEndpoint = '';
  section.dataset.usageUrl = '/assets/data/codex-usage.json';
  const detail = new Element();
  detail.textContent = '';
  const stats = new Element();
  const calendar = new Element();
  const elements = {
    'usage-initial-data': { textContent: JSON.stringify(embedded) },
    'usage-detail': detail,
    'usage-stats': stats,
    'usage-calendar': calendar
  };
  const storage = new Map(cached ? [[cacheKey, JSON.stringify(cached)]] : []);
  const writes = [];
  const document = {
    documentElement: new Element(),
    body: new Element(),
    hidden: false,
    getElementById: id => elements[id] || null,
    querySelector: () => section,
    querySelectorAll: () => [],
    createElement: () => new Element(),
    addEventListener() {}
  };
  vm.runInNewContext(source, {
    document,
    window: { addEventListener() {} },
    localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => { storage.set(key, value); writes.push(key); }
    },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    fetch: async () => {
      if (fail) throw new Error('Network unavailable');
      return { ok: true, json: async () => response };
    },
    AbortController,
    setTimeout: () => 1,
    clearTimeout() {},
    setInterval() {}
  });
  return {
    section, detail, calendar, writes,
    total: () => stats.children[0].children[1].textContent,
    cache: () => JSON.parse(storage.get(cacheKey)),
    settle: () => new Promise(resolve => setImmediate(resolve))
  };
}

test('a stale fetch preserves newer cached data, its source and its storage', async () => {
  const cached = usage('2026-10-11T02:00:00Z', 50_000_000);
  const page = homepage({
    embedded: usage('2026-10-11T00:00:00Z', 10_000_000),
    cached,
    response: usage('2026-10-11T01:00:00Z', 20_000_000)
  });
  const initialCalendar = page.calendar.children[0];
  assert.equal(page.total(), '50.0M');
  await page.settle();
  assert.equal(page.total(), '50.0M');
  assert.equal(page.section.dataset.source, 'cache');
  assert.equal(page.calendar.children[0], initialCalendar);
  assert.deepEqual(page.cache(), cached);
  assert.equal(page.writes.length, 0);
});

test('a newer fetch updates the calendar and cache', async () => {
  const response = usage('2026-10-11T02:00:00Z', 30_000_000);
  const page = homepage({ embedded: usage('2026-10-11T00:00:00Z', 10_000_000), response });
  const initialCalendar = page.calendar.children[0];
  await page.settle();
  assert.equal(page.total(), '30.0M');
  assert.equal(page.section.dataset.source, 'snapshot');
  assert.notEqual(page.calendar.children[0], initialCalendar);
  assert.deepEqual(page.cache(), response);
});

test('an unchanged day series with a newer timestamp advances cache without redrawing', async () => {
  const response = usage('2026-10-11T02:00:00Z', 10_000_000);
  const page = homepage({ embedded: usage('2026-10-11T00:00:00Z', 10_000_000), response });
  const initialCalendar = page.calendar.children[0];
  await page.settle();
  assert.equal(page.total(), '10.0M');
  assert.equal(page.calendar.children[0], initialCalendar);
  assert.deepEqual(page.cache(), response);
});

test('a network failure preserves the first-visit embedded snapshot', async () => {
  const page = homepage({ embedded: usage('2026-10-11T00:00:00Z', 10_000_000), fail: true });
  const initialCalendar = page.calendar.children[0];
  await page.settle();
  assert.equal(page.total(), '10.0M');
  assert.equal(page.section.dataset.state, 'ready');
  assert.equal(page.section.dataset.source, 'embedded');
  assert.equal(page.detail.textContent, '');
  assert.equal(page.calendar.children[0], initialCalendar);
  assert.equal(page.writes.length, 0);
});
