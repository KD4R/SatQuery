'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

const labels: Record<string,string> = {
  '/':'SATQUERY AI','/dashboard':'MISSION CONTROL','/dashboard/map':'MAP WORKSPACE',
  '/dashboard/monitoring':'PERSISTENT MONITORING','/dashboard/evidence':'EVIDENCE CHAIN',
  '/dashboard/history':'MISSION HISTORY','/dashboard/reports':'DECISION BRIEFS',
  '/dashboard/alerts':'ALERTS & EVENTS','/dashboard/settings':'SETTINGS','/dashboard/admin':'ADMIN & SECURITY'
};
const routeOrder=['/dashboard','/dashboard/map','/dashboard/monitoring','/dashboard/evidence','/dashboard/history','/dashboard/reports','/dashboard/alerts','/dashboard/settings','/dashboard/admin'];

export default function PageTransition(){
  const pathname=usePathname();
  const previous=useRef(pathname); const first=useRef(true); const launchPending=useRef(false);
  const [visible,setVisible]=useState(false); const [launching,setLaunching]=useState(false);
  const [direction,setDirection]=useState<'forward'|'backward'>('forward');
  const [label,setLabel]=useState(labels[pathname]||'MISSION CONTROL');

  useEffect(()=>{
    const onLaunch=()=>{ launchPending.current=false; setLaunching(false); setLabel('MISSION CONTROL'); };
    window.addEventListener('satquery:launch-console',onLaunch); return()=>window.removeEventListener('satquery:launch-console',onLaunch);
  },[]);

  useEffect(()=>{
    if(first.current){first.current=false;previous.current=pathname;return;}
    const from=previous.current; const a=routeOrder.indexOf(from), b=routeOrder.indexOf(pathname);
    setDirection(a===-1||b===-1||b>a?'forward':'backward'); setLabel(labels[pathname]||'MISSION CONTROL'); previous.current=pathname;
    // Landing -> Mission Control is intentionally a direct handoff.
    // Do not place a full-screen transition over the route; the landing CTA
    // already calls router.push('/dashboard') and the dashboard owns its own
    // entrance/status animation. This keeps navigation visually immediate.
    if(from==='/'&&pathname==='/dashboard'){
      setVisible(false);
      setLaunching(false);
      return;
    }
    setVisible(true); const t=window.setTimeout(()=>setVisible(false),180); return()=>window.clearTimeout(t);
  },[pathname]);

  return <>
    <div className={`page-transition ${visible?'is-active':''} ${direction}`} aria-hidden="true">
      <div className="transition-panel"><span>ROUTE HANDOFF</span><b>{label}</b></div>
      <div className="transition-scan"/><div className="transition-line"/>
    </div>
    <div className={`launch-transition ${launching?'is-active':''}`} aria-hidden="true">
      <div className="handoff-grid"/><div className="handoff-ring handoff-ring-a"/><div className="handoff-ring handoff-ring-b"/>
      <div className="handoff-center"><span>SECURE ROUTE</span><b>MISSION CONTROL</b><small>Opening geospatial workspace</small></div>
      <div className="handoff-scan"/>
    </div>
  </>;
}
