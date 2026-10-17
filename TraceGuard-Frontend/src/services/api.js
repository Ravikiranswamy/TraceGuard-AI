/**
 * ML API contract: TraceGuard-ML/INTEGRATION.md and traceguard/schemas.py.
 * In development, the /api prefix goes through Vite's local proxy (no browser CORS).
 * In production, VITE_API_BASE_URL must point to the public HTTPS backend origin.
 */
const API_ROOT = import.meta.env.DEV
  ? '/api'
  : (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'ApiError'; this.status = status; }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      ...options,
      headers: { 'Accept': 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) },
      signal: options.signal || AbortSignal.timeout(12000),
    });
  } catch (error) {
    throw new ApiError(error.name === 'TimeoutError'
      ? 'The backend timed out. Check that FastAPI is running.'
      : 'Cannot connect to FastAPI. Check the backend URL and that your server is running.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const details = body?.error?.details?.map((x) => `${x.field}: ${x.message}`).join('; ');
    throw new ApiError(details || body?.error?.message || (typeof body?.detail === 'string' ? body.detail : null) || `Request failed (HTTP ${response.status}).`, response.status);
  }
  if (response.status === 204) return null;
  return response.json().catch(() => { throw new ApiError('The server returned invalid JSON.', response.status); });
}

export const getHealth = () => request('/health');
export const getNetworks = (limit = 50) => request(`/networks?limit=${encodeURIComponent(limit)}`);
export const getNetwork = (id) => request(`/networks/${encodeURIComponent(id)}`);
export const recordTransaction = (payload) => request('/record', { method: 'POST', body: JSON.stringify(payload) });

export function validateScoreResponse(data) {
  if (!data || typeof data !== 'object' || !Number.isFinite(data.risk_score) || data.risk_score < 0 || data.risk_score > 1 ||
      !['LOW', 'MEDIUM', 'HIGH'].includes(data.risk_level) ||
      !['ALLOW', 'REVIEW', 'HOLD'].includes(data.recommended_action) ||
      !Array.isArray(data.reasons) || !data.reasons.every((r) => typeof r.code === 'string' && typeof r.description === 'string') ||
      typeof data.sender_known !== 'boolean' || typeof data.receiver_known !== 'boolean' ||
      typeof data.model_version !== 'string' || !Number.isFinite(data.latency_ms)) {
    throw new ApiError('Unexpected /score response. The backend may still be running the older 0–100 mock contract. Please integrate the ML schema in INTEGRATION.md.');
  }
  return data;
}

export const scoreTransaction = async (payload) => validateScoreResponse(
  await request('/score', { method: 'POST', body: JSON.stringify(payload) })
);
