// Band Evidence client. The server is the only source of truth: every view is re-fetched after a mutation.

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const csrf = () => $('meta[name="csrf-token"]')?.content || '';
const newKey = () => `ui-${crypto.randomUUID()}`;
const CONTROLS = 'input:not([type=hidden]), select, textarea';

function setOffline(offline) {
  const banner = $('[data-offline]');
  if (banner) banner.hidden = !offline;
}

async function fetchHTML(url) {
  let res;
  try {
    res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin' });
  } catch (err) {
    setOffline(true);
    throw err;
  }
  setOffline(false);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.text();
}

async function callAPI(url, body, key, multipart = false) {
  const headers = { 'X-CSRFToken': csrf(), 'Idempotency-Key': key };
  if (!multipart) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(url, { method: 'POST', headers, body: multipart ? body : JSON.stringify(body), credentials: 'same-origin' });
  } catch {
    setOffline(true);
    return { error: { code: 'offline', message: 'Could not reach the app. Your changes are kept here; try again.', fields: {}, retryable: true } };
  }
  setOffline(false);
  try {
    return await res.json();
  } catch {
    return { error: { code: `http_${res.status}`, message: res.status === 403 ? 'The request was refused. Reload the page and try again.' : 'Unexpected response. Nothing was changed.', fields: {}, retryable: true } };
  }
}

function toast(messages) {
  if (!messages?.length) return;
  let region = $('#toast');
  if (!region) {
    region = document.createElement('div');
    region.id = 'toast';
    region.setAttribute('role', 'status');
    document.body.append(region);
  }
  region.innerHTML = '';
  for (const m of messages) {
    const p = document.createElement('p');
    p.textContent = m.message || m;
    region.append(p);
  }
  region.classList.add('show');
  clearTimeout(region._t);
  region._t = setTimeout(() => region.classList.remove('show'), 7000);
}

// ---------- Form errors ----------

function clearErrors(scope) {
  $$('.field-error', scope).forEach((el) => el.remove());
  $$('[aria-invalid="true"]', scope).forEach((el) => {
    el.removeAttribute('aria-invalid');
    el.removeAttribute('aria-describedby');
  });
  $$('.form-error', scope).forEach((el) => { el.textContent = ''; });
}

function showError(scope, error, onReload) {
  const box = $('.form-error', scope);
  let firstField = null;
  for (const [name, msg] of Object.entries(error.fields || {})) {
    const field = scope.querySelector(`[name="${CSS.escape(name)}"]`);
    if (!field) continue;
    const id = `err-${name}-${Math.random().toString(36).slice(2, 7)}`;
    const span = document.createElement('span');
    span.className = 'field-error';
    span.id = id;
    span.textContent = msg;
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', id);
    (field.closest('label') || field).append(span);
    firstField ||= field;
  }
  if (box) {
    box.textContent = error.message;
    if (['stale_revision', 'stale_preview', 'batch_not_staged'].includes(error.code) && onReload) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'button small';
      btn.textContent = 'Show the current version';
      btn.addEventListener('click', onReload);
      box.append(' ', btn);
    }
    box.scrollIntoView({ block: 'nearest' });
  }
  (firstField || box)?.focus?.({ preventScroll: false });
}

function formBody(form, submitter) {
  if (form.hasAttribute('data-multipart')) {
    const fd = new FormData(form);
    if (submitter?.name) fd.append(submitter.name, submitter.value);
    return fd;
  }
  const out = {};
  const fd = new FormData(form);
  if (submitter?.name) fd.append(submitter.name, submitter.value);
  for (const [k, v] of fd.entries()) {
    if (k in out) out[k] = [].concat(out[k], v);
    else out[k] = v;
  }
  return out;
}

// ---------- Dialog primitive ----------

const dialog = {
  el: null,
  host: null,
  stack: [],        // [{url, title, dirty, snap}]
  pushed: 0,        // history entries this dialog created
  trigger: null,

  init() {
    this.el = $('#app-dialog');
    this.host = $('[data-dialog-frame]');
    if (!this.el) return;
    this.el.addEventListener('cancel', (e) => { e.preventDefault(); this.requestClose(); });
    // Browsers may force-close on repeated Escape; keep history and state consistent.
    this.el.addEventListener('close', () => { if (this.stack.length) this.close(); });
    this.el.addEventListener('click', (e) => {
      if (e.target.closest('[data-dialog-close]')) { e.preventDefault(); this.requestClose(); }
      else if (e.target.closest('[data-dialog-back]')) { e.preventDefault(); this.back(); }
      else if (e.target === this.el) { this.requestClose(); }
    });
    this.el.addEventListener('input', (e) => {
      if (e.target.matches(CONTROLS) && this.stack.length) {
        this.top().dirty = true;
        e.target.dataset.touched = '1';
      }
    });
    window.addEventListener('popstate', (e) => this.sync(e.state?.dialog || null));
    const initial = new URLSearchParams(location.search).getAll('d').filter((u) => u.startsWith('/ui/'));
    if (initial.length) {
      this.stack = initial.map((url) => ({ url, title: '', dirty: false }));
      history.replaceState({ dialog: initial }, '', this.urlFor(initial));
      this.show();
      this.render({ restore: false });
    } else {
      history.replaceState({ dialog: null }, '', location.href);
    }
  },

  top() { return this.stack[this.stack.length - 1]; },

  urlFor(urls) {
    const u = new URL(location.href);
    u.searchParams.delete('d');
    for (const x of urls || []) u.searchParams.append('d', x);
    return u.pathname + (u.search ? u.search : '') + u.hash;
  },

  show() {
    if (!this.el.open) this.el.showModal();
  },

  open(url, trigger) {
    this.trigger = trigger || document.activeElement;
    this.stack = [{ url, title: '', dirty: false }];
    this.pushed = 1;
    history.pushState({ dialog: [url] }, '', this.urlFor([url]));
    this.show();
    this.render({ restore: false });
  },

  push(url) {
    this.top().snap = this.snapshot();
    this.stack.push({ url, title: '', dirty: false });
    this.pushed += 1;
    const urls = this.stack.map((f) => f.url);
    history.pushState({ dialog: urls }, '', this.urlFor(urls));
    this.render({ restore: false });
  },

  back() {
    if (this.stack.length <= 1) { this.requestClose(); return; }
    if (this.pushed > 0) { history.back(); return; }
    this.stack.pop();
    const urls = this.stack.map((f) => f.url);
    history.replaceState({ dialog: urls }, '', this.urlFor(urls));
    this.render({ restore: true });
  },

  sync(urls) {
    if (!urls) { this.closeLocal(); return; }
    if (!this.el.open) { this.show(); }
    if (urls.length < this.stack.length) {
      this.pushed = Math.max(0, this.pushed - (this.stack.length - urls.length));
      this.stack = this.stack.slice(0, urls.length);
      this.render({ restore: true });
    } else if (urls.length > this.stack.length || urls.join() !== this.stack.map((f) => f.url).join()) {
      this.pushed += Math.max(0, urls.length - this.stack.length);
      const known = this.stack;
      this.stack = urls.map((url, i) => known[i]?.url === url ? known[i] : { url, title: '', dirty: false });
      this.render({ restore: false });
    }
  },

  anyDirty() { return this.stack.some((f) => f.dirty); },

  requestClose() {
    if (!this.anyDirty()) { this.close(); return; }
    if ($('.discard-bar', this.host)) return;
    const bar = $('#discard-template').content.firstElementChild.cloneNode(true);
    const foot = $('.modal-foot', this.host) || $('.modal-body', this.host);
    foot.prepend(bar);
    $('[data-keep]', bar).addEventListener('click', () => bar.remove());
    $('[data-discard]', bar).addEventListener('click', () => this.close());
    $('[data-keep]', bar).focus();
  },

  close() {
    this.stack.forEach((f) => { f.dirty = false; });
    if (this.pushed > 0) {
      const n = this.pushed;
      this.pushed = 0;
      history.go(-n);
      this.closeLocal();
    } else {
      history.replaceState({ dialog: null }, '', this.urlFor([]));
      this.closeLocal();
    }
  },

  closeLocal() {
    this.stack = [];
    this.pushed = 0;
    if (this.el.open) this.el.close();
    this.host.innerHTML = '';
    let target = this.trigger && document.contains(this.trigger) ? this.trigger : null;
    if (!target && this.trigger?.getAttribute?.('href')) {
      target = document.querySelector(`a[href="${CSS.escape(this.trigger.getAttribute('href'))}"]`);
    }
    (target || $('#main'))?.focus?.();
  },

  snapshot() {
    const frame = $('[data-frame]', this.host);
    if (!frame) return null;
    const controls = $$(CONTROLS, frame);
    const values = [];
    controls.forEach((el, i) => {
      if (el.dataset.touched) values.push({ i, name: el.name, value: el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value });
    });
    const body = $('.modal-body', frame);
    const active = document.activeElement && frame.contains(document.activeElement) ? document.activeElement : null;
    return {
      values,
      details: $$('details', frame).map((d) => d.open),
      scroll: body ? body.scrollTop : 0,
      focus: active ? { index: $$('a, button, input, select, textarea, summary', frame).indexOf(active) } : null,
    };
  },

  restore(frame, snap) {
    if (!snap) return false;
    const controls = $$(CONTROLS, frame);
    for (const v of snap.values) {
      const el = controls[v.i];
      if (!el || el.name !== v.name) continue;
      if (el.type === 'checkbox' || el.type === 'radio') el.checked = v.value;
      else el.value = v.value;
      el.dataset.touched = '1';
    }
    $$('details', frame).forEach((d, i) => { if (snap.details[i] !== undefined) d.open = snap.details[i]; });
    const body = $('.modal-body', frame);
    if (body) body.scrollTop = snap.scroll;
    if (snap.focus && snap.focus.index >= 0) {
      const el = $$('a, button, input, select, textarea, summary', frame)[snap.focus.index];
      if (el) { el.focus({ preventScroll: true }); return true; }
    }
    return false;
  },

  async render({ restore }) {
    const entry = this.top();
    if (!entry) return;
    this.host.setAttribute('aria-busy', 'true');
    let html;
    try {
      html = await fetchHTML(entry.url);
    } catch {
      this.host.innerHTML = `<div class="frame" data-frame data-title="Unavailable"><header class="modal-head"><div class="frame-nav" data-frame-nav></div><div class="head-row"><h2 id="dialog-title" tabindex="-1">Not available</h2><button class="close" type="button" data-dialog-close aria-label="Close">×</button></div></header><div class="modal-body"><p>This could not be loaded. It may have been removed, or the app is not running.</p><button class="button" type="button" data-retry>Try again</button></div></div>`;
      $('[data-retry]', this.host).addEventListener('click', () => this.render({ restore }));
      this.decorate();
      $('#dialog-title', this.host)?.focus();
      this.host.removeAttribute('aria-busy');
      return;
    }
    if (this.top() !== entry) return; // navigated meanwhile
    this.host.innerHTML = html;
    this.host.removeAttribute('aria-busy');
    const frame = $('[data-frame]', this.host);
    entry.title = frame?.dataset.title || '';
    this.el.classList.toggle('wide', !!frame?.classList.contains('wide'));
    this.decorate();
    enhance(frame);
    const focused = restore ? this.restore(frame, entry.snap) : false;
    entry.dirty = restore ? !!entry.snap?.values?.length : false;
    if (!focused) {
      const auto = $('[autofocus]', frame);
      (auto || $('#dialog-title', frame))?.focus({ preventScroll: true });
    }
  },

  decorate() {
    const nav = $('[data-frame-nav]', this.host);
    if (!nav) return;
    nav.innerHTML = '';
    if (this.stack.length > 1) {
      const prev = this.stack[this.stack.length - 2];
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'back-nav';
      btn.setAttribute('data-dialog-back', '');
      btn.innerHTML = '<span aria-hidden="true">‹</span> ';
      btn.append(document.createTextNode(prev.title || 'Back'));
      btn.setAttribute('aria-label', `Back to ${prev.title || 'previous'}`);
      nav.append(btn);
    }
  },

  async refreshTop() {
    const entry = this.top();
    if (!entry) return;
    entry.snap = this.snapshot();
    if (entry.snap) entry.snap.values = [];
    await this.render({ restore: true });
  },
};

// ---------- Page refresh (domain state, never stale HTML) ----------

let refreshing = false;
let lastSignature = '';
let lastFocusRefresh = Date.now();
function refreshOnReturn() {
  if (Date.now() - lastFocusRefresh < 15000) return;
  lastFocusRefresh = Date.now();
  refreshPage();
}
async function refreshPage() {
  const main = $('#main');
  if (!main || refreshing) return;
  if ($$('form', main).some((f) => f.dataset.dirty)) return;
  refreshing = true;
  try {
    const url = dialog.urlFor([]);
    const html = await fetchHTML(url);
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const fresh = doc.querySelector('#main');
    const signature = fresh ? fresh.innerHTML + (doc.querySelector('.top-actions')?.innerHTML || '') : '';
    if (fresh && signature !== lastSignature) {
      lastSignature = signature;
      const y = window.scrollY;
      main.innerHTML = fresh.innerHTML;
      const actions = doc.querySelector('.top-actions');
      if (actions) $('.top-actions').innerHTML = actions.innerHTML;
      const title = doc.querySelector('.page-title');
      if (title) $('.page-title').innerHTML = title.innerHTML;
      enhance(main);
      window.scrollTo(0, y);
    }
  } catch { /* offline banner already shown */ } finally {
    refreshing = false;
  }
}

function scheduleMinuteRefresh() {
  const ms = 60000 - (Date.now() % 60000) + 250;
  setTimeout(() => {
    if (document.visibilityState === 'visible') refreshPage();
    scheduleMinuteRefresh();
  }, ms);
}

// ---------- API forms ----------

async function submitApiForm(form, submitter) {
  const inDialog = dialog.el?.contains(form);
  clearErrors(form);
  const key = form.dataset.key || (form.dataset.key = newKey());
  const buttons = $$('button[type=submit]', form).concat(form.id ? $$(`button[form="${form.id}"]`) : []);
  buttons.forEach((b) => { b.disabled = true; });
  form.setAttribute('aria-busy', 'true');
  const res = await callAPI(form.dataset.api, formBody(form, submitter), key, form.hasAttribute('data-multipart'));
  buttons.forEach((b) => { b.disabled = false; });
  form.removeAttribute('aria-busy');
  if (res.error) {
    if (!res.error.retryable) delete form.dataset.key;
    showError(form, res.error, inDialog ? () => dialog.refreshTop() : () => location.reload());
    return;
  }
  delete form.dataset.key;
  delete form.dataset.dirty;
  toast(res.warnings);
  const after = form.dataset.after || 'reload';
  if (after === 'navigate') {
    if (inDialog) dialog.stack.forEach((f) => { f.dirty = false; });
    location.href = res.data?.redirect || location.href;
    return;
  }
  if (!inDialog) { location.reload(); return; }
  dialog.top().dirty = false;
  if (after === 'close') { dialog.close(); refreshPage(); return; }
  if (after === 'back') { dialog.back(); refreshPage(); return; }
  await dialog.refreshTop();
  refreshPage();
}

// ---------- Campaign creation flow ----------

function campaignFlow(frame) {
  const form = $('[data-campaign-form]', frame);
  if (!form) return;
  let step = 1;
  let createKey = null;
  const labels = { 1: '1 of 3 · Purpose and outcomes', 2: '2 of 3 · Resources', 3: '3 of 3 · Review' };
  const field = (name) => form.elements.namedItem(name);
  const objectBlock = $('[data-object-block]', form);
  const objectSelect = $('[data-object-select]', form);
  const newObject = $('[data-new-object]', form);

  const currentType = () => $('input[name=type]:checked', form);

  function filterModes(metricSelect) {
    const modeSelect = metricSelect.closest('.row')?.querySelector('[data-mode-select]');
    const opt = metricSelect.selectedOptions[0];
    if (!modeSelect || !opt) return;
    const modes = (opt.dataset.modes || '').split('|').filter(Boolean);
    let first = null;
    for (const o of modeSelect.options) {
      o.hidden = modes.length > 0 && !modes.includes(o.value);
      o.disabled = o.hidden;
      if (!o.hidden && !first) first = o;
    }
    if (modeSelect.selectedOptions[0]?.hidden && first) modeSelect.value = first.value;
    const hint = $('[data-source-hint]', form);
    if (hint && metricSelect.name === 'metric_id') hint.hidden = opt.dataset.sourced !== '0';
  }

  function applyType() {
    const t = currentType();
    const kind = t?.dataset.objectKind || '';
    objectBlock.hidden = !kind;
    if (kind) {
      $('[data-object-legend]', form).textContent = `Which ${kind === 'event' ? 'event' : kind}?`;
      $('[data-anchor-label]', form).textContent = t.dataset.anchor || 'Key date';
      let firstVisible = null;
      for (const o of objectSelect.options) {
        const show = o.value === 'new' || o.dataset.kind === kind;
        o.hidden = !show;
        o.disabled = !show;
        if (show && !firstVisible) firstVisible = o;
      }
      if (objectSelect.selectedOptions[0]?.hidden) objectSelect.value = firstVisible.value;
      $$('[data-event-only]', form).forEach((el) => { el.hidden = kind !== 'event'; });
    }
    newObject.hidden = !kind || objectSelect.value !== 'new';
    const scopes = ['artist', kind].filter(Boolean);
    $$('[data-metric-select]', form).forEach((sel) => {
      const visible = [];
      for (const o of sel.options) {
        if (!o.dataset.scope) continue;
        const ok = scopes.includes(o.dataset.scope);
        o.hidden = !ok;
        o.disabled = !ok;
        if (ok) visible.push(o);
      }
      if (sel.hasAttribute('data-optional')) {
        if (sel.selectedOptions[0]?.hidden) sel.value = '';
      } else if (!sel.dataset.userSet || sel.selectedOptions[0]?.hidden) {
        const preferred = visible.find((o) => o.dataset.scope === kind && o.dataset.sourced === '1')
          || visible.find((o) => o.dataset.sourced === '1') || visible[0];
        if (preferred) sel.value = preferred.value;
      }
      filterModes(sel);
    });
  }

  function payload(status) {
    const t = currentType();
    const kind = t?.dataset.objectKind;
    const data = {
      type: t?.value, name: field('name').value.trim(), start_date: field('start_date').value, end_date: field('end_date').value,
      status: status || 'active',
      primary_outcome: { mode: 'new', metric_id: field('metric_id').value, outcome_mode: field('outcome_mode').value, target: field('target').value },
      supporting_outcomes: [],
      resources: {
        channels: $$('input[name=channels]:checked', form).map((c) => c.value),
        email_list_confirmed: field('email_list_confirmed').checked,
        audience: field('audience').value, assets_ready_date: field('assets_ready_date').value || null,
        budget: field('budget').value, constraints: field('constraints').value,
      },
    };
    if (kind) {
      data.object = objectSelect.value === 'new'
        ? { mode: 'new', label: field('object_label').value, key_date: field('object_key_date').value || null,
          date_confirmed: field('object_date_confirmed').checked, venue: field('venue').value, ticket_url: field('ticket_url').value }
        : { mode: 'existing', id: objectSelect.value };
    }
    if (field('supporting_metric_id').value) {
      data.supporting_outcomes.push({ mode: 'new', metric_id: field('supporting_metric_id').value, outcome_mode: field('supporting_mode').value, target: field('supporting_target').value });
    }
    return data;
  }

  function cards() {
    return $$('[data-activity-card]', form).map((card) => {
      const get = (f) => card.querySelector(`[data-field="${f}"]`);
      return {
        selected: get('selected').checked, title: get('title').value, date: get('date').value || null, time: get('time').value || null,
        channel: get('channel').value, format: get('format').value, purpose: get('purpose')?.value || '',
        origin: card.dataset.origin, template_key: card.dataset.templateKey || null, kind: card.dataset.kind,
        effort_minutes: card.dataset.effort, basis: card.dataset.basis, edited: !!card.dataset.edited,
      };
    });
  }

  function show(n) {
    step = n;
    $$('[data-step]', form).forEach((s) => { s.hidden = Number(s.dataset.step) !== n; });
    $('[data-step-label]', frame).textContent = labels[n];
    $('[data-step-back]', frame).hidden = n === 1;
    $('[data-step-next]', frame).hidden = n === 3;
    $$('[data-create]', frame).forEach((b) => { b.hidden = n !== 3; });
    $('.modal-body', frame).scrollTop = 0;
    $('#dialog-title', frame).focus({ preventScroll: true });
  }

  function localCheck() {
    const missing = {};
    if (!field('name').value.trim()) missing.name = 'Required';
    if (!field('start_date').value) missing.start_date = 'Required';
    if (!field('end_date').value) missing.end_date = 'Required';
    if (field('target').value === '') missing.target = 'Required';
    if (!objectBlock.hidden && objectSelect.value === 'new' && !field('object_label').value.trim()) missing.object_label = 'Required';
    return missing;
  }

  async function next() {
    clearErrors(form);
    if (step === 1) {
      const missing = localCheck();
      if (Object.keys(missing).length) { showError(form, { message: 'Complete the highlighted fields.', fields: missing }); return; }
      show(2);
      return;
    }
    if (step === 2) {
      const btn = $('[data-step-next]', frame);
      btn.disabled = true;
      btn.textContent = 'Preparing review…';
      const res = await callAPI('/api/campaigns/preview', { campaign: payload() }, newKey());
      btn.disabled = false;
      btn.textContent = 'Continue';
      if (res.error) {
        const stepOneFields = ['name', 'start_date', 'end_date', 'target', 'metric_id', 'outcome_mode', 'object_label', 'object', 'type', 'mode'];
        if (Object.keys(res.error.fields || {}).some((f) => stepOneFields.includes(f)) || ['scope_mismatch', 'invalid_mode', 'invalid_window', 'object_required', 'scope_needs_object'].includes(res.error.code)) show(1);
        showError(form, res.error);
        return;
      }
      $('[data-review-slot]', form).innerHTML = res.data.html;
      createKey = null;
      show(3);
    }
  }

  async function create(status) {
    clearErrors(form);
    createKey ||= newKey();
    const buttons = $$('[data-create]', frame);
    buttons.forEach((b) => { b.disabled = true; });
    const res = await callAPI('/api/campaigns', { campaign: { ...payload(status), activities: cards() } }, createKey);
    buttons.forEach((b) => { b.disabled = false; });
    if (res.error) {
      if (!res.error.retryable) createKey = null;
      showError(form, res.error);
      return;
    }
    dialog.stack.forEach((f) => { f.dirty = false; });
    toast(res.warnings);
    location.href = res.data.redirect;
  }

  form.addEventListener('change', (e) => {
    if (e.target.name === 'type' || e.target === objectSelect) applyType();
    if (e.target.matches('[data-metric-select]')) { e.target.dataset.userSet = '1'; filterModes(e.target); }
    if (e.target === objectSelect && objectSelect.value !== 'new') {
      const d = objectSelect.selectedOptions[0]?.dataset.keyDate;
      if (d && !field('end_date').value) field('end_date').value = d;
    }
  });
  form.addEventListener('input', (e) => {
    createKey = null;
    const card = e.target.closest('[data-activity-card]');
    if (card && card.dataset.origin === 'operational_template' && e.target.dataset.field !== 'selected') card.dataset.edited = '1';
  });
  form.addEventListener('click', (e) => {
    if (e.target.closest('[data-add-activity]')) {
      const tpl = $('[data-manual-activity]', form);
      const card = tpl.content.firstElementChild.cloneNode(true);
      $('[data-proposal-list]', form).append(card);
      card.querySelector('[data-field="title"]').focus();
    }
    const remove = e.target.closest('[data-remove-card]');
    if (remove) remove.closest('[data-activity-card]').remove();
  });
  form.addEventListener('submit', (e) => { e.preventDefault(); next(); });
  $('[data-step-next]', frame).addEventListener('click', next);
  $('[data-step-back]', frame).addEventListener('click', () => { clearErrors(form); show(step - 1); });
  $$('[data-create]', frame).forEach((b) => b.addEventListener('click', () => create(b.dataset.create)));
  applyType();
}

// ---------- Small enhancements ----------

function enhance(root) {
  if (!root) return;
  if (root.matches?.('[data-campaign-flow]')) campaignFlow(root);
  $$('[data-channel-select]', root).forEach((sel) => {
    const list = $('[data-format-list]', root);
    const fill = () => {
      if (!list) return;
      list.innerHTML = '';
      for (const f of (sel.selectedOptions[0]?.dataset.formats || '').split('|').filter(Boolean)) {
        const o = document.createElement('option');
        o.value = f;
        list.append(o);
      }
    };
    sel.addEventListener('change', fill);
    fill();
  });
  $$('[data-metric-select]', root).forEach((sel) => {
    if (root.matches?.('[data-campaign-flow]')) return;
    const modeSel = $('[data-mode-select]', root);
    const apply = () => {
      const modes = (sel.selectedOptions[0]?.dataset.modes || '').split('|').filter(Boolean);
      let first = null;
      for (const o of modeSel.options) {
        o.hidden = modes.length > 0 && !modes.includes(o.value);
        o.disabled = o.hidden;
        if (!o.hidden && !first) first = o;
      }
      if (modeSel.selectedOptions[0]?.hidden && first) modeSel.value = first.value;
    };
    sel.addEventListener('change', apply);
    apply();
  });
}

function rememberEvidenceTab() {
  const m = location.pathname.match(/^\/evidence\/(findings|data|review)$/);
  if (m) sessionStorage.setItem(`evidence:${m[1]}`, location.search);
  if (location.pathname === '/evidence') sessionStorage.setItem('evidence:findings', location.search);
}

// ---------- Wiring ----------

document.addEventListener('click', (e) => {
  const open = e.target.closest('a[data-dialog-open]');
  if (open && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
    e.preventDefault();
    dialog.open(open.getAttribute('href'), open);
    return;
  }
  const push = e.target.closest('a[data-dialog-push]');
  if (push && !e.metaKey && !e.ctrlKey) {
    e.preventDefault();
    dialog.push(push.getAttribute('href'));
    return;
  }
  const tab = e.target.closest('[data-evidence-tabs] a[data-tab]');
  if (tab && !e.metaKey && !e.ctrlKey) {
    const saved = sessionStorage.getItem(`evidence:${tab.dataset.tab}`);
    if (saved && !tab.getAttribute('aria-current')) {
      e.preventDefault();
      location.href = tab.getAttribute('href') + saved;
    }
    return;
  }
  const menu = e.target.closest('[data-menu]');
  if (menu) {
    const open = document.body.classList.toggle('menu-open');
    menu.setAttribute('aria-expanded', String(open));
  }
});

document.addEventListener('submit', (e) => {
  const form = e.target.closest('form[data-api]');
  if (!form) return;
  e.preventDefault();
  submitApiForm(form, e.submitter);
});

document.addEventListener('input', (e) => {
  const form = e.target.closest('form');
  if (!form) return;
  if (form.dataset.api) delete form.dataset.key;
  if (!dialog.el?.contains(form) && form.dataset.api) form.dataset.dirty = '1';
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && document.body.classList.contains('menu-open')) {
    document.body.classList.remove('menu-open');
    $('[data-menu]')?.setAttribute('aria-expanded', 'false');
  }
});

document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') refreshOnReturn(); });
window.addEventListener('focus', refreshOnReturn);

if ($('[data-calendar] table.month') && !new URLSearchParams(location.search).has('view') && matchMedia('(max-width: 760px)').matches) {
  const u = new URL(location.href);
  u.searchParams.set('view', 'list');
  location.replace(u);
}

lastSignature = ($('#main')?.innerHTML || '') + ($('.top-actions')?.innerHTML || '');
dialog.init();
enhance(document.body);
rememberEvidenceTab();
scheduleMinuteRefresh();
window.bandEvidence = { dialog, refreshPage };
