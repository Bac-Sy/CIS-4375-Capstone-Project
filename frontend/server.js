'use strict';

// Single Express server combining both supplied server.js files.
// Run this file from the project root with npm run dev (or node frontend/server.js).
// Requires Node.js 18+ and: npm install express ejs dotenv express-session

const crypto = require('crypto');
const { AsyncLocalStorage } = require('async_hooks');
const { buildDonut, buildTrend } = require('./lib/charts');
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
app.use(async (req, res, next) => {
  if (req.session.user?.id) {
    try {
      if (!req.session.apiToken) throw new Error('Missing API authentication token');
      const verified = normalizeUser(await apiGet('/auth/me'));
      if (!verified || verified.id !== req.session.user.id) {
        throw new Error('Employee session no longer valid');
      }
      req.session.user = verified;
    } catch (err) {
      // Only log out when the login is really invalid (Flask said 401, or the token/user is missing or wrong).
      // If Flask is just slow or down (timeout, 503), keep the user logged in; the page shows its "unavailable" message.
      const loginInvalid = !(err instanceof ApiError) || err.status === 401;
      if (loginInvalid) {
        delete req.session.user;
        delete req.session.apiToken;
        delete req.session.authMode;
      }
    }
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
  return page(req, res, 'index', {
    api, data,
    donut: buildDonut(data.sales?.by_category || []),
    trend: buildTrend(Array.isArray(data.trend) ? data.trend : []),
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
app.get('/inventory', pageAccess, async (req, res) => {
  try {
    const result = await loadInventory();
    return page(req, res, 'inventory', { ...result, dataAvailable: true });
  } catch (err) {
    console.error('Inventory load failed:', err.message);
    return page(req, res, 'inventory', {
      items: [], rows: [], threshold: 5, dataAvailable: false,
      message: apiError(err, 'Inventory could not be loaded.')
    });
  }
});
app.post('/inventory/:variantId/adjust', signedIn, async (req, res) => {
  try {
    const result = await apiPut('/adjust/inventory', {
      Variant_ID: req.params.variantId,
      New_Quantity: req.body.New_Quantity,
      Employee_ID: req.session.user.id
    });
    return flashAndRedirect(req, res, result?.message || 'Inventory adjusted.', '/inventory');
  } catch (err) {
    return flashAndRedirect(req, res, apiError(err, 'Unable to adjust inventory.'), '/inventory');
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
app.get('/employees', pageAccess, async (req, res) => {
  try {
    const reply = await apiGet('/employees');
    const employees = arrayData(Array.isArray(reply) ? reply : reply?.employees).map(e => ({
      ...e,
      first_name: e.first_name ?? e.First_Name ?? '',
      last_name: e.last_name ?? e.Last_Name ?? '',
      username: e.username ?? e.Username ?? '',
      email: e.email ?? e.Email ?? '',
      role: e.role ?? e.Role ?? ''
    }));
    return page(req, res, 'employees', { employees, dataAvailable: true });
  } catch (err) {
    return page(req, res, 'employees', {
      employees: [], dataAvailable: false,
      message: apiError(err, 'Employee records are unavailable.')
    });
  }
});
app.get('/settings', pageAccess, (req, res) => page(req, res, 'settings', {
  message: req.session.user?.id ? res.locals.message : 'Sign in to see your real account details.'
}));

// Manager catalog index makes the five existing edit pages discoverable.
app.get('/manage', managerOnly, async (req, res) => {
  try {
    const [suppliers, categories, locations, products, variants] = await Promise.all([
      apiGet('/api/suppliers'), apiGet('/api/categories'), apiGet('/api/locations'),
      apiGet('/api/products'), apiGet('/api/product_variants')
    ]);
    return page(req, res, 'manage', { suppliers, categories, locations, products, variants });
  } catch (err) {
    return errorPage(req, res, 503, 'Catalog unavailable', apiError(err, 'Unable to load the catalog.'));
  }
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
    await apiPost('/api/products', {
      Name: name,
      Category_ID: Number(categoryId),
      Supplier_ID: Number(supplierId),
      Availability: Number(availability)
    });
    return flashAndRedirect(req, res, `Product "${name}" added to the catalogue.`, '/manage');
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
    return flashAndRedirect(req, res, reply?.message || 'Employee created.', '/new/employee');
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
      return flashAndRedirect(req, res, `${label} deleted.`, '/manage');
    } catch (err) {
      const destination = config.kind === 'products'
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
