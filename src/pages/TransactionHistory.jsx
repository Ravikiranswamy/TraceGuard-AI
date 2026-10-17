import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ArrowDownToLine, Filter, Search, SlidersHorizontal, X } from 'lucide-react';
import { useWorkspace } from '../context/WorkspaceContext';
import { DEMO_TRANSACTIONS } from '../utils/data';
import { DataNotice, DetailModal, Empty, SectionHeader, Surface, TransactionTable } from '../components/Shared';

function saveCsv(rows) {
  const cols = ['transaction_id','step','sender_account_id','receiver_account_id','amount','risk_score','risk_level','recommended_action','source'];
  const text = [cols.join(','),...rows.map(r=>cols.map(k=>JSON.stringify(r[k] ?? '')).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'}));
  const a = document.createElement('a');a.href=url;a.download='traceguard-transactions.csv';a.click();URL.revokeObjectURL(url);
}

export default function TransactionHistory() {
  const { session } = useWorkspace();
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState('report');
  const [risk, setRisk] = useState('ALL');
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(1);
  const search = searchParams.get('search') || '';
  const data = tab === 'report' ? [...DEMO_TRANSACTIONS].reverse() : session;
  const filtered = useMemo(() => data.filter(r => (risk==='ALL'||r.risk_level===risk) && (!search || [r.transaction_id,r.sender_account_id,r.receiver_account_id,r.step].some(k=>String(k||'').toLowerCase().includes(search.toLowerCase())))),[data,risk,search]);
  const pageSize = 12;const totalPages = Math.max(1,Math.ceil(filtered.length/pageSize));const shown = filtered.slice((page-1)*pageSize,page*pageSize);
  const chooseTab = x=>{setTab(x);setPage(1);};
  return <>
    <SectionHeader eyebrow="MONITORING / TRANSACTION LOG" title={<>Transaction <span className="heading-accent">history.</span></>} description="Review individual assessments, search account flows, and compare high-risk activity." action={<button className="secondary-button" disabled={!filtered.length} onClick={()=>saveCsv(filtered)}><ArrowDownToLine size={16}/> Export CSV</button>}/>
    <DataNotice/><div className="history-overview"><div><span>AVAILABLE RECORDS</span><strong>{data.length}</strong><small>{tab==='report'?'Precomputed offline ML test subset':'Checks performed in this browser session'}</small></div><div><span>MATCHING FILTERS</span><strong>{filtered.length}</strong><small>Click any row for details</small></div><div><span>SELECTED DATA SOURCE</span><strong className="source-name">{tab==='report'?'Offline report':'Session checks'}</strong><small>No transaction-history API is implemented yet</small></div></div>
    <Surface title="Scored transaction records" subtitle="All scores are 0–1. History here does not imply a completed settlement." aside={<div className="tabs"><button onClick={()=>chooseTab('report')} className={tab==='report'?'active':''}>Offline report</button><button onClick={()=>chooseTab('session')} className={tab==='session'?'active':''}>Session checks <b>{session.length}</b></button></div>}>
      <div className="table-controls"><div className="table-search"><Search size={17}/><input aria-label="Search transaction history" value={search} onChange={e=>{setSearchParams(e.target.value ? {search:e.target.value}:{});setPage(1);}} placeholder="Search ID, account, or step"/>{search&&<button aria-label="Clear search" onClick={()=>{setSearchParams({});setPage(1);}}><X size={16}/></button>}</div><div className="filter-wrap"><SlidersHorizontal size={17}/><select aria-label="Filter by risk level" value={risk} onChange={e=>{setRisk(e.target.value);setPage(1);}}><option value="ALL">All risk levels</option><option value="HIGH">High risk</option><option value="MEDIUM">Medium risk</option><option value="LOW">Low risk</option></select></div></div>
      <TransactionTable rows={shown} includeStep onSelect={setSelected}/><div className="table-pagination"><span>Showing {filtered.length?(page-1)*pageSize+1:0}–{Math.min(page*pageSize,filtered.length)} of {filtered.length} transactions</span><div><button disabled={page===1} onClick={()=>setPage(p=>p-1)}>Previous</button><span>Page {page} / {totalPages}</span><button disabled={page>=totalPages} onClick={()=>setPage(p=>p+1)}>Next</button></div></div>
    </Surface><DetailModal row={selected} onClose={()=>setSelected(null)}/>
  </>;
}
