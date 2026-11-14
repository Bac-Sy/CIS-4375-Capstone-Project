'use strict';

// Single Express server combining both supplied server.js files.
// Run this file from the project root with npm run dev (or node frontend/server.js).
// Requires Node.js 18+ and: npm install express ejs dotenv express-session

const crypto = require('crypto');
const { AsyncLocalStorage } = require('async_hooks');
const { buildDonut, buildFlow } = require('./lib/charts');
const fs = require('fs');
const path = require('path');
const express = require('express');
const session = require('express-session');
const dotenv = require('dotenv');

const env = process.env.NODE_ENV || 'development';
const envName = `.env.${env}`;
const envPath = [
  path.join(__dirname, '..', envName),
  path.join(__dirname, envName)
].find(fs.existsSync);
if (envPath) dotenv.config({ path: envPath });

const PORT = Number(process.env.PORT) || 8080;
const API_URL = String(
  process.env.FLASK_API_URL || process.env.API_URL || 'http://127.0.0.1:5000'
).replace(/\/+$/, '');
const AUTH_REQUIRED = !/^(0|false|no)$/i.test(process.env.AUTH_REQUIRED || 'true');
const providedSecret = process.env.SESSION_SECRET || '';
if (providedSecret.length < 32 || providedSecret.startsWith('REPLACE_')) {
  throw new Error('SESSION_SECRET missing or too short. Copy the root .env.development.example to .env.development at the project root, then generate a random SESSION_SECRET.');
}
const SESSION_SECRET = providedSecret;

const app = express();
app.disable('x-powered-by');
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
if (env === 'production') app.set('trust proxy', 1);
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'same-origin');
  next();
});

// The merged project keeps assets in root/public/ alongside frontend/.
const publicDir = [path.join(__dirname, '..', 'public'), path.join(__dirname, 'public')]
  .find(dir => fs.existsSync(path.join(dir, 'css', 'styles.css')));
if (publicDir) app.use(express.static(publicDir));
else console.warn('WARNING: public/css/styles.css was not found in either expected location.');

app.use(express.json({ limit: '32kb' }));
app.use(express.urlencoded({ extended: false, limit: '32kb' }));
app.use(session({
  name: 'scc.sid',
  secret: SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', secure: env === 'production', maxAge: 8 * 60 * 60 * 1000 }
}));

const requestContext = new AsyncLocalStorage();
app.use((req, res, next) => requestContext.run(req, next));

const guestUser = Object.freeze({ id: null, name: 'Guest', firstName: 'Guest', lastName: '', username: '', email: '', role: '' });
const fmt = {
  number: value => value == null || value === '' || !Number.isFinite(Number(value))
    ? 'N/A' : Number(value).toLocaleString('en-US'),
  money: value => value == null || value === '' || !Number.isFinite(Number(value))
    ? 'N/A' : Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' }),
  date(value) {
    if (!value) return 'N/A';
    if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
      const [year, month, day] = String(value).split('-').map(Number);
      return `${month}/${day}/${year}`;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'N/A' : date.toLocaleDateString('en-US');
  },
  signed(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `${n > 0 ? '+' : ''}${n.toLocaleString('en-US')}` : 'N/A';
  },
  tagClass(value) {
    const type = String(value || '').toLowerCase();
    if (type.includes('sale') || type.includes('sold')) return 'tag-blue';
    if (type.includes('return')) return 'tag-red';
    return 'tag-soft';
  }
};

function normalizeUser(raw = {}) {
  const src = raw.user && typeof raw.user === 'object' ? raw.user : raw;
  const id = src.id ?? src.Employee_ID ?? src.employee_id ?? src.EmployeeID ?? null;
  if (id === null || id === '') return null;
  const firstName = String(src.firstName ?? src.first_name ?? src.First_Name ?? '').trim();
  const lastName = String(src.lastName ?? src.last_name ?? src.Last_Name ?? '').trim();
  return {
    id: String(id),
    name: String(src.name || `${firstName} ${lastName}`.trim() || src.Username || src.username || 'Employee'),
    firstName: firstName || String(src.name || src.Username || src.username || 'Employee').split(' ')[0],
    lastName,
    username: String(src.username ?? src.Username ?? ''),
    email: String(src.email ?? src.Email ?? ''),
    role: String(src.role ?? src.Role ?? '')
  };
}

// Old templates expect FirstName/Role, newer templates expect user/fmt/api.
// Accounts authenticated through the modern API are revalidated on each request.
// The employee info is saved in the session at login and trusted until the session expires
// (8 hours, the same as the API token), so pages don't re-check the login with Flask.
// Flask still checks the token on every API call, so nobody can use the API without logging in.
app.use(async (req, res, next) => {
  if (req.session.user?.id && !req.session.apiToken) {
    // A session without a token can't call the API, so treat it as logged out.
    delete req.session.user;
    delete req.session.authMode;
  }
  const user = req.session.user || guestUser;
  res.locals.user = user;
  res.locals.authenticated = Boolean(user.id);
  res.locals.FirstName = user.id ? user.firstName : null;
  res.locals.Role = user.id ? user.role : null;
  res.locals.env = env;
  res.locals.fmt = fmt;
  res.locals.api = { status: 'unknown' };
  res.locals.message = req.session.flash || null;
  res.locals.ErrorMessage = null;
  if (req.session.flash) delete req.session.flash;
  next();
});

// CSRF tokens protect every browser POST (login, logout, stock, edit, delete).
app.use((req, res, next) => {
  if (!req.session.csrfToken) req.session.csrfToken = crypto.randomBytes(32).toString('hex');
  res.locals.csrfToken = req.session.csrfToken;
  if (req.method !== 'POST') return next();
  const provided = Buffer.from(String(req.body?._csrf || ''));
  const expected = Buffer.from(req.session.csrfToken);
  if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) {
    return res.status(403).render('pages/error', {
      ...res.locals, title: 'Request rejected',
      detail: 'This form has expired or the security token is missing. Refresh the page and try again.'
    });
  }
  next();
});

// One consistent Flask client for legacy /api/... and newer /dashboard, /auth/... routes.
// This replaces the need for axios and supports GET, POST, PUT and DELETE.
class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}
async function apiRequest(method, endpoint, { body, query, timeoutMs = 10000 } = {}) {
  const url = new URL(API_URL + endpoint);
  for (const [key, value] of Object.entries(query || {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  }
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(process.env.API_KEY ? { 'X-API-Key': process.env.API_KEY } : {}),
        ...(requestContext.getStore()?.session?.apiToken
            ? { Authorization: `Bearer ${requestContext.getStore().session.apiToken}` } : {})
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs)
    });
  } catch (err) {
    throw new ApiError('Cannot reach the Flask API.', 503, null);
  }
  const raw = await response.text();
  let data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch (_) { /* Unexpected non-JSON response. */ }
  if (!response.ok) {
    // Flask rejected the login token (expired or the account was deleted): log out of the session too,
    // so the next page goes to the login screen instead of showing errors.
    const session = requestContext.getStore()?.session;
    if (response.status === 401 && session?.apiToken && !/^\/(auth\/)?login$/.test(endpoint)) {
      delete session.user;
      delete session.apiToken;
      delete session.authMode;
    }
    throw new ApiError(
      data?.message || data?.error || `Flask returned HTTP ${response.status}`,
      response.status, data
    );
  }
  return data;
}
const apiGet = (endpoint, query) => apiRequest('GET', endpoint, { query });
const apiPost = (endpoint, body) => apiRequest('POST', endpoint, { body });
const apiPut = (endpoint, body) => apiRequest('PUT', endpoint, { body });
const apiDelete = endpoint => apiRequest('DELETE', endpoint);
async function health() {
  try { return (await apiRequest('GET', '/health', { timeoutMs: 3000 })) || { status: 'unknown' }; }
  catch (_) { return { status: 'unreachable' }; }
}
function apiError(err, fallback = 'The request could not be completed.') {
  if (err?.status === 404) return `${fallback} Flask does not provide this endpoint yet.`;
  if (err?.status === 503) return `${fallback} Flask or MySQL may be unavailable.`;
  return err?.body?.message || err?.body?.error || fallback;
}
function page(req, res, view, values = {}, status = 200) {
  return res.status(status).render(`pages/${view}`, {
    ...res.locals,
    ...values
  });
}
function localToday() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function errorPage(req, res, status, title, detail) {
  return page(req, res, 'error', { title, detail }, status);
}
function flashAndRedirect(req, res, message, destination = '/') {
  req.session.flash = String(message || 'Action completed.');
  return res.redirect(303, destination);
}
function accessDenied(req, res, status, reason) {
  return page(req, res, 'accessdenial', {
    title: 'Access denied', detail: reason, message: reason
  }, status);
}
function signedIn(req, res, next) {
  if (req.session.user?.id) return next();
  if (req.method === 'GET') return res.redirect('/login');
  return accessDenied(req, res, 401, 'Please log in before changing records.');
}
function managerOnly(req, res, next) {
  if (!req.session.user?.id) return signedIn(req, res, next);
  if (String(req.session.user.role).toLowerCase() === 'manager') return next();
  return accessDenied(req, res, 403, 'Manager permissions are required for this action.');
}
function pageAccess(req, res, next) {
  if (AUTH_REQUIRED) return signedIn(req, res, next);
  return next();
}

// DASHBOARD: the legacy API only provided /health; modern APIs can also provide /dashboard.
app.get('/', pageAccess, async (req, res) => {
  const api = await health();
  let data = {};
  let message = res.locals.message;
  try {
    data = await apiGet('/dashboard', { days: 30 }) || {};
    if (Array.isArray(data.warnings) && data.warnings.length)
      message = [message, ...data.warnings].filter(Boolean).join(' ');
  } catch (err) {
    message = [message, apiError(err, 'Live dashboard metrics are unavailable.')].filter(Boolean).join(' ');
  }
  // Recent orders card: Sales by default, with Restocks and Adjustments as tabs (?recent=Restock).
  const recentType = ['Sale', 'Restock', 'Adjustment'].includes(req.query.recent) ? req.query.recent : 'Sale';
  return page(req, res, 'index', {
    api, data,
    donut: buildDonut(data.sales?.by_category || []),
    flow: buildFlow(data.stock_weeks),
    recentType,
    message
  });
});

// LOGIN: accepts both POST /login (new EJS) and POST /process/login (legacy EJS).
app.get('/login', (req, res) => {
  if (req.session.user?.id) return res.redirect('/');
  return page(req, res, 'login', { error: null, ErrorMessage: null, username: '', Username: '' });
});
const loginAttempts = new Map();
async function login(req, res) {
  const username = String(req.body.username ?? req.body.Username ?? '').trim().slice(0, 100);
  const password = String(req.body.password ?? req.body.Password ?? '');
  const key = `${req.ip}:${username}`;
  const now = Date.now();
  const attempts = (loginAttempts.get(key) || []).filter(t => t > now - 15 * 60 * 1000);
  if (attempts.length >= 10) {
    const msg = 'Too many login attempts. Try again in 15 minutes.';
    return page(req, res, 'login', { error: msg, ErrorMessage: msg, username, Username: username }, 429);
  }
  attempts.push(now);
  loginAttempts.set(key, attempts);
  if (loginAttempts.size > 2000) {
    for (const [k, v] of loginAttempts) {
      if (!v.some(t => t > now - 15 * 60 * 1000)) loginAttempts.delete(k);
    }
  }
  if (!username || !password) {
    const msg = 'Enter your username and password.';
    return page(req, res, 'login', { error: msg, ErrorMessage: msg, username, Username: username }, 400);
  }
  const payloadModern = { username, password };
  const payloadLegacy = { Username: username, Password: password };
  const isLegacyForm = req.path === '/process/login';
  const candidates = isLegacyForm
    ? [['/login', payloadLegacy], ['/auth/login', payloadModern]]
    : [['/auth/login', payloadModern], ['/login', payloadLegacy]];
  try {
    let reply;
    let successfulEndpoint = null;
    for (const [endpoint, body] of candidates) {
      try {
        // Login gets 30 seconds instead of the usual 10: connecting to the AWS database can be slow at times.
        reply = await apiRequest('POST', endpoint, { body, timeoutMs: 30000 });
        successfulEndpoint = endpoint;
        break;
      } catch (err) {
        // Only use the alternate auth endpoint when the first is not implemented.
        if (err.status !== 404 || endpoint === candidates[candidates.length - 1][0]) throw err;
      }
    }
    loginAttempts.delete(key);
    const user = normalizeUser(reply || {});
    if (!user) throw new ApiError('Flask did not return a valid employee identifier.', 502, null);
    if (!reply.token) throw new ApiError('Flask must return a signed authentication token. Apply the backend portion of this patch.', 502, null);
    // Regenerate session on login to prevent session fixation.
    await new Promise((resolve, reject) => req.session.regenerate(err => err ? reject(err) : resolve()));
    req.session.user = user;
    req.session.apiToken = reply.token;
    req.session.authMode = successfulEndpoint === '/auth/login' ? 'modern' : 'legacy';
    req.session.EmployeeID = user.id;
    req.session.FirstName = user.firstName;
    req.session.LastName = user.lastName;
    req.session.Username = user.username;
    req.session.Email = user.email;
    req.session.Role = user.role;
    req.session.flash = `Welcome, ${user.firstName}!`;
    await new Promise((resolve, reject) => req.session.save(err => err ? reject(err) : resolve()));
    return res.redirect(303, '/');
  } catch (err) {
    const msg = err.status === 401 || err.status === 404
      ? 'Incorrect username or password.' : apiError(err, 'Unable to log in.');
    return page(req, res, 'login', { error: msg, ErrorMessage: msg, username, Username: username }, err.status === 401 ? 401 : 503);
  }
}
app.post('/login', login);
app.post('/process/login', login);

// Support the current POST logout form and the older GET /logout link.
function logout(req, res, next) {
  req.session.destroy(err => {
    if (err) return next(err);
    res.clearCookie('scc.sid', { path: '/', httpOnly: true, sameSite: 'lax', secure: env === 'production' });
    res.redirect(303, '/login');
  });
}
app.post('/logout', logout);
app.get('/logout', (req, res) => res.redirect(303, req.session.user?.id ? '/settings' : '/login')); // GET must not log out.

// INVENTORY: prefer newer /inventory response; if missing, join legacy six endpoints.
const arrayData = value => Array.isArray(value) ? value : [];
function normalizeInventoryItem(row) {
  return {
    product: row.product ?? row.Product ?? row.Name ?? 'Unknown product',
    category: row.category ?? row.Category ?? '',
    size: row.size ?? row.Size ?? '',
    color: row.color ?? row.Color ?? '',
    location: row.location ?? row.Location ?? '',
    quantity: Number(row.quantity ?? row.Quantity ?? 0),
    price: row.price ?? row.Price ?? null,
    supplier: row.supplier ?? row.Supplier ?? '',
    available: row.available ?? row.Availability ?? true,
    variant_id: row.variant_id ?? row.Variant_ID ?? null
  };
}
async function legacyInventory() {
  const [inventories, variants, products, sizes, colors, locations] = await Promise.all([
    apiGet('/api/inventory'),
    apiGet('/api/product_variants'),
    apiGet('/api/products'),
    apiGet('/show/all/sizes'),
    apiGet('/show/all/colors'),
    apiGet('/api/locations')
  ]);
  const productsById = new Map(arrayData(products).map(p => [String(p.Product_ID), p]));
  const variantsById = new Map(arrayData(variants).map(v => [String(v.Variant_ID), v]));
  const sizesById = new Map(arrayData(sizes).map(s => [String(s.Size_ID), s]));
  const colorsById = new Map(arrayData(colors).map(c => [String(c.Color_ID), c]));
  const locationsById = new Map(arrayData(locations).map(l => [String(l.Location_ID), l]));
  const rows = arrayData(inventories).map(record => {
    const variant = variantsById.get(String(record.Variant_ID)) || {};
    const product = productsById.get(String(variant.Product_ID)) || {};
    const size = sizesById.get(String(variant.Size_ID)) || {};
    const color = colorsById.get(String(variant.Color_ID)) || {};
    const location = locationsById.get(String(variant.Location_ID)) || {};
    return {
      Variant_ID: record.Variant_ID,
      Product_ID: product.Product_ID ?? null,
      Product: product.Name || 'Unknown product',
      Size: size.Size || '',
      Color: color.Color || '',
      Location: location.Location_Name || '',
      Quantity: Number(record.Quantity) || 0,
      Price: variant.Price ?? null,
      Availability: product.Availability ?? true
    };
  });
  rows.sort((a, b) => String(a.Product).localeCompare(String(b.Product)));
  return { items: rows.map(normalizeInventoryItem), rows, threshold: 5 };
}
async function loadInventory() {
  try {
    const reply = await apiGet('/inventory');
    const rawItems = Array.isArray(reply) ? reply : (reply?.items ?? reply?.rows ?? []);
    const items = arrayData(rawItems).map(normalizeInventoryItem);
    const rows = arrayData(rawItems).map(x => ({
      Variant_ID: x.Variant_ID ?? x.variant_id,
      Product_ID: x.Product_ID ?? x.product_id ?? null,
      Product: x.Product ?? x.product,
      Size: x.Size ?? x.size,
      Color: x.Color ?? x.color,
      Location: x.Location ?? x.location,
      Category: x.Category ?? x.category ?? '',
      Available: x.Available ?? x.available ?? x.Availability ?? null,
      Quantity: x.Quantity ?? x.quantity,
      Price: x.Price ?? x.price
    }));
    const parsedThreshold = Number(reply?.low_stock_threshold ?? reply?.threshold ?? 5);
    return { items, rows, threshold: Number.isFinite(parsedThreshold) && parsedThreshold >= 0 ? parsedThreshold : 5 };
  } catch (err) {
    if (err.status !== 404) throw err;
    return legacyInventory();
  }
}
// Groups the inventory rows under their product, so each product shows its total and its sizes/colors.
// Products that have no variants yet are added from the product list, so they don't disappear.
function groupInventory(rows, products, categories, threshold) {
  const categoryNames = new Map(arrayData(categories).map(c => [String(c.Category_ID), c.Category]));
  const groups = new Map();
  for (const row of rows) {
    const key = String(row.Product_ID ?? row.Product);
    if (!groups.has(key)) {
      groups.set(key, { id: row.Product_ID, name: row.Product || 'Unknown product', category: row.Category || '',
        available: row.Available === undefined || row.Available === null ? true : Boolean(Number(row.Available)), variants: [] });
    }
    groups.get(key).variants.push(row);
  }
  for (const p of arrayData(products)) {
    const key = String(p.Product_ID);
    const available = p.Availability === undefined || p.Availability === null ? true : Boolean(Number(p.Availability));
    if (groups.has(key)) {
      const group = groups.get(key);
      if (!group.category) group.category = categoryNames.get(String(p.Category_ID)) || '';
      group.available = available;
    } else {
      groups.set(key, { id: p.Product_ID, name: p.Name, category: categoryNames.get(String(p.Category_ID)) || '', available, variants: [] });
    }
  }
  return [...groups.values()].map(g => ({
    ...g,
    total: g.variants.reduce((sum, v) => sum + (Number(v.Quantity) || 0), 0),
    low: g.variants.filter(v => Number(v.Quantity) <= threshold).length
  })).sort((a, b) => String(a.name).localeCompare(String(b.name)));
}
app.get('/inventory', pageAccess, async (req, res) => {
  try {
    const [result, products, categories] = await Promise.all([
      loadInventory(),
      apiGet('/api/products').catch(() => []),
      apiGet('/api/categories').catch(() => [])
    ]);
    const allGroups = groupInventory(result.rows, products, categories, result.threshold);
    // ?low=1 shows only the low stock variants (and the products they belong to).
    const lowOnly = req.query.low === '1';
    const lowCount = allGroups.reduce((n, g) => n + g.low, 0);
    const groups = lowOnly
      ? allGroups.filter(g => g.low).map(g => ({ ...g, variants: g.variants.filter(v => Number(v.Quantity) <= result.threshold) }))
      : allGroups;
    // ?adjust=<Variant_ID> opens that row in Adjust stock mode (chosen from its ⋯ menu).
    const adjusting = /^[1-9]\d*$/.test(String(req.query.adjust || '')) ? String(req.query.adjust) : null;
    return page(req, res, 'inventory', { ...result, groups, allGroups, lowOnly, lowCount, adjusting, dataAvailable: true });
  } catch (err) {
    console.error('Inventory load failed:', err.message);
    return page(req, res, 'inventory', {
      items: [], rows: [], groups: [], allGroups: [], lowOnly: false, lowCount: 0, adjusting: null, threshold: 5, dataAvailable: false,
      message: apiError(err, 'Inventory could not be loaded.')
    });
  }
});
app.post('/inventory/:variantId/adjust', signedIn, async (req, res) => {
  const back = `/inventory#v${encodeURIComponent(req.params.variantId)}`;
  const quantity = String(req.body.New_Quantity ?? '').trim();
  if (!/^\d+$/.test(quantity) || !Number.isSafeInteger(Number(quantity))) {
    return flashAndRedirect(req, res, 'Enter the new stock count as a whole number (0 or more).',
      `/inventory?adjust=${encodeURIComponent(req.params.variantId)}#v${encodeURIComponent(req.params.variantId)}`);
  }
  try {
    const result = await apiPut('/adjust/inventory', {
      Variant_ID: req.params.variantId,
      New_Quantity: Number(quantity),
      Employee_ID: req.session.user.id
    });
    return flashAndRedirect(req, res, result?.message || 'Inventory adjusted.', back);
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to adjust inventory.'), back);
  }
});

// ORDERS and EMPLOYEES: these require the newer Flask endpoints.
function normalizeOrder(r) {
  return {
    ...r,
    invoice_id: r.invoice_id ?? r.Invoice_ID ?? '',
    date: r.date ?? r.Date ?? '',
    transaction_type: r.transaction_type ?? r.Transaction_Type ?? '',
    product: r.product ?? r.Product ?? '',
    size: r.size ?? r.Size ?? '',
    color: r.color ?? r.Color ?? '',
    quantity_change: r.quantity_change ?? r.Quantity_Change ?? 0,
    employee: r.employee ?? r.Employee ?? ''
  };
}
app.get('/orders', pageAccess, async (req, res) => {
  const selected = typeof req.query.type === 'string' ? req.query.type : '';
  const fallback = { rows: [], types: [], selected, limit: 100, dataAvailable: false };
  try {
    const reply = await apiGet('/orders', { type: selected, limit: 100 });
    const rows = arrayData(Array.isArray(reply) ? reply : reply?.rows).map(normalizeOrder);
    return page(req, res, 'orders', {
      ...fallback, rows, types: arrayData(reply?.types),
      limit: Number(reply?.limit) || 100, dataAvailable: true
    });
  } catch (err) {
    return page(req, res, 'orders', {
      ...fallback, message: apiError(err, 'Order records are unavailable.')
    });
  }
});

// BEST SELLERS REPORT: ranks products and items by how many sold (Flask /report/best/sellers).
// ?days=7, 30 or 90 limits it to recent sales; no days (or 0) means all time.
const reportPeriods = [
  { days: 7, label: 'Last 7 days' },
  { days: 30, label: 'Last 30 days' },
  { days: 90, label: 'Last 90 days' },
  { days: 0, label: 'All time' }
];
app.get('/reports/best-sellers', pageAccess, async (req, res) => {
  const requested = Number(req.query.days ?? 30);
  const days = reportPeriods.some(p => p.days === requested) ? requested : 30;
  const view = req.query.view === 'item' ? 'item' : 'product';
  const fallback = { days, view, periods: reportPeriods, byProduct: [], byItem: [], totalUnits: 0, totalRevenue: 0, dataAvailable: false };
  try {
    // 30 seconds instead of the usual 10: the report runs two bigger queries and the AWS database can be slow.
    const reply = await apiRequest('GET', '/report/best/sellers', { query: { days }, timeoutMs: 30000 });
    return page(req, res, 'bestsellers', {
      ...fallback,
      byProduct: arrayData(reply?.by_product),
      byItem: arrayData(reply?.by_item),
      totalUnits: Number(reply?.total_units) || 0,
      totalRevenue: Number(reply?.total_revenue) || 0,
      dataAvailable: true
    });
  } catch (err) {
    return page(req, res, 'bestsellers', {
      ...fallback, message: apiError(err, 'The best sellers report is unavailable.')
    });
  }
});

app.get('/new/transaction', signedIn, async (req, res) => {
  try {
    const inventory = await loadInventory();
    const allTypes = await apiGet('/show/all/transaction/types');

    const types = arrayData(allTypes).filter(t =>
      ['Sale', 'Restock'].includes(t.Transaction_Type)
    );

    return page(req, res, 'newtransaction', {
      variants: inventory.items.filter(v =>
        Number.isSafeInteger(Number(v.variant_id)) &&
        Number(v.variant_id) > 0
      ),
      types
    });
  } catch (err) {
    return errorPage(
      req, res, 503, 'Transactions unavailable',
      apiError(err, 'Unable to load transaction form.')
    );
  }
});

app.post('/record/transaction', signedIn, async (req, res) => {
  try {
    const variantId = Number(req.body.Variant_ID);
    const typeId = Number(req.body.Transaction_Type_ID);
    const quantity = Number(req.body.Quantity);

    if (![variantId, typeId, quantity].every(
      n => Number.isSafeInteger(n) && n > 0
    )) {
      return flashAndRedirect(
        req, res, 'Enter valid transaction details.',
        '/new/transaction'
      );
    }

    const inventory = await loadInventory();
    const variantExists = inventory.items.some(v =>
      Number(v.variant_id) === variantId
    );

    if (!variantExists) {
      return flashAndRedirect(
        req, res, 'Choose a valid inventory item.',
        '/new/transaction'
      );
    }

    const allTypes = await apiGet('/show/all/transaction/types');
    const selected = arrayData(allTypes).find(t =>
      Number(t.Transaction_Type_ID) === typeId
    );

    if (!selected ||
        !['Sale', 'Restock'].includes(selected.Transaction_Type)) {
      return flashAndRedirect(
        req, res, 'Choose Sale or Restock.',
        '/new/transaction'
      );
    }

    const change =
      selected.Transaction_Type === 'Sale'
        ? -quantity
        : quantity;

    const result = await apiPost('/create/invoice', {
      Variant_ID: variantId,
      Transaction_Type_ID: typeId,
      Quantity_Change: change,
      Employee_ID: req.session.user.id
    });

    return flashAndRedirect(
      req, res,
      result?.message || 'Transaction recorded.',
      '/orders'
    );
  } catch (err) {
    return flashAndRedirect(
      req, res,
      apiError(err, 'Unable to record transaction.'),
      '/new/transaction'
    );
  }
});

// Find an existing order by invoice ID.
async function findOrder(id) {
  const reply = await apiGet('/orders', { limit: 200 });

  const rows = arrayData(
    Array.isArray(reply) ? reply : reply?.rows
  ).map(normalizeOrder);

  return rows.find(
    r => String(r.invoice_id) === String(id)
  ) || null;
}

// EDIT ORDER: the type, item (product / size / color), date and quantity can all be corrected.
// The API moves the stock when the quantity or item changes. "Recorded by" can't be changed.
async function loadOrderForm(id) {
  const [order, inventory, allTypes] = await Promise.all([
    findOrder(id),
    loadInventory(),
    apiGet('/show/all/transaction/types')
  ]);
  const types = arrayData(allTypes).filter(t => ['Sale', 'Restock', 'Adjustment'].includes(t.Transaction_Type));
  const variants = inventory.items
    .filter(v => Number.isSafeInteger(Number(v.variant_id)) && Number(v.variant_id) > 0)
    .sort((a, b) => String(a.product).localeCompare(String(b.product)) || String(a.size).localeCompare(String(b.size)) || String(a.color).localeCompare(String(b.color)));
  return { order, types, variants };
}

// GET: Display the Edit Order page.
app.get('/orders/:id/edit', signedIn, async (req, res) => {
  try {
    const { order, types, variants } = await loadOrderForm(req.params.id);

    if (!order) {
      return errorPage(
        req, res, 404,
        'Order not found',
        'The selected order could not be found.'
      );
    }

    return page(req, res, 'edit-order', { order, types, variants, today: localToday() });

  } catch (err) {
    return errorPage(
      req, res, 503,
      'Unable to load order',
      apiError(err, 'Order information is unavailable.')
    );
  }
});

// POST: Save changes to an Order.
app.post('/orders/:id/edit', signedIn, async (req, res) => {
  const back =
    `/orders/${encodeURIComponent(req.params.id)}/edit`;

  try {
    const rawQuantity = String(req.body.Quantity_Change ?? '').trim();
    const typeId = String(req.body.Transaction_Type_ID ?? '').trim();
    const variantId = String(req.body.Variant_ID ?? '').trim();
    const orderDate = String(req.body.Date ?? '').trim();

    // Quantity must be a nonzero whole number.
    if (!/^-?\d+$/.test(rawQuantity) ||
        !Number.isSafeInteger(Number(rawQuantity)) ||
        Number(rawQuantity) === 0) {
      return flashAndRedirect(req, res, 'Enter a valid nonzero whole-number quantity.', back);
    }
    if (!/^[1-9]\d*$/.test(typeId) || !/^[1-9]\d*$/.test(variantId)) {
      return flashAndRedirect(req, res, 'Choose a transaction type and an item.', back);
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(orderDate) || Number.isNaN(Date.parse(orderDate)) || orderDate > localToday()) {
      return flashAndRedirect(req, res, 'Enter a valid date that is not in the future.', back);
    }

    const quantity = Number(rawQuantity);
    const { order, types } = await loadOrderForm(req.params.id);

    if (!order) {
      return errorPage(req, res, 404, 'Order not found', 'The selected order could not be found.');
    }

    const selected = types.find(t => String(t.Transaction_Type_ID) === typeId);
    if (!selected) return flashAndRedirect(req, res, 'Choose Sale, Restock or Adjustment.', back);

    // Sales reduce inventory. Restocks increase it. Adjustments can go either way.
    const type = selected.Transaction_Type;
    if ((type === 'Sale' && quantity >= 0) || (type === 'Restock' && quantity <= 0)) {
      return flashAndRedirect(req, res, 'Sales must be negative and Restocks must be positive.', back);
    }

    const result = await apiPut('/update/invoice', {
      Invoice_ID: req.params.id,
      Transaction_Type_ID: Number(typeId),
      Variant_ID: Number(variantId),
      Date: orderDate,
      Quantity_Change: quantity
    });

    return flashAndRedirect(req, res, result?.message || 'Order updated successfully.', '/orders');

  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to update order.'), back);
  }
});

// POST: Delete an Order (Managers only).
app.post('/orders/:id/delete', managerOnly, async (req, res) => {
  try {
    const result = await apiRequest(
      'DELETE',
      '/delete/invoice',
      {
        body: {
          Invoice_ID: req.params.id
        }
      }
    );

    return flashAndRedirect(
      req, res,
      result?.message || 'Order deleted successfully.',
      '/orders'
    );

  } catch (err) {
    return flashAndRedirect(
      req, res,
      apiError(err, 'Unable to delete order.'),
      '/orders'
    );
  }
});


app.get('/employees', pageAccess, async (req, res) => {
  try {
    const reply = await apiGet('/employees');
    const employees = arrayData(Array.isArray(reply) ? reply : reply?.employees).map(e => ({
      ...e,
      first_name: e.first_name ?? e.First_Name ?? '',
      last_name: e.last_name ?? e.Last_Name ?? '',
      username: e.username ?? e.Username ?? '',
      email: e.email ?? e.Email ?? '',
      role: e.role ?? e.Role ?? '',
      id: e.id ?? e.employee_id ?? e.Employee_ID ?? null,
      active: e.active ?? e.is_active ?? e.Is_Active ?? null,
    }));
    return page(req, res, 'employees', { employees, dataAvailable: true });
  } catch (err) {
    return page(req, res, 'employees', {
      employees: [], dataAvailable: false,
      message: apiError(err, 'Employee records are unavailable.')
    });
  }
});
// SETTINGS: your account, log out, change your own password, and (managers) the low stock threshold.
app.get('/settings', pageAccess, async (req, res) => {
  if (!req.session.user?.id) {
    return page(req, res, 'settings', { message: 'Sign in to see your real account details.', storeSettings: null });
  }
  let storeSettings = null;
  if (String(req.session.user.role).toLowerCase() === 'manager') {
    try { storeSettings = await apiGet('/settings/store'); } catch (_) { storeSettings = null; }
  }
  return page(req, res, 'settings', { storeSettings });
});
app.post('/settings/password', signedIn, async (req, res) => {
  const current = String(req.body.Current_Password ?? '');
  const next = String(req.body.New_Password ?? '');
  const confirmation = String(req.body.Confirm_Password ?? '');
  if (!current || !next) return flashAndRedirect(req, res, 'Enter your current password and a new password.', '/settings');
  if (next.length < 8 || next.length > 128) return flashAndRedirect(req, res, 'The new password must be between 8 and 128 characters.', '/settings');
  if (next !== confirmation) return flashAndRedirect(req, res, 'The new passwords do not match.', '/settings');
  try {
    const result = await apiPost('/change/password', { Current_Password: current, New_Password: next });
    return flashAndRedirect(req, res, result?.message || 'Your password was changed.', '/settings');
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to change your password.'), '/settings');
  }
});
app.post('/settings/store', managerOnly, async (req, res) => {
  const value = String(req.body.Low_Stock_Threshold ?? '').trim();
  if (!/^\d+$/.test(value) || Number(value) > 1000) {
    return flashAndRedirect(req, res, 'Enter a low stock threshold between 0 and 1000.', '/settings');
  }
  try {
    const result = await apiPut('/settings/store', { low_stock_threshold: Number(value) });
    return flashAndRedirect(req, res, result?.message || 'Store settings saved.', '/settings');
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to save store settings.'), '/settings');
  }
});


async function findEmployee(id) {
  const response = await apiGet('/employees');

  const employees = arrayData(
    Array.isArray(response)
      ? response
      : response?.employees
  );

  const match = employees.find(e =>
    String(e.id ?? e.employee_id ?? e.Employee_ID) === String(id)
  );

  if (!match) return null;

  return {
    id: match.id ?? match.employee_id ?? match.Employee_ID,
    First_Name: match.First_Name ?? match.first_name ?? '',
    Last_Name: match.Last_Name ?? match.last_name ?? '',
    Username: match.Username ?? match.username ?? '',
    Email: match.Email ?? match.email ?? '',
    Role: match.Role ?? match.role ?? ''
  };
}

// 1. GET — DISPLAY EDIT EMPLOYEE PAGE

app.get('/employees/:id/edit', managerOnly, async (req, res) => {
  try {
    const employee = await findEmployee(req.params.id);

    if (!employee) {
      return errorPage(
        req, res, 404,
        'Employee not found',
        'The selected employee could not be found.'
      );
    }

    return page(req, res, 'editemployee', { employee });

  } catch (err) {
    return errorPage(
      req, res, 503,
      'Unable to load employee',
      apiError(err, 'Employee information is unavailable.')
    );
  }
});


// 2. POST — SAVE EDIT EMPLOYEE CHANGES

app.post('/employees/:id/edit', managerOnly, async (req, res) => {
  const back =
    `/employees/${encodeURIComponent(req.params.id)}/edit`;

  try {
    const employee = await findEmployee(req.params.id);

    if (!employee) {
      return errorPage(
        req, res, 404,
        'Employee not found',
        'The selected employee could not be found.'
      );
    }

    const firstName = String(req.body.First_Name ?? '').trim();
    const lastName = String(req.body.Last_Name ?? '').trim();
    const username = String(req.body.Username ?? '').trim();
    const email = String(req.body.Email ?? '').trim();
    const role = String(req.body.Role ?? '').trim();

    if (!firstName || !lastName || !username || !email ||
        !['Employee', 'Manager'].includes(role)) {
      return flashAndRedirect(
        req, res,
        'Please enter valid employee information.',
        back
      );
    }

    if (firstName.length > 50 ||
        lastName.length > 50 ||
        username.length > 50 ||
        email.length > 100 ||
        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return flashAndRedirect(
        req, res,
        'Check the employee fields and email address.',
        back
      );
    }

    // Avoid accidentally removing your own Manager access.
    if (
      String(employee.id) === String(req.session.user.id) &&
      role !== 'Manager'
    ) {
      return flashAndRedirect(
        req, res,
        'You cannot remove your own Manager role.',
        back
      );
    }

    const result = await apiPut('/update/employee', {
      Current_Email: employee.Email,
      First_Name: firstName,
      Last_Name: lastName,
      Username: username,
      Email: email,
      Role: role
    });

    return flashAndRedirect(
      req, res,
      result?.message || 'Employee updated successfully.',
      '/employees'
    );

  } catch (err) {
    return flashAndRedirect(
      req, res,
      err?.body?.message ||
        apiError(err, 'Unable to update employee.'),
      back
    );
  }
});


// 3. GET — DISPLAY RESET PASSWORD PAGE

app.get('/employees/:id/reset-password', managerOnly, async (req, res) => {
  try {
    const employee = await findEmployee(req.params.id);

    if (!employee) {
      return errorPage(
        req, res, 404,
        'Employee not found',
        'The selected employee could not be found.'
      );
    }

    return page(req, res, 'resetpassword', { employee });

  } catch (err) {
    return errorPage(
      req, res, 503,
      'Unable to load password reset page',
      apiError(err, 'Employee information is unavailable.')
    );
  }
});


// 4. POST — RESET EMPLOYEE PASSWORD

app.post('/employees/:id/reset-password', managerOnly, async (req, res) => {
  const back =
    `/employees/${encodeURIComponent(req.params.id)}/reset-password`;

  try {
    const password = String(req.body.Password ?? '');
    const confirmation = String(req.body.ConfirmPassword ?? '');

    if (password.length < 8 || password.length > 128) {
      return flashAndRedirect(
        req, res,
        'Password must contain between 8 and 128 characters.',
        back
      );
    }

    if (password !== confirmation) {
      return flashAndRedirect(
        req, res,
        'The passwords do not match.',
        back
      );
    }

    const employee = await findEmployee(req.params.id);

    if (!employee) {
      return errorPage(
        req, res, 404,
        'Employee not found',
        'The selected employee could not be found.'
      );
    }

    const result = await apiPut('/update/employee', {
      Current_Email: employee.Email,
      Password: password
    });

    return flashAndRedirect(
      req, res,
      result?.message || 'Employee password reset successfully.',
      '/employees'
    );

  } catch (err) {
    return flashAndRedirect(
      req, res,
      err?.body?.message ||
        apiError(err, 'Unable to reset employee password.'),
      back
    );
  }
});


// 5. POST — DELETE EMPLOYEE (MANAGER ONLY)

app.post('/employees/:id/delete', managerOnly, async (req, res) => {
  try {
    const employee = await findEmployee(req.params.id);

    if (!employee) {
      return errorPage(
        req, res, 404,
        'Employee not found',
        'The selected employee could not be found.'
      );
    }

    // Prevent a Manager from deleting their own account.
    if (String(employee.id) === String(req.session.user.id)) {
      return flashAndRedirect(
        req, res,
        'You cannot delete your own account.',
        '/employees'
      );
    }

    // The Flask API identifies an employee by Email.
    const result = await apiRequest(
      'DELETE',
      '/delete/employee',
      {
        body: {
          Email: employee.Email
        }
      }
    );

    return flashAndRedirect(
      req, res,
      result?.message || 'Employee deleted successfully.',
      '/employees'
    );

  } catch (err) {
    return flashAndRedirect(
      req, res,
      err?.body?.message ||
        apiError(err, 'Unable to delete employee.'),
      '/employees'
    );
  }
});


app.get('/manage', managerOnly, async (req, res) => {
  try {
    const [
      suppliers,
      categories,
      locations,
      products,
      variants,
      colors,
      sizes
    ] = await Promise.all([
      apiGet('/api/suppliers'),
      apiGet('/api/categories'),
      apiGet('/api/locations'),
      apiGet('/api/products'),
      apiGet('/api/product_variants'),
      apiGet('/show/all/colors'),
      apiGet('/show/all/sizes')
    ]);

    // Variants aren't listed here any more (they're managed on Inventory); they're only counted per product.
    const variantCounts = {};
    for (const v of arrayData(variants)) variantCounts[v.Product_ID] = (variantCounts[v.Product_ID] || 0) + 1;
    // ?rename=colors-3 opens that color or size as a rename box (chosen from its ⋯ menu).
    const renaming = /^(colors|sizes)-[1-9]\d*$/.test(String(req.query.rename || '')) ? String(req.query.rename) : null;

    return page(req, res, 'manage', {
      suppliers: arrayData(suppliers),
      categories: arrayData(categories),
      locations: arrayData(locations),
      products: arrayData(products),
      variantCounts,
      renaming,
      colors: arrayData(colors),
      sizes: arrayData(sizes)
    });

  } catch (err) {
    return errorPage(
      req, res, 503,
      'Catalog unavailable',
      apiError(err, 'Unable to load the catalog.')
    );
  }
});

const catalogAdds = {
  suppliers: {
    endpoint: '/api/suppliers',
    fields: ['Name', 'Email', 'Phone'],
    required: 'Name'
  },
  categories: {
    endpoint: '/api/categories',
    fields: ['Category'],
    required: 'Category'
  },
  locations: {
    endpoint: '/api/locations',
    fields: ['Location_Name'],
    required: 'Location_Name'
  },
  colors: {
    endpoint: '/create/color',
    fields: ['Color'],
    required: 'Color'
  },
  sizes: {
    endpoint: '/create/size',
    fields: ['Size'],
    required: 'Size'
  }
};

app.post('/manage/add/:kind', managerOnly, async (req, res) => {
  const config = catalogAdds[req.params.kind];

  if (!config) {
    return errorPage(
      req, res, 404,
      'Invalid catalog type',
      'This type of catalog record cannot be added.'
    );
  }

  const payload = {};

  for (const field of config.fields) {
    payload[field] = String(req.body[field] ?? '').trim();
  }

  if (!payload[config.required]) {
    return flashAndRedirect(
      req, res, 'Please fill in the required field.',
      '/manage'
    );
  }

  try {
    const result = await apiPost(config.endpoint, payload);

    return flashAndRedirect(
      req, res,
      result?.message || 'Catalogue record added.',
      '/manage'
    );
  } catch (err) {
    return flashAndRedirect(
      req, res,
      apiError(err, 'Unable to add catalogue record.'),
      '/manage'
    );
  }
});

// RENAME COLORS AND SIZES

const catalogRenames = {
  colors: {
    endpoint: '/update/color',
    idField: 'Color_ID',
    nameField: 'Color'
  },
  sizes: {
    endpoint: '/update/size',
    idField: 'Size_ID',
    nameField: 'Size'
  }
};

app.post('/manage/rename/:kind/:id', managerOnly, async (req, res) => {
  const config = catalogRenames[req.params.kind];

  if (!config) {
    return errorPage(
      req, res, 404,
      'Invalid catalogue type',
      'Only Colors and Sizes can be renamed here.'
    );
  }

  const id = Number(req.params.id);
  const name = String(req.body.Name ?? '').trim();

  if (!Number.isSafeInteger(id) || id <= 0 ||
      !name || name.length > 50) {
    return flashAndRedirect(
      req, res,
      'Enter a valid name.',
      '/manage'
    );
  }

  try {
    const payload = {
      [config.idField]: id,
      [config.nameField]: name
    };

    const result = await apiPut(config.endpoint, payload);

    return flashAndRedirect(
      req, res,
      result?.message || 'Catalogue record updated.',
      '/manage'
    );
  } catch (err) {
    return flashAndRedirect(
      req, res,
      apiError(err, 'Unable to rename catalogue record.'),
      '/manage'
    );
  }
});

// ADD VARIANTS: pick sizes and colors, then check each size/color combination the product comes in.
// Every checked row has its own starting stock, location, price and cost, unless "same for all" is ticked.
// Combinations the product already has are shown as "Already exists" and can't be added twice.
app.get('/products/:id/variants/new', managerOnly, async (req, res) => {
  try {
    const [products, sizes, colors, locations, variants] = await Promise.all([
      apiGet('/api/products'),
      apiGet('/show/all/sizes'),
      apiGet('/show/all/colors'),
      apiGet('/api/locations'),
      apiGet('/api/product_variants')
    ]);

    const product = arrayData(products).find(
      p => String(p.Product_ID) === String(req.params.id)
    );

    if (!product) {
      return errorPage(
        req, res, 404, 'Product not found',
        'The selected product does not exist.'
      );
    }

    const existing = arrayData(variants)
      .filter(v => String(v.Product_ID) === String(product.Product_ID))
      .map(v => `${v.Size_ID}-${v.Color_ID}`);

    return page(req, res, 'newvariant', {
      product,
      sizes: arrayData(sizes),
      colors: arrayData(colors),
      locations: arrayData(locations),
      existing
    });
  } catch (err) {
    return errorPage(
      req, res, 503, 'Variant form unavailable',
      apiError(err, 'Unable to load variant options.')
    );
  }
});


app.post('/products/:id/variants', managerOnly, async (req, res) => {
  const back = `/products/${encodeURIComponent(req.params.id)}/variants/new`;
  const validId = x => /^[1-9]\d*$/.test(String(x)) && Number.isSafeInteger(Number(x));
  const validMoney = x => /^(0|[1-9]\d{0,7})(\.\d{1,2})?$/.test(String(x).replace(/^\$/, '').trim());
  const money = x => Number(String(x).replace(/^\$/, '').trim());
  const productId = req.params.id;
  if (!validId(productId)) return flashAndRedirect(req, res, 'Choose a valid product.', '/manage');

  const combos = [].concat(req.body.combo || []).map(String).filter(c => /^[1-9]\d*-[1-9]\d*$/.test(c));
  if (!combos.length) {
    return flashAndRedirect(req, res, 'Check at least one size and color combination to add.', back);
  }

  const sameLocation = req.body.same_location === '1';
  const samePrice = req.body.same_price === '1';
  const planned = [];
  const problems = [];
  for (const combo of [...new Set(combos)]) {
    const [sizeId, colorId] = combo.split('-');
    const key = `${sizeId}_${colorId}`;
    const label = String(req.body[`label_${key}`] || combo).slice(0, 60);
    const stock = String(req.body[`stock_${key}`] ?? '0').trim() || '0';
    const location = String(sameLocation ? req.body.Location_ID : req.body[`location_${key}`] ?? '').trim();
    const price = String(samePrice ? req.body.Price : req.body[`price_${key}`] ?? '').trim();
    const cost = String(samePrice ? req.body.Cost : req.body[`cost_${key}`] ?? '').trim();
    if (!/^\d+$/.test(stock) || !Number.isSafeInteger(Number(stock))) problems.push(`${label}: starting stock must be a whole number`);
    else if (!validId(location)) problems.push(`${label}: choose a location`);
    else if (!validMoney(price) || !validMoney(cost)) problems.push(`${label}: enter a price and cost like 32.00`);
    else planned.push({ sizeId: Number(sizeId), colorId: Number(colorId), label, stock: Number(stock),
      location: Number(location), price: money(price), cost: money(cost) });
  }
  if (problems.length) {
    return flashAndRedirect(req, res, `Nothing was added. ${problems.slice(0, 3).join('; ')}${problems.length > 3 ? '; …' : ''}.`, back);
  }

  // Check again for combinations that already exist, in case someone added one in the meantime.
  let existing;
  try {
    existing = new Set(arrayData(await apiGet('/api/product_variants'))
      .filter(v => String(v.Product_ID) === String(productId))
      .map(v => `${v.Size_ID}-${v.Color_ID}`));
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to check the existing variants.'), back);
  }
  const duplicates = planned.filter(p => existing.has(`${p.sizeId}-${p.colorId}`));
  if (duplicates.length) {
    return flashAndRedirect(req, res,
      `Nothing was added: ${duplicates.map(d => d.label).join(', ')} already ${duplicates.length === 1 ? 'exists' : 'exist'}.`, back);
  }

  const added = [];
  for (const item of planned) {
    let variantId = null;
    try {
      const created = await apiPost('/api/product_variants', {
        Product_ID: Number(productId),
        Size_ID: item.sizeId,
        Color_ID: item.colorId,
        Location_ID: item.location,
        Price: item.price,
        Cost: item.cost
      });
      variantId = Number(created?.Variant_ID);
      if (!validId(variantId)) throw new ApiError('Variant creation returned no valid ID.', 502, null);
      await apiPost('/api/inventory', { Variant_ID: variantId, Quantity: 0 });
      if (item.stock > 0) {
        await apiPut('/adjust/inventory', { Variant_ID: variantId, New_Quantity: item.stock });
      }
      added.push(item.label);
    } catch (err) {
      const done = added.length ? `Added ${added.join(', ')}. ` : '';
      const failed = variantId
        ? `${item.label} was created, but its stock may not be set. Check it on Inventory.`
        : `${item.label} could not be added: ${apiError(err, 'the API rejected it.')}`;
      return flashAndRedirect(req, res, `${done}${failed} Anything after it was not added.`, variantId || added.length ? `/inventory#p${productId}` : back);
    }
  }

  return flashAndRedirect(req, res,
    `Added ${added.length} ${added.length === 1 ? 'variant' : 'variants'}: ${added.join(', ')}.`,
    `/inventory#p${productId}`);
});


// MANAGER: create a catalogue product using the existing Flask product API.
// A product needs a category and supplier; variants/stock are managed separately.
app.get('/new/product', managerOnly, async (req, res) => {
  try {
    const [categories, suppliers] = await Promise.all([
      apiGet('/api/categories'), apiGet('/api/suppliers')
    ]);
    return page(req, res, 'newproduct', {
      categories: arrayData(categories), suppliers: arrayData(suppliers)
    });
  } catch (err) {
    return errorPage(req, res, 503, 'Cannot add product',
      apiError(err, 'Categories and suppliers could not be loaded.'));
  }
});

app.post('/create/product', managerOnly, async (req, res) => {
  const name = String(req.body?.Name ?? '').trim();
  const categoryId = String(req.body?.Category_ID ?? '').trim();
  const supplierId = String(req.body?.Supplier_ID ?? '').trim();
  const availability = String(req.body?.Availability ?? '1').trim();
  const validId = value => /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value));

  if (!name || name.length > 100 || !validId(categoryId) || !validId(supplierId) ||
      !['0', '1'].includes(availability)) {
    return flashAndRedirect(req, res,
      'Enter a product name (up to 100 characters), category, supplier and availability.',
      '/new/product');
  }

  try {
    const created = await apiPost('/api/products', {
  Name: name,
  Category_ID: Number(categoryId),
  Supplier_ID: Number(supplierId),
  Availability: Number(availability)
});

const productId = Number(created.Product_ID);

if (!Number.isSafeInteger(productId) || productId <= 0) {
  return flashAndRedirect(
    req, res,
    'Product created, but no ID was returned. Check Manage Catalogue.',
    '/manage'
  );
}

return flashAndRedirect(
  req, res,
  `Product "${name}" created. Add its size/color variant next.`,
  `/products/${productId}/variants/new`
);
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to add product.'), '/new/product');
  }
});

// MANAGER: create employee account (legacy /add/employee API).
app.get('/new/employee', managerOnly, (req, res) => page(req, res, 'newemployee'));
app.post('/create/employee', managerOnly, async (req, res) => {
  try {
    const reply = await apiPost('/add/employee', {
      First_Name: req.body.First_Name,
      Last_Name: req.body.Last_Name,
      Role: req.body.Role,
      Username: req.body.Username,
      Email: req.body.Email,
      Password: req.body.Password
    });
    return flashAndRedirect(req, res, reply?.message || 'Employee created.', '/employees');
  } catch (err) {
  return page(req, res, 'newemployee', {
    message: apiError(err, 'Unable to create employee.'),
    form: {
      First_Name: req.body.First_Name,
      Last_Name: req.body.Last_Name,
      Role: req.body.Role,
      Username: req.body.Username,
      Email: req.body.Email
    }
  }, 400);
}
});

// Edit screens from screenshot: supplier, category, location, product, variant.
// Legacy edit URLs and Flask endpoints are retained. All mutations require login;
// deletion and creating employees are manager-only.
const editPages = [
  {
    kind: 'suppliers', view: 'edit-supplier', key: 'supplier', id: 'Supplier_ID',
    list: ['/api/suppliers'], put: '/api/suppliers', fields: ['Name', 'Email', 'Phone']
  },
  {
    kind: 'categories', view: 'edit-category', key: 'category', id: 'Category_ID',
    list: ['/api/categories'], put: '/api/categories', fields: ['Category']
  },
  {
    kind: 'locations', view: 'edit-location', key: 'location', id: 'Location_ID',
    list: ['/api/locations'], put: '/api/locations', fields: ['Location_Name']
  },
  {
    kind: 'products', view: 'edit-product', key: 'product', id: 'Product_ID',
    list: ['/api/products', '/api/categories', '/api/suppliers'],
    collections: ['products', 'categories', 'suppliers'],
    put: '/api/products', fields: ['Name', 'Category_ID', 'Availability', 'Supplier_ID']
  },
  {
    kind: 'variants', view: 'edit-variant', key: 'variant', id: 'Variant_ID',
    list: ['/api/product_variants', '/show/all/sizes', '/show/all/colors', '/api/products', '/api/locations'],
    collections: ['variants', 'sizes', 'colors', 'products', 'locations'],
    put: '/api/product_variants', fields: ['Size_ID', 'Color_ID', 'Product_ID', 'Location_ID', 'Price', 'Cost']
  }
];

for (const config of editPages) {
  const label = config.key.charAt(0).toUpperCase() + config.key.slice(1);
  app.get(`/${config.kind}/:id/edit`, signedIn, async (req, res) => {
    try {
      const results = await Promise.all(config.list.map(apiGetEndpoint => apiGet(apiGetEndpoint)));
      const values = {};
      if (config.collections) config.collections.forEach((name, index) => { values[name] = results[index]; });
      const selected = arrayData(results[0]).find(row => String(row[config.id]) === String(req.params.id));
      if (!selected) return errorPage(req, res, 404, 'Record not found', `${config.key} ID ${req.params.id} does not exist.`);
      values[config.key] = selected;
      return page(req, res, config.view, values);
    } catch (err) {
      return errorPage(req, res, 503, 'Could not load record', apiError(err, `Unable to load ${config.key}.`));
    }
  });

  app.post(`/${config.kind}/:id/edit`, signedIn, async (req, res) => {
    const updated = {};
    for (const key of config.fields) {
      if (req.body[key] !== undefined) updated[key] = req.body[key] === '' ? null : req.body[key];
    }
    try {
      await apiPut(`${config.put}/${encodeURIComponent(req.params.id)}`, updated);
      return flashAndRedirect(req, res, `${label} updated.`, `/${config.kind}/${encodeURIComponent(req.params.id)}/edit`);
    } catch (err) {
      return flashAndRedirect(req, res, apiError(err, `Unable to update ${config.key}.`), `/${config.kind}/${encodeURIComponent(req.params.id)}/edit`);
    }
  });

  app.post(`/${config.kind}/:id/delete`, managerOnly, async (req, res) => {
    try {
      await apiDelete(`${config.put}/${encodeURIComponent(req.params.id)}`);
      // Variants are managed on Inventory now; everything else is on Manage catalog.
      return flashAndRedirect(req, res, `${label} deleted.`, config.kind === 'variants' ? '/inventory' : '/manage');
    } catch (err) {
      const destination = config.kind === 'products' || config.kind === 'variants'
        ? `/${config.kind}/${encodeURIComponent(req.params.id)}/edit` : '/manage';
      return flashAndRedirect(req, res, apiError(err, `Unable to delete ${config.key}.`), destination);
    }
  });
}

// Diagnostics present in the second server.js.
app.get('/api/health', async (req, res) => {
  const result = await health();
  return res.status(result.status === 'ok' ? 200 : 503).json(result);
});
app.get('/api/db/check', async (req, res) => {
  try {
    const result = await apiGet('/db/check');
    return res.status(result?.connected ? 200 : 503).json({ connected: result?.connected === true });
  } catch (_) {
    return res.status(503).json({ connected: false, error: 'Database check unavailable' });
  }
});
if (env !== 'production') {
  app.get('/api/integration/status', signedIn, async (req, res) => {
    const api = await health();
    try {
      const db = await apiGet('/db/check');
      return res.json({ api, database: db, mode: 'root-server / live Flask reporting' });
    } catch (err) {
      return res.status(503).json({ api, database: { connected: false }, error: apiError(err) });
    }
  });
}

app.use((req, res) => errorPage(req, res, 404, 'Page not found', 'The requested page does not exist.'));
app.use((err, req, res, next) => {
  console.error(err);
  if (res.headersSent) return next(err);
  return errorPage(req, res, 500, 'Server error', 'An unexpected error occurred. Check the terminal for details.');
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Space City Couture frontend (${env}): http://localhost:${PORT}`);
    console.log(`Static files: ${publicDir || 'NOT FOUND'}`);
    console.log(`Flask API: ${API_URL}`);
    if (!AUTH_REQUIRED) console.warn('Development mode: read-only page browsing is allowed without login.');
  });
}

// Allows tests to import the app without starting a listener.
module.exports = app;
