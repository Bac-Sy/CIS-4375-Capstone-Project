'use strict';
// Offline route/entry-point checks. These are not live database/browser tests.
const assert = require('assert');
const path = require('path');
const Module = require('module');
const fs = require('fs');
const root = path.resolve(__dirname, '..', '..'); // project root (this file is in frontend/tests)
const expected = path.join(root, 'frontend', 'server.js');
const pkg = require(path.join(root, 'package.json'));
assert.strictEqual(pkg.main, 'frontend/server.js');
for (const command of Object.values(pkg.scripts)) {
  assert(command.includes('frontend/server.js'), 'npm script does not reference frontend/server.js');
}
const routes = [];
let views = null;
const app = {
  disable: () => {},
  set(name, value) { if (name === 'views') views = value; },
  use: () => {},
  get(url, ...handlers) { routes.push({ method: 'GET', url, handlers }); },
  post(url, ...handlers) { routes.push({ method: 'POST', url, handlers }); }
};
const express = () => app;
let staticDir = null;
express.json = () => (_req, _res, next) => next();
express.urlencoded = () => (_req, _res, next) => next();
express.static = dir => { staticDir = dir; return (_req, _res, next) => next(); }; 
const originalLoad = Module._load;
const originalExistsSync = fs.existsSync;
const expectedStatic = path.join(root, 'public');
const expectedCss = path.join(expectedStatic, 'css', 'styles.css');
// The offline patch does not include public/, but the user's actual root does.
fs.existsSync = p => String(p) === expectedCss || originalExistsSync(p);
Module._load = function(request, parent, isMain) {
  if (request === 'express') return express;
  if (request === 'express-session') return () => (_req, _res, next) => next();
  if (request === 'dotenv') return { config: () => ({ parsed: {} }) };
  return originalLoad.call(this, request, parent, isMain);
};
const oldSecret = process.env.SESSION_SECRET;
process.env.SESSION_SECRET = 'A'.repeat(64);
let returnedApp;
try { returnedApp = require(expected); }
finally {
  Module._load = originalLoad;
  fs.existsSync = originalExistsSync;
  if (oldSecret === undefined) delete process.env.SESSION_SECRET;
  else process.env.SESSION_SECRET = oldSecret;
}
assert.strictEqual(returnedApp, app);
assert.strictEqual(views, path.join(root, 'frontend', 'views'));
assert.strictEqual(staticDir, expectedStatic, 'Static assets must load from root/public');
const route = (method, url) => {
  const found = routes.find(r => r.method === method && r.url === url);
  assert(found, `missing ${method} ${url}`);
  return found;
};
for (const endpoint of ['/', '/login', '/inventory', '/orders', '/employees', '/settings',
  '/manage', '/new/employee', '/new/product', '/api/health', '/api/db/check', '/api/integration/status',
  '/suppliers/:id/edit', '/categories/:id/edit', '/locations/:id/edit',
  '/products/:id/edit', '/variants/:id/edit']) route('GET', endpoint);
for (const endpoint of ['/login', '/process/login', '/logout', '/create/employee', '/create/product',
  '/inventory/:variantId/adjust', '/suppliers/:id/edit', '/suppliers/:id/delete',
  '/categories/:id/edit', '/categories/:id/delete',
  '/locations/:id/edit', '/locations/:id/delete',
  '/products/:id/edit', '/products/:id/delete',
  '/variants/:id/edit', '/variants/:id/delete']) route('POST', endpoint);
// Logged-out users may not reach the adjustment handler.
const adjust = route('POST','/inventory/:variantId/adjust');
let denied = null;
adjust.handlers[0]({ method:'POST', session:{} }, {
  status(code) { denied = { code }; return this; },
  render(view) { denied.view = view; },
  redirect(url) { denied = { redirect:url }; }
}, () => { throw new Error('Logged-out stock update was permitted'); });
assert(denied && denied.code === 401, 'Missing authentication on inventory adjustment');
const deleteSupplier = route('POST','/suppliers/:id/delete');
let deleteDenied = null;
deleteSupplier.handlers[0]({ method:'POST', session:{user:{id:'1',role:'Employee'}} }, {
  status(code) { deleteDenied = { code }; return this; },
  render(view) { deleteDenied.view = view; }
}, () => { throw new Error('Non-manager deletion was permitted'); });
assert(deleteDenied && deleteDenied.code === 403, 'Manager role not required for deletion');
console.log(`PASS: frontend/server.js registered ${routes.length} GET/POST routes`);
console.log('PASS: EJS path is frontend/views, static files are root/public, and npm scripts target frontend/server.js');
console.log('PASS: logged-out stock adjustment denied; non-manager delete denied');

// Product-creation integration simulation: mock only the Flask HTTP response,
// exercise the actual Express route handlers and verify the posted JSON.
async function verifyProductFlow() {
  const originalFetch = global.fetch;
  const calls = [];
  global.fetch = async (url, opts = {}) => {
    const routePath = new URL(String(url)).pathname;
    calls.push({ routePath, method: opts.method, body: opts.body ? JSON.parse(opts.body) : null });
    if (routePath === '/api/categories') return { ok: true, status: 200,
      text: async () => JSON.stringify([{ Category_ID: 1, Category: 'Dresses' }]) };
    if (routePath === '/api/suppliers') return { ok: true, status: 200,
      text: async () => JSON.stringify([{ Supplier_ID: 2, Name: 'Houston Threads' }]) };
    if (routePath === '/api/products' && opts.method === 'POST') return { ok: true, status: 201,
      text: async () => JSON.stringify({ message: 'Product added!', Product_ID: 9 }) };
    if (routePath === '/api/products/7' && opts.method === 'DELETE') return { ok: false, status: 409,
      text: async () => JSON.stringify({ message: 'This product has variants and cannot be deleted.' }) };
    if (routePath === '/api/products/8' && opts.method === 'DELETE') return { ok: true, status: 200,
      text: async () => JSON.stringify({ message: 'Product deleted!' }) };
    throw new Error(`Unexpected API mock: ${opts.method} ${routePath}`);
  };
  try {
    const manager = { id: '1', role: 'Manager' };
    const add = route('POST', '/create/product');
    const addGet = route('GET', '/new/product');
    const productDelete = route('POST', '/products/:id/delete');
    const denyRes = () => ({ status(code) { this.code = code; return this; }, render(view) { this.view = view; } });
    let denied = denyRes();
    add.handlers[0]({ method: 'POST', session: { user: { id: '2', role: 'Employee' } } }, denied,
      () => { throw new Error('Employee could create a product'); });
    assert.strictEqual(denied.code, 403);
    denied = denyRes();
    productDelete.handlers[0]({ method: 'POST', session: { user: { id: '2', role: 'Employee' } } }, denied,
      () => { throw new Error('Employee could delete a product'); });
    assert.strictEqual(denied.code, 403);

    const getRequest = { method: 'GET', session: { user: manager } };
    const getResponse = { locals: {}, status(code) { this.code = code; return this; },
      render(view, values) { this.view = view; this.values = values; } };
    let allowedGet = false;
    addGet.handlers[0](getRequest, getResponse, () => { allowedGet = true; });
    assert(allowedGet);
    await addGet.handlers[1](getRequest, getResponse);
    assert.strictEqual(getResponse.view, 'pages/newproduct');
    assert.strictEqual(getResponse.values.categories[0].Category_ID, 1);
    assert.strictEqual(getResponse.values.suppliers[0].Supplier_ID, 2);

    const addReq = { method: 'POST', body: { Name: 'New Dress', Category_ID: '1',
      Supplier_ID: '2', Availability: '0' }, session: { user: manager } };
    const addRes = { redirect(code, target) { this.redirectCode = code; this.target = target; } };
    let allowedPost = false;
    add.handlers[0](addReq, addRes, () => { allowedPost = true; });
    assert(allowedPost);
    await add.handlers[1](addReq, addRes);
    assert.strictEqual(addRes.redirectCode, 303);
    assert.strictEqual(addRes.target, '/products/9/variants/new'); // a new product goes straight to Add variants
    assert(addReq.session.flash.includes('New Dress'));
    const posted = calls.find(c => c.routePath === '/api/products' && c.method === 'POST');
    assert.deepStrictEqual(posted.body, { Name: 'New Dress', Category_ID: 1,
      Supplier_ID: 2, Availability: 0 });

    const beforeBad = calls.length;
    const badReq = { method: 'POST', body: { Name: '', Category_ID: '1',
      Supplier_ID: '2', Availability: '1' }, session: { user: manager } };
    const badRes = { redirect(code, target) { this.code = code; this.target = target; } };
    await add.handlers[1](badReq, badRes);
    assert.strictEqual(badRes.target, '/new/product');
    assert.strictEqual(calls.length, beforeBad, 'Invalid input was sent to the database');

    const deleteReq = { method: 'POST', params: { id: '7' }, session: { user: manager } };
    const deleteRes = { redirect(code, target) { this.code = code; this.target = target; } };
    await productDelete.handlers[1](deleteReq, deleteRes);
    assert.strictEqual(deleteRes.code, 303);
    assert.strictEqual(deleteRes.target, '/products/7/edit');
    assert(deleteReq.session.flash.includes('variants'), 'Variant deletion conflict not displayed');

    const deleteOkReq = { method: 'POST', params: { id: '8' }, session: { user: manager } };
    const deleteOkRes = { redirect(code, target) { this.code = code; this.target = target; } };
    await productDelete.handlers[1](deleteOkReq, deleteOkRes);
    assert.strictEqual(deleteOkRes.code, 303);
    assert.strictEqual(deleteOkRes.target, '/manage');
    assert(deleteOkReq.session.flash.includes('deleted'));
    assert(calls.some(c => c.routePath === '/api/products/8' && c.method === 'DELETE'));
    console.log('PASS: product creation, validation, role checks, 303 redirects, and delete success/conflict feedback');
  } finally {
    global.fetch = originalFetch;
  }
}
verifyProductFlow().catch(err => { console.error(err); process.exitCode = 1; });
