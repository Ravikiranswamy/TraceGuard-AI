import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity, ArrowRight, ArrowUpRight, ChevronRight, CircleDot, Database, GitBranch, ShieldAlert, ShieldCheck, Sparkles, UsersRound } from 'lucide-react';
import { useWorkspace } from '../context/WorkspaceContext';
import { Connection, DataNotice, DetailModal, RiskPill, SectionHeader, Surface, TransactionTable } from '../components/Shared';
import { DEMO_NETWORKS, DEMO_TRANSACTIONS, countRisk, formatNumber, getRiskTrend, money, pct, suspiciousAccounts } from '../utils/data';

const trend = getRiskTrend(DEMO_TRANSACTIONS);
const distribution = ['HIGH', 'MEDIUM', 'LOW'].map(name => ({ name, value: countRisk(DEMO_TRANSACTIONS,name) }));
const colors = { HIGH: '#ea6574', MEDIUM: '#f5aa55', LOW: '#2dc4a0' };
const high = countRisk(DEMO_TRANSACTIONS, 'HIGH');

function MetricCard({ icon: Icon, label, value, footer, tone }) {
  return <div className="metric-card"><div className="metric-top"><span className={`metric-icon ${tone}`}><Icon size={20}/></span><span className="metric-arrow"><ArrowUpRight size={17}/></span></div><div className="metric-number">{value}</div><div className="metric-label">{label}</div><div className="metric-footer"><span className="metric-small-dot"/>{footer}</div></div>;
}
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>Step {label}</strong>{payload.map(item => <div key={item.name}><span style={{ color: item.color }}>●</span> {item.name}: <b>{item.value}</b></div>)}</div>;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { session, mode, health, refreshHealth } = useWorkspace();
  const [selected, setSelected] = useState(null);
  const latest = useMemo(() => [...DEMO_TRANSACTIONS].reverse().slice(0, 6), []);
  const topAlerts = useMemo(() => [...DEMO_TRANSACTIONS].filter(r => r.risk_level === 'HIGH').sort((a,b) => b.risk_score - a.risk_score).slice(0,4), []);
  return <>
    <SectionHeader eyebrow="MONITORING / OVERVIEW" title={<>Clarity in every <span className="heading-accent">decision.</span></>} description="One workspace to spot unusual activity, trace account relationships, and investigate transaction risk." action={<button className="primary-button" onClick={() => navigate('/risk-check')}><CircleDot size={17}/> New risk check <ArrowRight size={17}/></button>}/>
    <section className="hero-panel"><div className="hero-copy"><span className="hero-eyebrow"><Sparkles size={15}/> TRACEGUARD INTELLIGENCE</span><h2>See the patterns.<br/><em>Not just the transactions.</em></h2><p>A network-aware view of suspicious activity. Built for faster, more informed human decisions.</p><div className="hero-actions"><button className="hero-button" onClick={() => navigate('/networks')}>Explore networks <ArrowUpRight size={16}/></button><span className="hero-secondary"><span className="pulse-dot"/> Synthetic demonstration</span></div></div><div className="hero-visual" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="orbit orbit-three"/><svg viewBox="0 0 320 220"><g stroke="#6bafff" strokeWidth="1.5" fill="none" opacity=".42"><path d="M162 108 89 50 75 137 133 174 237 159 255 70 162 108 237 159M89 50 255 70M75 137 162 108M133 174 162 108"/></g>{[[89,50,6],[75,137,5],[133,174,6],[237,159,7],[255,70,6],[162,108,14]].map(([cx,cy,r],i)=><g key={i}><circle cx={cx} cy={cy} r={r+7} fill="#277efa" fillOpacity=".12"/><circle cx={cx} cy={cy} r={r} fill={i===5?'#65e6fb':'#5c9ff7'} stroke="#d8f2ff" strokeWidth="1.4"/></g>)}</svg><div className="hero-floating-badge"><ShieldCheck size={17}/> Intelligent screening <span className="badge-check">✓</span></div></div></section>
    <DataNotice />
    <div className="metrics-grid">
      <MetricCard icon={Activity} label="Transactions in sample" value={formatNumber(DEMO_TRANSACTIONS.length)} footer="Offline scored test subset" tone="indigo"/>
      <MetricCard icon={ShieldAlert} label="High-risk observations" value={formatNumber(high)} footer="From precomputed scores" tone="rose"/>
      <MetricCard icon={UsersRound} label="Accounts in candidate networks" value={formatNumber(suspiciousAccounts)} footer="Not confirmed fraudulent" tone="orange"/>
      <MetricCard icon={GitBranch} label="Candidate networks" value={formatNumber(DEMO_NETWORKS.length)} footer="Offline community detection" tone="teal"/>
    </div>
    <div className="dashboard-charts">
      <Surface className="trend-panel" title="Risk activity over time" subtitle="Transaction count per time step · offline sample" aside={<div className="chart-legend"><span><i className="legend-dot" style={{background:colors.HIGH}}/>High</span><span><i className="legend-dot" style={{background:colors.MEDIUM}}/>Medium</span><span><i className="legend-dot" style={{background:colors.LOW}}/>Low</span></div>}>
        <div className="trend-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend} margin={{top:10,right:10,left:-27,bottom:0}}><defs>{['HIGH','MEDIUM','LOW'].map(k=><linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={colors[k]} stopOpacity={.13}/><stop offset="100%" stopColor={colors[k]} stopOpacity={0}/></linearGradient>)}</defs><CartesianGrid strokeDasharray="4 5" vertical={false} stroke="#e8edf5"/><XAxis dataKey="step" tickLine={false} axisLine={false} tick={{fontSize:11,fill:'#9babbc'}} dy={9}/><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{fontSize:11,fill:'#9babbc'}}/><Tooltip content={<ChartTooltip/>}/>{['LOW','MEDIUM','HIGH'].map(k=><Area key={k} type="monotone" name={k} dataKey={k} stroke={colors[k]} strokeWidth={2.7} fill={`url(#grad-${k})`} dot={false} activeDot={{r:5,strokeWidth:0}}/>)}</AreaChart></ResponsiveContainer></div>
      </Surface>
      <Surface title="Risk distribution" subtitle="120 offline-scored test transactions" aside={<span className="mini-tag">SAMPLE ONLY</span>}>
        <div className="risk-visual"><div className="donut-wrap"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="value" cx="50%" cy="50%" innerRadius={63} outerRadius={81} strokeWidth={0} paddingAngle={3} startAngle={90} endAngle={-270}>{distribution.map(item=><Cell key={item.name} fill={colors[item.name]}/>)}</Pie><Tooltip formatter={(v,name)=>[`${v} transactions`,name]}/></PieChart></ResponsiveContainer><div className="donut-label"><strong>{DEMO_TRANSACTIONS.length}</strong><span>Scored</span></div></div><div className="dist-legend">{distribution.map(({name,value})=><div key={name}><span><i className="legend-dot" style={{background:colors[name]}}/>{name.charAt(0)+name.slice(1).toLowerCase()}</span><strong>{value} <small>({Math.round(value/DEMO_TRANSACTIONS.length*100)}%)</small></strong></div>)}</div></div>
      </Surface>
    </div>
    <div className="dashboard-bottom">
      <Surface title="Recent transactions" subtitle="Latest records from the offline test subset" className="dashboard-table" aside={<button className="text-button" onClick={() => navigate('/transactions')}>View all <ArrowRight size={16}/></button>}><TransactionTable rows={latest} onSelect={setSelected}/></Surface>
      <div className="right-stack"><Surface title="Priority alerts" subtitle="Highest-scoring offline observations" aside={<button className="text-button" onClick={() => navigate('/alerts')}>View all <ArrowRight size={16}/></button>}><div className="priority-list">{topAlerts.map(a=><button key={a.transaction_id} className="priority-item" onClick={()=>setSelected(a)}><span className="priority-icon"><ShieldAlert size={17}/></span><span className="priority-main"><strong>{a.transaction_id}</strong><span>{a.sender_account_id} → {a.receiver_account_id} · {money(a.amount)}</span></span><span className="priority-score">{pct(a.risk_score)}</span><ChevronRight size={15}/></button>)}</div></Surface>
      <Surface title="System connections" subtitle="Real-time availability checks" aside={<button className="text-button" onClick={refreshHealth}>Refresh <ArrowRight size={15}/></button>}><div className="status-list"><div><div className="system-icon"><Activity size={17}/></div><span><strong>FastAPI backend</strong><small>GET /health</small></span><Connection/></div><div><div className="system-icon"><ShieldCheck size={17}/></div><span><strong>Scoring model</strong><small>Model identity from health response</small></span><Connection model/></div></div>{session.length > 0 && <div className="session-status">{session.length} session check{session.length>1?'s':''} recorded locally</div>}</Surface></div>
    </div>
    <DetailModal row={selected} onClose={() => setSelected(null)}/>
  </>;
}
