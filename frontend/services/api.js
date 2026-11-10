// All calls to the Flask API go through here.

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

async function request(method, path, { body, query } = {}) {
  const url = new URL(baseUrl() + path);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value);
  });

  let res;
  try {
    res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-API-Key': process.env.API_KEY || '' },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(8000)
    });
  } catch (err) {
    throw new ApiError('Could not reach the API', 503);
  }

  let data = null;
  try { data = await res.json(); } catch (err) { /* empty or non-JSON body */ }

  if (!res.ok) throw new ApiError((data && data.error) || `API returned ${res.status}`, res.status, data);
  return data;
}

// Used by the dashboard footer. Never throws.
async function health() {
  try {
    const res = await fetch(`${baseUrl()}/health`, { signal: AbortSignal.timeout(3000) });
    return await res.json();
  } catch (err) {
    return { status: 'unreachable' };
  }
}

module.exports = {
  ApiError,
  health,
  get: (path, query) => request('GET', path, { query }),
  post: (path, body) => request('POST', path, { body })
};
