const path = require('path');
const dotenv = require('dotenv');

// APP_ENV picks which env file to load: development | test | production
const APP_ENV = process.env.APP_ENV || 'development';
dotenv.config({ path: path.join(__dirname, `.env.${APP_ENV}`) });

const express = require('express');
const session = require('express-session');
const rateLimit = require('express-rate-limit');

const flask = require('./services/api');
const fmt = require('./lib/format');
const { buildDonut, buildTrend } = require('./lib/charts');

if (!process.env.SESSION_SECRET) {
  console.error(`SESSION_SECRET is missing. Add it to .env.${APP_ENV}`);
  process.exit(1);
}

const app = express();
const isProd = APP_ENV === 'production';

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
if (isProd) app.set('trust proxy', 1); // needed for secure cookies behind a load balancer

app.use(express.static(path.join(__dirname, 'public')));
app.use(express.urlencoded({ extended: false }));
app.use(session({
  name: 'scc.sid',
  secret: process.env.SESSION_SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: { httpOnly: true, sameSite: 'lax', secure: isProd, maxAge: 8 * 60 * 60 * 1000 }
}));

// Available in every view
app.use((req, res, next) => {
  res.locals.user = req.session.user || null;
  res.locals.env = APP_ENV;
  res.locals.fmt = fmt;
  // One-time message shown by views/template/messages.ejs
  res.locals.message = req.session.flash || null;
  delete req.session.flash;
  next();
});

const wrap = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);

function requireLogin(req, res, next) {
  if (req.session.user) return next();
  return res.redirect('/login');
}

// ------------------------------------------------------------------ auth
const loginLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 10,
  standardHeaders: true,
  legacyHeaders: false,
  handler: (req, res) =>
    res.status(429).render('pages/login', { error: 'Too many attempts. Try again in 15 minutes.', username: '' })
});

app.get('/login', (req, res) => {
  if (req.session.user) return res.redirect('/');
  res.render('pages/login', { error: null, username: '' });
});

app.post('/login', loginLimiter, wrap(async (req, res, next) => {
  const username = String(req.body.username || '').trim();
  const password = String(req.body.password || '');
  if (!username || !password) {
    return res.status(400).render('pages/login', { error: 'Enter your username and password.', username });
  }

  let result;
  try {
    result = await flask.post('/auth/login', { username, password });
  } catch (err) {
    if (err instanceof flask.ApiError && err.status === 401) {
      return res.status(401).render('pages/login', { error: 'Incorrect username or password.', username });
    }
    throw err;
  }

  const e = result.employee;
  req.session.regenerate((err) => {
    if (err) return next(err);
    req.session.user = {
      id: e.id,
      firstName: e.first_name,
      lastName: e.last_name,
      name: `${e.first_name} ${e.last_name}`,
      username: e.username,
      email: e.email,
      role: e.role
    };
    req.session.save(() => res.redirect('/'));
  });
}));

app.post('/logout', (req, res) => {
  req.session.regenerate(() => {
    req.session.flash = 'You have been logged out.';
    res.redirect('/login');
  });
});

// Everything below needs a signed-in employee
app.use(requireLogin);

// ------------------------------------------------------------------ pages
app.get('/', wrap(async (req, res) => {
  const [api, data] = await Promise.all([flask.health(), flask.get('/dashboard')]);
  res.render('pages/index', {
    api,
    data,
    donut: buildDonut(data.sales.by_category),
    trend: buildTrend(data.trend)
  });
}));

app.get('/inventory', wrap(async (req, res) => {
  const data = await flask.get('/inventory');
  res.render('pages/inventory', { items: data.items, threshold: data.low_stock_threshold });
}));

// Orders are the rows of the Invoice table (Sale, Restock, Adjustment)
app.get('/orders', wrap(async (req, res) => {
  const selected = typeof req.query.type === 'string' ? req.query.type : '';
  const data = await flask.get('/orders', { type: selected });
  res.render('pages/orders', { rows: data.rows, types: data.types, limit: data.limit, selected });
}));

app.get('/employees', wrap(async (req, res) => {
  const data = await flask.get('/employees');
  res.render('pages/employees', { employees: data.employees });
}));

app.get('/settings', (req, res) => res.render('pages/settings'));

// ------------------------------------------------------------------ errors
app.use((req, res) => {
  res.status(404).render('pages/error', { title: 'Page not found', detail: 'That page does not exist.' });
});

app.use((err, req, res, next) => {
  console.error(err);
  const apiProblem = err instanceof flask.ApiError;
  res.status(apiProblem ? 502 : 500).render('pages/error', {
    title: 'Something went wrong',
    detail: apiProblem
      ? 'The data service is not responding right now. Try again in a moment.'
      : 'Something went wrong on our side. Try again in a moment.'
  });
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => console.log(`Listening on port ${PORT} (${APP_ENV})`));
