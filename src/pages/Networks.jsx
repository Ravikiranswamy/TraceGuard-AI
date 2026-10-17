import { useEffect, useMemo, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, ChevronRight, CircleAlert, Database, GitBranch, Network, RefreshCcw, Search, ShieldAlert, UsersRound } from 'lucide-react';
import observed from '../data/observedEdges.json';
import { useWorkspace } from '../context/WorkspaceContext';
import { getNetwork, getNetworks } from '../services/api';
import { DEMO_NETWORKS, formatNumber, money, pct } from '../utils/data';
import { AlertMessage, DataNotice, Empty, SectionHeader, Surface } from '../components/Shared';

function ObservedGraph() {
  const [focus,setFocus]=useState(observed.hub);
  const edges=observed.edges;
  const accounts=[...new Set(edges.flatMap(e=>[e.source,e.target]))].filter(id=>id!==observed.hub);
  const nodePositions={};
  accounts.forEach((n,i)=>{const rad=(Math.PI*2*i/accounts.length)-Math.PI/2;nodePositions[n]={x:310+205*Math.cos(rad),y:205+155*Math.sin(rad)};});
  const hub={x:310,y:205};
  const focused=edges.filter(e=>e.source===focus||e.target===focus);
  return <div className="observed-graph"><svg viewBox="0 0 620 410" className="observed-graph-svg" role="img" aria-label="Observed sample transfers to and from account 19998"><defs><marker id="tg-arrow" markerWidth="9" markerHeight="9" refX="22" refY="4" orient="auto" markerUnits="userSpaceOnUse"><path d="M0 0 L8 4 L0 8" stroke="#7da4d7" fill="none" strokeWidth="1"/></marker></defs>{edges.map((edge,i)=>{const s=edge.source===observed.hub?hub:nodePositions[edge.source],t=edge.target===observed.hub?hub:nodePositions[edge.target];if(!s||!t)return null;const active=focus===observed.hub||focus===edge.source||focus===edge.target;return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke={active?'#81a9e1':'#d3def0'} opacity={active?0.8:.25} strokeWidth={Math.min(3,1+edge.count*.35)} markerEnd="url(#tg-arrow)"/>;})}{accounts.map((account,i)=>{const {x,y}=nodePositions[account];const focused=focus===account;return <g key={account} onClick={()=>setFocus(account)} className="graph-node" role="button" tabIndex="0" onKeyDown={e=>e.key==='Enter'&&setFocus(account)}><circle cx={x} cy={y} r={focused?19:15} fill={focused?'#2d67e4':'#ddecff'} stroke={focused?'#1744af':'#7cacf2'} strokeWidth="2"/><text x={x} y={y+30} textAnchor="middle" fill="#536884" fontSize="12" fontWeight="600">{account}</text></g>;})}<g onClick={()=>setFocus(observed.hub)} className="graph-node" role="button" tabIndex="0" onKeyDown={e=>e.key==='Enter'&&setFocus(observed.hub)}><circle cx={hub.x} cy={hub.y} r="41" fill="#2665e6" fillOpacity=".09"/><circle cx={hub.x} cy={hub.y} r="27" fill="#2465e7" stroke="#b6d4ff" strokeWidth="5"/><text x={hub.x} y={hub.y+5} textAnchor="middle" fill="#fff" fontSize="12" fontWeight="700">HUB</text><text x={hub.x} y={hub.y+54} textAnchor="middle" fill="#2e59a0" fontSize="13" fontWeight="700">{observed.hub}</text></g></svg><div className="graph-detail"><span>SELECTED ACCOUNT</span><strong>{focus}</strong><span>{focused.length} observed transfer edge{focused.length===1?'':'s'}</span><small>Click a node to explore its direct transfers</small></div></div>;
}

export default function Networks() {
  const { mode, health } = useWorkspace();
  const [networks,setNetworks]=useState(DEMO_NETWORKS);
  const [source,setSource]=useState('offline-report');
  const [err,setErr]=useState('');
  const [loading,setLoading]=useState(false);
  const [selectedId,setSelectedId]=useState(DEMO_NETWORKS[0]?.network_id);
  const [details,setDetails]=useState(null);
  const [search,setSearch]=useState('');
  useEffect(()=>{
    let canceled=false;
    if(mode!=='live'){setNetworks(DEMO_NETWORKS);setSource('offline-report');setErr('');return;}
    setLoading(true);setErr('');
    getNetworks(100).then(res=>{if(canceled)return;if(!Array.isArray(res))throw Error('Unexpected network list format.');setNetworks(res);setSource('live-api');setSelectedId(res[0]?.network_id);}).catch(e=>{if(!canceled){setErr(`${e.message} Showing labelled offline networks instead.`);setNetworks(DEMO_NETWORKS);setSource('offline-report');setSelectedId(DEMO_NETWORKS[0]?.network_id);}}).finally(()=>!canceled&&setLoading(false));
    return ()=>{canceled=true};
  },[mode,health.status]);
  const selected=networks.find(n=>n.network_id===selectedId)||networks[0];
  useEffect(()=>{let canceled=false;setDetails(null);if(source!=='live-api'||!selected?.network_id)return;
    getNetwork(selected.network_id).then(res=>{if(!canceled)setDetails(res);}).catch(()=>{});return()=>{canceled=true};
  },[source,selected?.network_id]);
  const shown=useMemo(()=>networks.filter(n=>n.network_id.toLowerCase().includes(search.toLowerCase())||n.accounts.some(a=>String(a).includes(search))),[networks,search]);
  const selectedInfo=details?.network_id===selected?.network_id?details:selected;
  return <>
    <SectionHeader eyebrow="INVESTIGATE / RELATIONSHIP INTELLIGENCE" title={<>Follow the <span className="heading-accent">connections.</span></>} description="Examine synthetic account communities and a separate graph built only from observed transaction edges." action={<span className="environment-badge"><span className={source==='live-api'?'green-dot':'blue-dot'}/>{source==='live-api'?'API NETWORK SUMMARIES':'OFFLINE NETWORK SUMMARIES'}</span>}/>
    <DataNotice/>
    {err&&<AlertMessage type="error">{err}</AlertMessage>}
    <div className="network-summary-grid"><div><span className="net-stat-icon blue"><Network size={20}/></span><div><strong>{networks.length}</strong><span>Candidate communities</span></div></div><div><span className="net-stat-icon teal"><UsersRound size={20}/></span><div><strong>{new Set(networks.flatMap(n=>n.accounts)).size}</strong><span>Distinct listed accounts</span></div></div><div><span className="net-stat-icon violet"><GitBranch size={20}/></span><div><strong>{observed.edges.length}</strong><span>Observed sample edges</span></div></div></div>
    <div className="network-grid">
      <Surface title="Candidate network communities" subtitle={source==='live-api'?'Summaries returned by GET /networks':'Precomputed offline ML community list'} className="network-list-panel" aside={<span className="mini-tag">{loading?'LOADING...':`${shown.length} RESULTS`}</span>}><div className="network-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find network or account" aria-label="Find network"/></div><div className="network-items">{shown.length?shown.slice(0,52).map(n=><button className={`network-row ${n.network_id===selected?.network_id?'active':''}`} key={n.network_id} onClick={()=>setSelectedId(n.network_id)}><span className="network-row-icon"><GitBranch size={19}/></span><span className="network-row-main"><strong>{n.network_id}</strong><small>{n.n_accounts} accounts · {n.n_transactions} transactions</small></span><span className="network-row-score">{pct(n.mean_account_score)}</span><ChevronRight size={16}/></button>):<Empty title="No matching communities"/>}</div></Surface>
      <div className="network-right"><Surface title={selectedInfo ? `${selectedInfo.network_id} · Community profile`:'Select a community'} subtitle="Precomputed candidate group — member links not provided by this endpoint" aside={<span className="mini-tag">{source==='live-api'?'API SUMMARY':'OFFLINE SUMMARY'}</span>}>
        {selectedInfo?<div className="network-detail"><div className="network-profile-grid"><div><span>ACCOUNTS</span><strong>{selectedInfo.n_accounts}</strong></div><div><span>TRANSFERS</span><strong>{selectedInfo.n_transactions}</strong></div><div><span>TOTAL TRANSFER VALUE</span><strong>{money(selectedInfo.total_amount)}</strong></div><div><span>MEAN ACCOUNT SCORE</span><strong>{pct(selectedInfo.mean_account_score)}</strong></div></div><div className="network-highlight"><span className="network-hub"><GitBranch size={21}/></span><span><small>HUB ACCOUNT</small><strong>{selectedInfo.hub_account}</strong><small>In-degree: {selectedInfo.hub_in_degree}</small></span><span className="hint-pill">Pattern hint: {selectedInfo.pattern_hint||'Unknown'}</span></div><div className="members-heading"><strong>Account members</strong><span>{selectedInfo.accounts?.length||0} listed</span></div><div className="network-members">{selectedInfo.accounts?.map(a=><span key={a}>{a}</span>)}</div><div className="network-caveat"><CircleAlert size={16}/><span>Network memberships are candidate groupings, not proof of money laundering. This endpoint does not expose edge-level evidence, so none is invented here.</span></div></div>:<Empty title="No network selected"/>}
      </Surface>
      <Surface title="Observed transfer relationships" subtitle="Independent ego-network sample centered on account 19998" aside={<span className="mini-tag">18 OBSERVED EDGES</span>}><ObservedGraph/><div className="graph-legend"><span><i className="legend-dot" style={{background:'#2465e7'}}/>Hub</span><span><i className="legend-dot" style={{background:'#90baf1'}}/>Counterparty</span><span>Directed lines = actual sampled transfers</span></div></Surface></div></div>
  </>;
}
