/* eslint-disable */
'use client';
import Link from 'next/link';
import {usePathname,useRouter} from 'next/navigation';
import {Bell,Command,HelpCircle,Menu,Moon,Search,Sun} from 'lucide-react';
import {useEffect,useState} from 'react';
import Sidebar from './Sidebar';
import {applyTheme,readTheme,Theme} from '../lib/theme';

const titles:Record<string,string>={
 '/dashboard':'Mission overview','/dashboard/map':'Map workspace','/dashboard/monitoring':'Persistent monitoring','/dashboard/evidence':'Evidence chain','/dashboard/history':'Mission history','/dashboard/reports':'Reports & decision briefs','/dashboard/alerts':'Alerts & events','/dashboard/settings':'Settings & preferences','/dashboard/admin':'Admin & security'
};
export default function PageShell({children}:{children:React.ReactNode}){
 const router=useRouter(); const pathname=usePathname(); const [theme,setTheme]=useState<Theme>('dark'); const [mobile,setMobile]=useState(false);
 useEffect(()=>{['/dashboard','/dashboard/map','/dashboard/monitoring','/dashboard/evidence','/dashboard/history','/dashboard/reports','/dashboard/alerts','/dashboard/settings','/dashboard/admin'].forEach(path=>router.prefetch(path))},[router]);
 useEffect(()=>{const stored=readTheme(); setTheme(stored); applyTheme(stored)},[]);
 const active=pathname.split('/')[2]||'dashboard';
 const activeMap:Record<string,string>={dashboard:'mission',map:'map',monitoring:'monitor',evidence:'evidence',history:'history',reports:'reports',alerts:'alerts',settings:'settings',admin:'admin'};
 return <div className="app-shell"><div className={`mobile-nav ${mobile?'open':''}`}><Sidebar active={activeMap[active]||'mission'} onSelect={id=>{setMobile(false); if(id==='mission')router.push('/dashboard'); else router.push(`/dashboard/${id}`)}}/></div><div className="desktop-sidebar"><Sidebar active={activeMap[active]||'mission'} onSelect={id=>router.push(id==='mission'?'/dashboard':`/dashboard/${id}`)}/></div><main className="main"><header className="topbar"><div className="top-context"><div className="eyebrow">SATQUERY / MISSION CONTROL</div><div className="top-title"><span className="top-title-mark">SQ</span>Earth Observation Intelligence <span className="live-pill"><i/> LIVE</span></div></div><div className="top-actions"><div className="run-pill"><span>RUN</span>SAT-2409</div><button className="icon-btn"><Search size={16}/></button><button className="icon-btn"><Command size={16}/></button><button className="icon-btn"><Bell size={16}/></button><button className="icon-btn" onClick={()=>setTheme((prev: Theme)=>{const next=prev==='dark'?'light':'dark';applyTheme(next);return next})}>{theme==='dark'?<Sun size={16}/>:<Moon size={16}/>}</button><button className="help-btn"><HelpCircle size={15}/><span>Help</span></button><div className="avatar">SQ</div></div></header><div className="mobile-top"><button className="icon-btn" onClick={()=>setMobile(true)}><Menu size={17}/></button><span>{titles[pathname]||'Mission Control'}</span></div><div className="content">{children}</div><footer className="app-footer"><div><b>SatQuery AI</b><span>Evidence-first satellite intelligence</span></div><div><span>Gateway-only browser access</span><span>•</span><span>Traceable outputs</span><span>•</span><span>Accessible UI</span></div></footer></main></div>
}

