/* eslint-disable */
'use client';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {Bell,Command,HelpCircle,Search,Sun,Moon} from 'lucide-react';
import {useEffect,useState} from 'react';
import DashboardTopBar from './DashboardTopBar';
import {applyTheme,readTheme,Theme} from '../lib/theme';

const titles:Record<string,string>={
 '/dashboard':'Mission overview','/dashboard/map':'Map workspace','/dashboard/monitoring':'Persistent monitoring','/dashboard/evidence':'Evidence chain','/dashboard/history':'Mission history','/dashboard/reports':'Reports & decision briefs','/dashboard/alerts':'Alerts & events','/dashboard/settings':'Settings & preferences','/dashboard/admin':'Admin & security'
};

/**
 * Sub-page shell for the dashboard family. The old left sidebar is gone —
 * the top telemetry bar carries every section (see DashboardTopBar), and the
 * Dither field runs behind the page like everywhere else in the family.
 */
export default function PageShell({children}:{children:React.ReactNode}){
 const router=useRouter(); const pathname=usePathname(); const [theme,setTheme]=useState<Theme>('dark');
 useEffect(()=>{['/dashboard','/dashboard/map','/dashboard/monitoring','/dashboard/evidence','/dashboard/history','/dashboard/reports','/dashboard/alerts','/dashboard/settings','/dashboard/admin'].forEach(path=>router.prefetch(path))},[router]);
 useEffect(()=>{const stored=readTheme(); setTheme(stored); applyTheme(stored)},[]);
 return <>
 <div className="app-shell app-shell--flat">
 <main className="main">
  <header className="topbar">
    <div className="top-context">
      <div className="eyebrow">SATQUERY / MISSION CONTROL</div>
      <div className="top-title"><span className="top-title-mark">SQ</span>{' '}Earth Observation Intelligence <span className="live-pill"><i/> LIVE</span></div>
    </div>
    <div className="top-actions">
      <div className="run-pill"><span>RUN</span>SAT-2409</div>
      <button className="icon-btn"><Search size={16}/></button>
      <button className="icon-btn"><Command size={16}/></button>
      <button className="icon-btn"><Bell size={16}/></button>
      <button className="icon-btn" onClick={()=>setTheme((prev: Theme)=>{const next=prev==='dark'?'light':'dark';applyTheme(next);return next})}>{theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}</button>
      <button className="help-btn"><HelpCircle size={15}/><span>Help</span></button>
      <div className="avatar">SQ</div>
    </div>
  </header>
  <DashboardTopBar activeHref={pathname} below/>
  <div className="content">{children}</div>
  <footer className="app-footer"><div><b>SatQuery AI</b><span>Evidence-first satellite intelligence</span></div><div><span>Gateway-only browser access</span><span>•</span><span>Traceable outputs</span><span>•</span><span>Accessible UI</span></div></footer>
 </main>
 </div>
 </>
}
