'use strict';

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const env = process.env.NODE_ENV || 'development';
require('dotenv').config({ path: path.join(__dirname, `.env.${env}`) });

const express = require('express');
const flaskApi = require('./services/api');
const app = express();
const PORT = Number(process.env.PORT) || 3000;
const SESSION_SECRET = process.env.SESSION_SECRET || '';
const AUTH_REQUIRED = env === 'production' || /^(true|yes|1)$/i.test(process.env.AUTH_REQUIRED || 'false');
const COOKIE_NAME = 'scc_session';
const SESSION_AGE_MS = 8 * 60 * 60 * 1000;

if (AUTH_REQUIRED && (SESSION_SECRET.length < 32 || SESSION_SECRET.startsWith('REPLACE_'))) {
  throw new Error('Set a SESSION_SECRET of at least 32 characters in frontend/.env.' + env);
}

app.disable('x-powered-by');
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.urlencoded({ extended: false, limit: '16kb' }));
app.use(express.json({ limit: '16kb' }));
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'same-origin');
  next();
});

// Your screenshot shows public/ at the project root. This supports either
// public/ beside frontend/ or public/ inside frontend/.
const publicDir = [
  path.join(__dirname, 'public'),
  path.join(__dirname, '..', 'public')
].find(dir => fs.existsSync(path.join(dir, 'css', 'styles.css')));
if (publicDir) app.use(express.static(publicDir));
else console.warn('WARNING: Cannot locate public/css/styles.css');

const guestUser = Object.freeze({ name: 'Guest', firstName: 'Guest', username: '', email: '', role: '' });
const fmt = {
  number: value => value == null || value === '' ? 'N/A' : Number(value).toLocaleString('en-US'),
  money: value => value == null || value === '' ? 'N/A' : Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' }),
  date: value => {
    if (!value) return 'N/A';
    const raw = String(value);
    // A YYYY-MM-DD date should not shift backward in US time zones.
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
      const [year, month, day] = raw.split('-').map(Number);
      return `${month}/${day}/${year}`;
    }
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? 'N/A' : d.toLocaleDateString('en-US');
  },
  signed: value => {
    const n = Number(value);
    return Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n.toLocaleString('en-US')}` : 'N/A';
  },
  tagClass: value => {
    const type = String(value || '').toLowerCase();
    if (type.includes('sale') || type.includes('sold')) return 'tag-blue';
    if (type.includes('return')) return 'tag-red';
    return 'tag-soft';
  }
};

function locals(user = guestUser, extra = {}) {
  return { env, user, authenticated: Boolean(user.id), api: { status: 'unknown' }, message: null, fmt, ...extra };
}

function getCookie(req, name) {
  const all = String(req.headers.cookie || '').split(';');
  const pair = all.map(s => s.trim()).find(v => v.startsWith(name + '='));
  if (!pair) return null;
  try { return decodeURIComponent(pair.substring(name.length + 1)); }
  catch (_) { return null; }
}

function sign(value) {
  return crypto.createHmac('sha256', SESSION_SECRET).update(value).digest('base64url');
}

function sessionId(req) {
  if (SESSION_SECRET.length < 32 || SESSION_SECRET.startsWith('REPLACE_')) return null;
  const cookie = getCookie(req, COOKIE_NAME);
  if (!cookie) return null;
  const parts = cookie.split('.');
  if (parts.length !== 2) return null;
  const [encoded, signature] = parts;
  const actual = Buffer.from(signature);
  const expected = Buffer.from(sign(encoded));
  if (actual.length !== expected.length || !crypto.timingSafeEqual(actual, expected)) return null;
  try {
    const payload = JSON.parse(Buffer.from(encoded, 'base64url').toString('utf8'));
    if (!payload || typeof payload.id !== 'string' || payload.id.length > 128) return null;
    if (!Number.isSafeInteger(payload.exp) || payload.exp < Date.now()) return null;
    return payload.id;
  } catch (_) {
    return null;
  }
}

function cookieOptions() {
  return { httpOnly: true, sameSite: 'lax', secure: env === 'production', path: '/' };
}

function writeSession(res, id) {
  const payload = Buffer.from(JSON.stringify({ id: String(id), exp: Date.now() + SESSION_AGE_MS })).toString('base64url');
  res.cookie(COOKIE_NAME, `${payload}.${sign(payload)}`, { ...cookieOptions(), maxAge: SESSION_AGE_MS });
}

function clearSession(res) {
  res.clearCookie(COOKIE_NAME, cookieOptions());
}

async function resolveUser(req) {
  const id = sessionId(req);
  if (!id) return null;
  try {
    const data = await flaskApi.get('/auth/me', { user_id: id });
    return data && data.user && data.user.id ? data.user : null;
  } catch (err) {
    // Invalid sessions fail closed. A DB outage will not impersonate a user.
    return null;
  }
}

async function pageUser(req, res) {
  const signedIn = await resolveUser(req);
  if (AUTH_REQUIRED && !signedIn) {
    clearSession(res);
    res.redirect('/login');
    return null;
  }
  return signedIn || guestUser;
}

function friendlyError(err) {
  if (err && err.status === 404)
    return 'The requested Flask endpoint does not exist yet. This frontend requires additional backend data endpoints; the supplied Flask api.py only exposes /health and /db/check.';
  if (err && err.body && err.body.error === 'schema_unmapped')
    return `${err.body.model || 'Page'} data is not mapped to a database table/view. Run the schema inspector (see README).`;
  if (err && err.body && err.body.error === 'database_unavailable')
    return 'Cannot connect to MySQL. Check the backend environment and network access.';
  if (err && err.status === 401)
    return 'Flask rejected the API key. Set the same API_KEY on frontend and backend.';
  if (err && err.body && err.body.error === 'configuration_error')
    return 'Backend schema configuration is invalid.';
  return 'Live data is currently unavailable. Check the Flask terminal for details.';
}

async function loadAndRender(req, res, view, endpoint, fallback, map = x => x) {
  const user = await pageUser(req, res);
  if (!user) return;
  let payload = fallback;
  let message = null;
  let dataAvailable = false;
  try {
    const result = await flaskApi.get(endpoint, req.query);
    payload = map(result);
    dataAvailable = true;
    if (result.truncated) message = 'The list reached its page limit; more database records may exist.';
  } catch (err) {
    console.error(`GET ${endpoint} failed:`, err.message);
    message = friendlyError(err);
  }
  res.render(`pages/${view}`, locals(user, { ...payload, dataAvailable, message }));
}

app.get('/', async (req, res) => {
  const user = await pageUser(req, res);
  if (!user) return;
  const api = await flaskApi.health();
  let data = {};
  let message = null;
  try {
    data = await flaskApi.get('/dashboard', { days: 30 });
    const critical = (data.warnings || []).filter(x => !x.includes('inventory history'));
    if (critical.length) message = critical.join(' ');
  } catch (err) {
    console.error('Dashboard API failed:', err.message);
    message = friendlyError(err);
  }
  res.render('pages/index', locals(user, { api, data, message }));
});

app.get('/inventory', (req, res) => loadAndRender(req, res, 'inventory', '/inventory', {
  items: [], threshold: 5
}));

app.get('/orders', (req, res) => loadAndRender(req, res, 'orders', '/orders', {
  rows: [], types: [], selected: '', limit: 100
}));

app.get('/employees', (req, res) => loadAndRender(req, res, 'employees', '/employees', {
  employees: []
}));

app.get('/settings', async (req, res) => {
  const user = await pageUser(req, res);
  if (!user) return;
  res.render('pages/settings', locals(user, {
    message: user.id ? null : 'Sign in to view your real account details.'
  }));
});

app.get('/login', async (req, res) => {
  const user = await resolveUser(req);
  if (user) return res.redirect('/');
  res.render('pages/login', locals(guestUser, { error: null, username: '' }));
});

// Basic single-process rate limit. Use a shared rate-limit store in production.
const loginAttempts = new Map();
app.post('/login', async (req, res) => {
  const username = String(req.body.username || '').trim().slice(0, 100);
  const password = req.body.password;
  const key = `${req.ip}:${username}`;
  const now = Date.now();
  const attempts = (loginAttempts.get(key) || []).filter(t => t > now - 15 * 60 * 1000);
  if (attempts.length >= 10) {
    return res.status(429).render('pages/login', locals(guestUser, {
      error: 'Too many attempts. Please try again later.', username
    }));
  }
  attempts.push(now);
  loginAttempts.set(key, attempts);
  if (loginAttempts.size > 2000) {
    for (const [k, v] of loginAttempts) {
      if (!v.some(t => t > now - 15 * 60 * 1000)) loginAttempts.delete(k);
    }
  }
  if (SESSION_SECRET.length < 32 || SESSION_SECRET.startsWith('REPLACE_')) {
    return res.status(503).render('pages/login', locals(guestUser, {
      error: 'Login is not configured. Add SESSION_SECRET to your frontend environment.', username
    }));
  }
  try {
    const reply = await flaskApi.post('/auth/login', { username, password });
    if (!reply || !reply.user || !reply.user.id) throw new Error('Authentication did not return an account');
    loginAttempts.delete(key);
    writeSession(res, reply.user.id);
    return res.redirect('/');
  } catch (err) {
    const msg = err.status === 401 ? 'Invalid username or password.' : friendlyError(err);
    return res.status(err.status === 401 ? 401 : 503).render('pages/login', locals(guestUser, {
      error: msg, username
    }));
  }
});

app.post('/logout', (req, res) => {
  clearSession(res);
  res.redirect('/login');
});

app.get('/api/health', async (req, res) => {
  const status = await flaskApi.health();
  res.status(status.status === 'ok' ? 200 : 503).json(status);
});

app.get('/api/db/check', async (req, res) => {
  try {
    const result = await flaskApi.get('/db/check');
    res.status(result.connected ? 200 : 503).json({ connected: Boolean(result.connected) });
  } catch (err) {
    res.status(503).json({ connected: false, error: 'Database check unavailable' });
  }
});

// Developer-only diagnostic: returns table/view mappings, never database rows.
if (env !== 'production') {
  app.get('/api/integration/status', async (req, res) => {
    try {
      const result = await flaskApi.get('/schema/status');
      res.json(result);
    } catch (err) {
      res.status(503).json({ error: friendlyError(err) });
    }
  });
}

app.use((req, res) => res.status(404).render('pages/error', locals(guestUser, {
  title: 'Page not found', detail: 'The requested page does not exist.'
})));

app.use((err, req, res, next) => {
  console.error(err);
  if (res.headersSent) return next(err);
  res.status(500).render('pages/error', locals(guestUser, {
    title: 'Server error', detail: 'An unexpected error occurred while loading this page.'
  }));
});

app.listen(PORT, () => {
  console.log(`Frontend (${env}) http://localhost:${PORT}`);
  console.log(`Static files: ${publicDir || 'NOT FOUND'}`);
  console.log(`Flask API: ${process.env.FLASK_API_URL || 'http://localhost:5000'}`);
  if (!AUTH_REQUIRED) console.warn('Development only: AUTH_REQUIRED is false. Enable it before deployment.');
});
