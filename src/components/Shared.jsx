import { ArrowUpRight, CheckCircle2, CircleAlert, Database, ExternalLink, LoaderCircle, SearchX, ShieldAlert, Wifi, WifiOff, X } from 'lucide-react';
import { money, pct } from '../utils/data';
import { useWorkspace } from '../context/WorkspaceContext';

export function RiskPill({ level }) { return <span className={`risk-pill risk-${String(level).toLowerCase()}`}><span className="risk-dot" />{level || '—'}</span>; }
export function ActionPill({ action }) { return <span className={`action-pill action-${String(action).toLowerCase()}`}>{action || '—'}</span>; }
export function SourcePill({ source }) { return <span className={`source-pill ${source === 'live-api' ? 'source-live' : ''}`}>{source === 'live-api' ? 'LIVE API' : source === 'offline-report' ? 'OFFLINE REPORT' : 'DEMO RULE'}</span>; }
export function Connection({ model = false }) {
  const { health } = useWorkspace();
  const online = model ? health.model === 'detected' : health.status === 'online';
  const checking = health.status === 'checking';
  const text = model ? online ? `ML v${health.data?.model_version}` : health.model === 'unverified' ? 'Model unverified' : 'Model unavailable' : checking ? 'Checking...' : online ? 'API connected' : 'API offline';
  return <span className={`connection ${online ? 'connected' : 'disconnected'}`}>{checking ? <LoaderCircle size={14} className="spin" /> : online ? <Wifi size={14} /> : <WifiOff size={14} />}{text}</span>;
}
export function SectionHeader({ eyebrow, title, description, action }) {
  return <div className="section-heading"><div><div className="section-eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="heading-action">{action}</div>}</div>;
}
export function Surface({ children, title, subtitle, aside, className = '' }) {
  return <section className={`surface ${className}`}><div className="surface-head"><div><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{aside}</div>{children}</section>;
}
export function Empty({ title = 'Nothing here yet', description, icon: Icon = SearchX }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={22}/></div><strong>{title}</strong>{description && <span>{description}</span>}</div>;
}
export function AlertMessage({ type = 'info', children }) {
  return <div className={`inline-alert ${type}`}>{type === 'error' ? <CircleAlert size={17}/> : type === 'success' ? <CheckCircle2 size={17}/> : <ShieldAlert size={17}/>}<span>{children}</span></div>;
}
export function DataNotice({ small = false }) {
  return <div className={`data-notice ${small ? 'compact' : ''}`}><Database size={16}/><span><strong>Dataset replay</strong> — values shown are from a limited, precomputed synthetic AMLSim test report, not live bank activity.</span></div>;
}
export function TransactionTable({ rows, onSelect, limit, includeStep = false }) {
  const items = typeof limit === 'number' ? rows.slice(0, limit) : rows;
  if (!items.length) return <Empty title="No transactions match" description="Try a different filter or run a scoring check." />;
  return <div className="table-scroll"><table className="transactions-table"><thead><tr><th>TRANSACTION</th>{includeStep && <th>STEP</th>}<th>ACCOUNT FLOW</th><th>AMOUNT</th><th>RISK SCORE</th><th>RISK</th><th>ACTION</th><th aria-label="Open" /></tr></thead><tbody>{items.map((t, i) => <tr key={`${t.source}-${t.transaction_id || i}-${i}`} className={onSelect ? 'clickable-row' : ''} onClick={() => onSelect?.(t)}><td><strong>{t.transaction_id || 'No ID'}</strong><div className="subcell"><SourcePill source={t.source}/></div></td>{includeStep && <td className="mono">{t.step}</td>}<td><div className="account-flow"><span>{t.sender_account_id}</span><span className="flow-arrow">→</span><span>{t.receiver_account_id}</span></div></td><td className="num-cell">{money(t.amount)}</td><td><div className="score-cell"><span className="score-track"><span className={`score-bar ${String(t.risk_level).toLowerCase()}`} style={{width:`${t.risk_score * 100}%`}}/></span><span>{pct(t.risk_score)}</span></div></td><td><RiskPill level={t.risk_level}/></td><td><ActionPill action={t.recommended_action}/></td><td>{onSelect && <ArrowUpRight size={15} color="#9eafc4"/>}</td></tr>)}</tbody></table></div>;
}
export function DetailModal({ row, onClose }) {
  if (!row) return null;
  return <div className="modal-backdrop" onMouseDown={onClose} role="presentation"><div className="detail-modal" role="dialog" aria-modal="true" aria-label="Transaction details" onMouseDown={(e) => e.stopPropagation()}><div className="modal-head"><div><span className="section-eyebrow">TRANSACTION DETAIL</span><h2>{row.transaction_id || 'Scored transaction'}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X size={20}/></button></div><div className="modal-body"><div className="modal-score"><span className="modal-score-num">{pct(row.risk_score,2)}</span><RiskPill level={row.risk_level}/><ActionPill action={row.recommended_action}/></div><div className="detail-grid"><div><span>Sender account</span><strong>{row.sender_account_id}</strong></div><div><span>Receiver account</span><strong>{row.receiver_account_id}</strong></div><div><span>Amount (dataset units)</span><strong>{money(row.amount)}</strong></div><div><span>Transaction step</span><strong>{row.step}</strong></div></div><h4>Risk indicators</h4>{row.reasons?.length ? <div className="reason-stack">{row.reasons.map((r,i)=><div className="reason-item" key={i}><strong>{r.code}</strong><span>{r.description}</span></div>)}</div> : <AlertMessage>Reason codes were not included in this offline scored report. A risk score alone is not an explanation.</AlertMessage>}<div className="modal-footer"><SourcePill source={row.source}/><button className="secondary-button" onClick={onClose}>Close details</button></div></div></div></div>;
}
