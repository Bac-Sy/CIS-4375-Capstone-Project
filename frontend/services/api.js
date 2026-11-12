// Server-side client for the Flask API. Never import this into browser JavaScript.
'use strict';

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

function baseUrl() {
  return (process.env.FLASK_API_URL || 'http://localhost:5000').replace(/\/$/, '');
}

async function request(method, endpoint, { body, query, timeout = 12000 } = {}) {
  const url = new URL(baseUrl() + endpoint);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, String(value));
  });
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: { 'Accept': 'application/json', 'Content-Type': 'application/json',
                 'X-API-Key': process.env.API_KEY || '' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeout)
    });
  } catch (err) {
    throw new ApiError('Could not reach the Flask API', 503);
  }
  let data;
  try { data = await response.json(); } catch (_) { data = null; }
  if (!response.ok) throw new ApiError(data?.message || data?.error || `Flask returned ${response.status}`, response.status, data);
  return data;
}

async function health() {
  try {
    return await request('GET', '/health', { timeout: 3000 });
  } catch (err) {
    return { status: 'unreachable' };
  }
}

module.exports = {
  ApiError,
  health,
  get: (endpoint, query) => request('GET', endpoint, { query }),
  post: (endpoint, body) => request('POST', endpoint, { body })
};
