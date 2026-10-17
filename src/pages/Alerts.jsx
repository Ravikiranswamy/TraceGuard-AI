import { useMemo, useState } from 'react';
import { ArrowRight, Check, CircleCheck, ClipboardCheck, ShieldAlert, ShieldEllipsis, TriangleAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useWorkspace } from '../context/WorkspaceContext';
import { DEMO_TRANSACTIONS, money, pct } from '../utils/data';
import { DataNotice, DetailModal, Empty, RiskPill, SectionHeader, SourcePill, Surface } from '../components/Shared';

export default function Alerts() {
  const { session, reviewed, toggleReview } = useWorkspace();
  const [source,setSource]=useState('report');const [risk,setRisk]=useState('ALL');const [selected,setSelected]=useState(null);
  const navigate=useNavigate();
  const data=source==='report'?DEMO_TRANSACTIONS:session;
  const alerts=useMemo(()=>[...data].filter(x=>x.risk_level!=='LOW' && (risk==='ALL'||x.risk_level===risk)).sort((a,b)=>b.risk_score-a.risk_score),[data,risk]);
  return <>
    <SectionHeader eyebrow="INVESTIGATE / ALERT QUEUE" title={<>Prioritize what <span className="heading-accent">matters.</span></>} description="Identify transactions worth attention and organize a local review queue. No holds or reviews are submitted to a bank." action={<button className="primary-button" onClick={()=>navigate('/risk-check')}><ShieldEllipsis size={17}/> New risk check <ArrowRight size={16}/></button>}/>
    <DataNotice/>
    <div className="alert-summary-grid"><div className="alert-summary strong"><span className="alert-summary-icon"><TriangleAlert size={22}/></span><div><strong>{alerts.filter(x=>x.risk_level==='HIGH').length}</strong><span>High-priority observations</span></div><small>Risk level HIGH</small></div><div className="alert-summary"><span className="alert-summary-icon amber"><ShieldAlert size={22}/></span><div><strong>{alerts.filter(x=>x.risk_level==='MEDIUM').length}</strong><span>Manual-review suggestions</span></div><small>Risk level MEDIUM</small></div><div className="alert-summary"><span className="alert-summary-icon teal"><ClipboardCheck size={22}/></span><div><strong>{reviewed.length}</strong><span>Locally marked reviewed</span></div><small>Browser session only</small></div></div>
    <Surface title="Alert inbox" subtitle="Priority ordered by model risk score, not observed fraud." aside={<div className="tabs"><button className={source==='report'?'active':''} onClick={()=>setSource('report')}>Offline report</button><button className={source==='session'?'active':''} onClick={()=>setSource('session')}>Session checks</button></div>}>
      <div className="alert-toolbar"><div><span className="queue-pip"/> {alerts.length} observations in queue</div><select value={risk} onChange={e=>setRisk(e.target.value)} aria-label="Filter alert priority"><option value="ALL">All priorities</option><option value="HIGH">High only</option><option value="MEDIUM">Medium only</option></select></div>
      {alerts.length===0?<Empty icon={CircleCheck} title="No alerts in this view" description="Try the offline report tab or run a transaction risk check."/>:<div className="alert-list">{alerts.slice(0,60).map((r,i)=>{const key=`${r.source||source}-${r.transaction_id||'no-id'}-${r.step}-${r.recorded_at||'report'}`;const done=reviewed.includes(key);return <div key={key} className={`alert-entry ${done?'reviewed':''}`}><div className={`alert-entry-symbol ${r.risk_level.toLowerCase()}`}><ShieldAlert size={20}/></div><div className="alert-entry-main"><div className="alert-entry-head"><strong>{r.transaction_id||'Session check'}</strong><RiskPill level={r.risk_level}/><SourcePill source={r.source}/></div><p>Account <b>{r.sender_account_id}</b> → <b>{r.receiver_account_id}</b> <span className="middle-dot">·</span> Step {r.step} <span className="middle-dot">·</span> {money(r.amount)}</p></div><div className="alert-entry-score"><strong>{pct(r.risk_score)}</strong><span>Risk score</span></div><div className="alert-entry-buttons"><button className="secondary-button small" onClick={()=>setSelected(r)}>Inspect</button><button className={`review-button ${done?'done':''}`} onClick={()=>toggleReview(key)} title="Changes only local interface state"><Check size={15}/>{done?'Reviewed':'Mark reviewed'}</button></div></div>})}</div>}
      {alerts.length>60&&<div className="table-pagination"><span>Displaying the 60 highest-scoring observations of {alerts.length} available.</span></div>}
    </Surface><div className="queue-footer-notice"><ShieldAlert size={16}/> Marking an alert reviewed only changes this dashboard's session UI. It does not approve, freeze, block, or change any transfer.</div><DetailModal row={selected} onClose={()=>setSelected(null)}/>
  </>;
}
