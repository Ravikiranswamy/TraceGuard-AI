import { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Activity, ArrowRight, Bell, ChartNoAxesCombined, ChevronDown, CircleHelp, Command, GitBranch, LayoutDashboard, Menu, Search, ShieldCheck, ShieldPlus, X } from 'lucide-react';
import { useWorkspace } from '../context/WorkspaceContext';
import { Connection } from './Shared';

const menu = [
  { to: '/', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/risk-check', icon: ShieldPlus, label: 'Risk check' },
  { to: '/transactions', icon: Activity, label: 'Transactions' },
  { to: '/alerts', icon: Bell, label: 'Alerts & reviews' },
  { to: '/networks', icon: GitBranch, label: 'Account networks' },
];
const titleMap = { '/': 'Overview', '/risk-check': 'Transaction risk check', '/transactions': 'Transaction history', '/alerts': 'Alerts & reviews', '/networks': 'Network explorer' };

export function Sidebar({ mobileOpen, setMobileOpen }) {
  const { mode, setMode, health, refreshHealth } = useWorkspace();
  return <>
    <div className={`sidebar-overlay ${mobileOpen ? 'show' : ''}`} onClick={() => setMobileOpen(false)}/>
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand-row"><div className="brand-symbol"><ShieldCheck size={23} strokeWidth={2.4}/></div><div><div className="brand-name">TraceGuard<span> AI</span></div><div className="brand-sub">INVESTIGATION INTELLIGENCE</div></div><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18}/></button></div>
      <div className="sidebar-group-label">WORKSPACE</div>
      <nav className="nav-list">{menu.map(({ to, icon: Icon, label, end }) => <NavLink key={to} to={to} end={end} onClick={() => setMobileOpen(false)} className={({isActive}) => `nav-item ${isActive ? 'selected' : ''}`}><Icon size={19} strokeWidth={1.85}/><span>{label}</span>{to === '/alerts' && <span className="nav-count">!</span>}</NavLink>)}</nav>
      <div className="sidebar-divider"/>
      <div className="sidebar-group-label">ENVIRONMENT</div>
      <div className="mode-switch" role="group" aria-label="Data mode"><button className={mode === 'demo' ? 'active' : ''} onClick={() => setMode('demo')}>Demo</button><button className={mode === 'live' ? 'active' : ''} onClick={() => { setMode('live'); refreshHealth(); }}>Live API</button></div>
      <div className="mode-note">{mode === 'demo' ? 'Explore the interface with labelled sample data and mock form scoring.' : health.status === 'online' ? 'API online. Live checks use the ML response contract.' : 'Live checks require a reachable FastAPI server.'}</div>
      <div className="sidebar-bottom"><div className="sidebar-help"><div className="sidebar-help-icon"><CircleHelp size={18}/></div><div><strong>Built for AI for Good</strong><small>IBM Z Datathon 2026</small></div></div><div className="sidebar-foot"><span>TRACEGUARD / WORKSPACE</span><span>v1.0</span></div></div>
    </aside>
  </>;
}

export function Topbar({ openMenu }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { mode } = useWorkspace();
  const [search, setSearch] = useState('');
  return <header className="topbar"><div className="topbar-left"><button className="hamburger icon-button" aria-label="Open menu" onClick={openMenu}><Menu size={22}/></button><div className="breadcrumb"><span>Workspace</span><span className="slash">/</span><strong>{titleMap[location.pathname] || 'Workspace'}</strong></div></div><div className="topbar-right"><form className="global-search" onSubmit={(e) => { e.preventDefault(); navigate(`/transactions?search=${encodeURIComponent(search.trim())}`); }}><Search size={16}/><input aria-label="Search transactions" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search transactions..."/><kbd>↵</kbd></form><div className="topbar-divider"/><div className="data-mode-chip"><span className={mode === 'demo' ? 'blue-dot' : 'green-dot'}/>{mode === 'demo' ? 'Demo workspace' : 'Live API mode'}</div><div className="user-avatar" title="Investigation console">TG</div></div></header>;
}

export default function Navigation({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  return <div className="app-shell"><Sidebar mobileOpen={mobileOpen} setMobileOpen={setMobileOpen}/><div className="workspace"><Topbar openMenu={() => setMobileOpen(true)}/><main className="main-content">{children}</main><footer className="page-footer"><span>TraceGuard AI <span className="footer-dot">·</span> Decision support, not automated enforcement</span><span>IBM Z Datathon 2026</span></footer></div></div>;
}
