import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeftRight, BarChart3, Bell, CalendarRange, ChevronDown, FileBarChart, FileText, LayoutDashboard, Menu, Moon, Settings, Sun, Users, WalletCards, X } from 'lucide-react'
import { api, setToken } from '../lib/api'
import type { Activity, Client, Filters } from '../lib/types'
import { Logo } from './Logo'
import { DeveloperSignature } from './DeveloperSignature'

const links = [
  { to: '/dashboard', label: 'Vue exécutive', icon: LayoutDashboard },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { to: '/clients', label: 'Clients', icon: Users },
  { to: '/quotes', label: 'Devis & factures', icon: FileText },
  { to: '/profitability', label: 'Rentabilité', icon: BarChart3 },
  { to: '/alerts', label: 'Alertes & économies', icon: AlertTriangle },
  { to: '/forecast', label: 'Prévisions', icon: CalendarRange },
  { to: '/reports', label: 'Rapports', icon: FileBarChart },
]
const headings: Record<string, [string, string]> = {
  '/dashboard': ['Vue exécutive', 'Votre activité, en un coup d’œil.'], '/transactions': ['Transactions', 'Suivez les mouvements de trésorerie.'],
  '/clients': ['Clients', 'Comprenez la valeur et la fiabilité de chaque relation.'], '/quotes': ['Devis & factures', 'Du devis au règlement, sans perdre le fil.'],
  '/profitability': ['Rentabilité', 'Investissez votre temps là où il rapporte.'], '/alerts': ['Alertes & économies', 'Anticipez les risques et les actions utiles.'],
  '/forecast': ['Prévisions', 'Projetez votre trésorerie sur les trois prochains mois.'], '/reports': ['Rapports', 'Exportez un bilan mensuel prêt à partager.'], '/settings': ['Paramètres', 'Personnalisez votre espace FinPilot.'],
}

export function periodParams(filters: Filters) {
  const result: Record<string, string | number | undefined> = { year: filters.year }
  if (filters.period.startsWith('Q')) result.quarter = Number(filters.period.slice(1))
  else if (filters.period.startsWith('M')) result.month = Number(filters.period.slice(1))
  if (filters.activityId) result.activity_id = filters.activityId
  if (filters.clientId) result.client_id = filters.clientId
  return result
}

export function Layout() {
  const location = useLocation()
  const [period, setPeriod] = useState('year')
  const [year, setYear] = useState(new Date().getFullYear())
  const [activityId, setActivityId] = useState('')
  const [clientId, setClientId] = useState('')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [dark, setDark] = useState(localStorage.getItem('finpilot_theme') === 'dark')
  const activityQuery = useQuery({ queryKey: ['activities'], queryFn: () => api<Activity[]>('/activities') })
  const clientQuery = useQuery({ queryKey: ['clients', 'filter'], queryFn: () => api<Client[]>('/clients') })
  const meQuery = useQuery({ queryKey: ['me'], queryFn: () => api<{email:string}>('/auth/me') })
  const settingsQuery = useQuery({ queryKey: ['settings'], queryFn: () => api<Record<string,any>>('/settings') })
  const filters = useMemo<Filters>(() => ({ year, period, activityId, clientId }), [year, period, activityId, clientId])
  const title = headings[location.pathname] || headings['/dashboard']
  useEffect(() => { document.documentElement.classList.toggle('dark', dark); localStorage.setItem('finpilot_theme', dark ? 'dark' : 'light') }, [dark])
  useEffect(() => { if(settingsQuery.data){localStorage.setItem('finpilot_currency',settingsQuery.data.currency||'XOF');localStorage.setItem('finpilot_fx_rate',String(settingsQuery.data.fx_rate||1));setDark(settingsQuery.data.theme==='dark')} }, [settingsQuery.data])
  useEffect(() => { setMobileOpen(false) }, [location.pathname])

  const nav = <>
    <div className="brand-lockup"><div className="brand-lockup__identity"><Logo /><div className="brand-caption">FINANCE OS</div></div><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Fermer le menu"><X size={18}/></button></div>
    <div className="workspace-label">ESPACE DE TRAVAIL</div>
    <nav className="side-nav">{links.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={17}/><span>{label}</span>{to==='/alerts' && <span className="nav-dot"/>}</NavLink>)}</nav>
    <div className="sidebar-bottom"><div className="sidebar-mini-card"><div className="mini-icon"><WalletCards size={18}/></div><div><strong>Finances claires.</strong><span>Décisions sereines.</span></div></div><NavLink to="/settings" className={({isActive}) => `nav-link settings-link ${isActive ? 'active' : ''}`}><Settings size={17}/><span>Paramètres</span></NavLink><div className="profile-row"><div className="avatar">{(meQuery.data?.email || 'FP').slice(0,2).toUpperCase()}</div><div className="profile-info"><strong>{meQuery.data?.email?.split('@')[0] || 'Mon espace'}</strong><span>Entrepreneur individuel</span></div><button className="icon-button small" title="Se déconnecter" onClick={() => { setToken(null); window.location.reload() }}><ChevronDown size={15}/></button></div></div>
  </>

  const years = Array.from({length: 6}, (_,i) => new Date().getFullYear()-i)
  return <div className="app-shell">
    {mobileOpen && <button className="mobile-scrim" onClick={() => setMobileOpen(false)} aria-label="Fermer la navigation"/>}
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>{nav}</aside>
    <main className="main-shell">
      <header className="topbar">
        <button className="mobile-menu icon-button" onClick={() => setMobileOpen(true)} aria-label="Ouvrir le menu"><Menu size={20}/></button>
        <div className="breadcrumbs"><span>FinPilot</span><span className="crumb-sep">/</span><strong>{title[0]}</strong></div>
        <div className="topbar-actions"><button className="icon-button theme-toggle" onClick={() => setDark(v => !v)} title={dark ? 'Passer en mode clair' : 'Passer en mode sombre'}>{dark ? <Sun size={17}/> : <Moon size={17}/>}</button><NavLink to="/alerts" className="icon-button bell-button" title="Alertes"><Bell size={17}/><span/></NavLink><div className="top-avatar">FP</div></div>
      </header>
      <div className="page-wrap">
        <div className="page-heading"><div><div className="eyebrow">PILOTAGE FINANCIER · {new Date().toLocaleDateString('fr-FR',{weekday:'long',day:'numeric',month:'long'})}</div><h1>{title[0]}</h1><p>{title[1]}</p></div><div className="filter-box"><span className="filter-label"><CalendarRange size={15}/> PÉRIODE</span><select value={year} onChange={e => setYear(Number(e.target.value))} aria-label="Année">{years.map(y => <option key={y}>{y}</option>)}</select><select value={period} onChange={e => setPeriod(e.target.value)} aria-label="Période"><option value="year">Année complète</option>{[1,2,3,4].map(q => <option key={`Q${q}`} value={`Q${q}`}>T{q}</option>)}{Array.from({length:12},(_,i) => <option key={`M${i+1}`} value={`M${i+1}`}>{new Date(2020,i,1).toLocaleDateString('fr-FR',{month:'long'})}</option>)}</select>
          <span className="filter-divider"/><select value={activityId} onChange={e => setActivityId(e.target.value)} aria-label="Activité"><option value="">Toutes les activités</option>{activityQuery.data?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select><select value={clientId} onChange={e => setClientId(e.target.value)} aria-label="Client"><option value="">Tous les clients</option>{clientQuery.data?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div></div>
        <Outlet context={filters}/>
        <footer className="page-footer"><span><i/> Base de données <b>SQLite</b></span><span><i/> Objectif <b>pilotage quotidien</b></span><span><i/> Portée <b>vue financière · {year}</b></span><span className="footer-copy">FINPILOT · CONFIDENTIEL</span><DeveloperSignature className="app-signature" /></footer>
      </div>
    </main>
  </div>
}

export function useFilters() {
  return useOutletContext<Filters>()
}
