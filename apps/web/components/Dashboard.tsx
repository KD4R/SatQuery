/* eslint-disable */
'use client';
import {Download,FileText,Globe2,Menu,PanelRightClose,PanelRightOpen,RefreshCw,ShieldCheck} from 'lucide-react';
import {applyTheme,readTheme,Theme} from '../lib/theme';
import dynamic from 'next/dynamic';
import {useEffect,useMemo,useState} from 'react';import {useRouter} from 'next/navigation';
import Sidebar from './Sidebar'; import Topbar from './Topbar'; import QueryConsole from './QueryConsole'; import EvidencePanel from './EvidencePanel'; import ConfidenceCard from './ConfidenceCard'; import RunTimeline from './RunTimeline'; import SensorCard from './SensorCard'; import MonitoringCard from './MonitoringCard'; import ReportCard from './ReportCard';
const MapCanvas = dynamic(() => import('./MapCanvas'), { ssr: false, loading: () => <div className="map-loading-skeleton"><span/><b>Loading map workspace</b><small>Preparing geospatial layers…</small></div> });
const TraceDrawer = dynamic(() => import('./TraceDrawer'), { ssr: false });
import type {Stage} from '../lib/types';
import { useMissionRun } from '../lib/useMissionRun';
import { toUIMissionState } from '../lib/backendAdapter';
const initialQuery='Show me the flooded areas around Guntur and explain why you chose SAR.';

export default function Dashboard(){
  const router=useRouter();
  const [theme,setTheme]=useState<Theme>('dark');
  const [active,setActive]=useState('mission');
  const [query,setQuery]=useState(initialQuery);
  const [trace,setTrace]=useState(false);
  const [mobileNav,setMobileNav]=useState(false);
  const [rightRail,setRightRail]=useState(true);
  
  const { phase, stages: runStages, agentState, start, reset: runReset } = useMissionRun(false);
  const running = phase === "running";
  
  const mission = useMemo(() => {
    return toUIMissionState(query, agentState, runStages);
  }, [query, agentState, runStages]);

  useEffect(()=>{['/dashboard','/dashboard/map','/dashboard/monitoring','/dashboard/evidence','/dashboard/history','/dashboard/reports','/dashboard/alerts','/dashboard/settings','/dashboard/admin'].forEach(path=>router.prefetch(path))},[router]);
  useEffect(()=>{const stored=readTheme(); setTheme(stored); applyTheme(stored)},[]);
  
  const run=()=>{
    if(running||!query.trim())return;
    start(query, null); // Submit to the live gateway
  };
  
  const reset=()=>{
    setQuery(initialQuery);
    runReset();
  };
  const contentTitle=active==='mission'?'Mission overview':active==='map'?'Map workspace':active==='monitor'?'Persistent monitoring':active==='evidence'?'Evidence chain':active==='history'?'Mission history':'Reports & decision briefs';
  return <div className="app-shell"><div className={`mobile-nav ${mobileNav?'open':''}`}><Sidebar active={active} onSelect={id=>{setMobileNav(false); if(id==='mission') router.push('/dashboard'); else router.push(`/dashboard/${id}`)}}/></div><div className="desktop-sidebar"><Sidebar active={active} onSelect={id=>{if(id==='mission') router.push('/dashboard'); else router.push(`/dashboard/${id}`)}}/></div><main className="main"><Topbar theme={theme} onTheme={()=>setTheme((prev: Theme)=>{const next=prev==='dark'?'light':'dark';applyTheme(next);return next})} runId={mission.runId}/><div className="mobile-top"><button className="icon-btn" onClick={()=>setMobileNav(true)}><Menu size={17}/></button><span>{contentTitle}</span></div><div className="content"><div className="page-head"><div><div className="eyebrow">FLAGSHIP MISSION · FLOOD IMPACT</div><h1>See what changed.<br/><span>Know why.</span></h1><p className="subtitle">A map-first command center for evidence-backed satellite intelligence. Plan the mission, inspect observations, arbitrate sensors, measure change, and keep every conclusion auditable.</p></div><div className="head-actions"><span className="gateway-chip"><i/> Gateway only · secured</span><button className="primary-btn" onClick={reset}><RefreshCw size={14}/> New mission</button></div></div><div className="workspace-mode"><div><b>{contentTitle}</b><span>{active==='mission'?'Flagship flood mission and evidence-first workflow':active==='map'?'Inspect AOI, observations, overlays and confidence layers':active==='monitor'?'Recurring acquisition, alerting and mission watch state':active==='evidence'?'Provenance, observations, model metadata and audit trace':active==='history'?'Temporal mission memory and prior runs':'Decision briefs, report generation and export surfaces'}</span></div><span className="mono-chip">P5 / {active.toUpperCase()}</span></div><div className="workspace"><div className="map-card"><MapCanvas cogUrl={mission.cogUrl} aoiGeoJson={mission.aoiGeoJson} /></div>{rightRail&&<div className="right-rail"><QueryConsole value={query} onChange={setQuery} onRun={run} running={running} onReset={reset}/><ConfidenceCard confidence={mission.confidence}/><EvidencePanel evidence={mission.evidence} onTrace={()=>setTrace(true)}/></div>}<button className="rail-toggle" onClick={()=>setRightRail(!rightRail)} title={rightRail?'Hide analysis rail':'Show analysis rail'}>{rightRail?<PanelRightClose size={15}/>:<PanelRightOpen size={15}/>}</button></div><div className="section-strip"><div><span>MISSION ID</span><b>{mission.missionId}</b></div><div><span>AOI</span><b>{mission.location}</b></div><div><span>RESULT</span><b>{mission.summary}</b></div><div><span>CONFIDENCE</span><b>{mission.confidence?`${Math.round(mission.confidence*100)}%`:'—'}</b></div><div><span>STATUS</span><b className="success-text">{mission.status==='running'?'RUNNING':'EVIDENCE READY'}</b></div></div><div className="bottom-grid"><RunTimeline stages={mission.stages}/><SensorCard/><MonitoringCard/><ReportCard onReport={()=>router.push('/dashboard/reports')}/></div><footer className="app-footer"><div><Globe2 size={14}/><b>SatQuery AI</b><span>Evidence-first satellite intelligence</span></div><div><span>Gateway-only browser access</span><span>•</span><span>Traceable outputs</span><span>•</span><span>Accessible UI</span></div></footer></div></main>{trace&&<TraceDrawer stages={mission.stages} runId={mission.runId} onClose={()=>setTrace(false)}/>}<div className="mobile-nav-overlay" onClick={()=>setMobileNav(false)}/></div>}

