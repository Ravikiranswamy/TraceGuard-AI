import rawTransactions from '../data/demoTransactions.json';
import rawNetworks from '../data/networks.json';

export const DEMO_TRANSACTIONS = rawTransactions.map((t) => ({
  transaction_id: t.id, sender_account_id: t.sender, receiver_account_id: t.receiver,
  amount: t.amount, step: t.step, risk_score: t.score, risk_level: t.level,
  recommended_action: t.action, reasons: [], source: 'offline-report',
}));
export const DEMO_NETWORKS = rawNetworks;
export const countRisk = (rows, risk) => rows.filter((t) => t.risk_level === risk).length;
export const suspiciousAccounts = new Set(DEMO_NETWORKS.flatMap((n) => n.accounts)).size;
export const formatNumber = (n) => new Intl.NumberFormat('en-US').format(n);
export const money = (n) => '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (n, digits = 1) => `${(Number(n) * 100).toFixed(digits)}%`;
export const riskColor = (risk) => ({ HIGH: '#ed6174', MEDIUM: '#f2a84c', LOW: '#27b98b' }[risk] || '#95a4b8');

export function demoAssessment(payload) {
  // Transparent, deterministic UI placeholder: not the trained model.
  const amount = Number(payload.amount);
  let score = 0.12;
  const reasons = [];
  if (amount <= 20) {
    score += .42;
    reasons.push({ code: 'DEMO_SMALL_AMOUNT', description: 'Placeholder rule: amount is at most 20. Not a validated fraud signal.' });
  }
  if (amount >= 500) {
    score += .3;
    reasons.push({ code: 'DEMO_LARGE_AMOUNT', description: 'Placeholder rule: amount is at least 500. Not a validated fraud signal.' });
  }
  if (Number(payload.sender_account_id) % 5 === 0) {
    score += .2;
    reasons.push({ code: 'DEMO_ACCOUNT_ID_RULE', description: 'Illustrative account-ID rule for interface testing only.' });
  }
  score = Math.min(score, .99);
  const level = score >= .7 ? 'HIGH' : score >= .4 ? 'MEDIUM' : 'LOW';
  return {
    transaction_id: payload.transaction_id || null, risk_score: score, risk_level: level,
    recommended_action: { LOW: 'ALLOW', MEDIUM: 'REVIEW', HIGH: 'HOLD' }[level],
    reasons, sender_known: false, receiver_known: false, model_version: 'DEMO-HEURISTIC (NOT ML)',
    latency_ms: 0, source: 'demo-rule',
  };
}

export function getRiskTrend(rows) {
  const counts = new Map();
  rows.forEach((r) => {
    const key = r.step;
    if (!counts.has(key)) counts.set(key, { step: key, HIGH: 0, MEDIUM: 0, LOW: 0 });
    counts.get(key)[r.risk_level]++;
  });
  return [...counts.values()].sort((a, b) => a.step - b.step);
}
