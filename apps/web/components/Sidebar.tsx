/* eslint-disable */
'use client';
import {Activity,Bell,FileText,Globe2,History,LayoutDashboard,Settings,ShieldCheck,SlidersHorizontal,ArrowUpRight} from 'lucide-react';
const items:any[]=[['mission',LayoutDashboard,'Mission'],['map',Globe2,'Map'],['monitor',Activity,'Monitoring'],['evidence',ShieldCheck,'Evidence'],['history',History,'History'],['reports',FileText,'Reports'],['alerts',Bell,'Alerts'],['settings',SlidersHorizontal,'Settings'],['admin',Settings,'Admin']];
export default function Sidebar({active,onSelect}:{active:string;onSelect:(id:string)=>void}){
 const activeLabel=items.find(([id])=>id===active)?.[2] || 'Mission';
 return <aside className="sidebar">
  <div className="brand">
   <div className="brand-mark"><span>SQ</span></div>
   <div className="brand-copy"><b>SatQuery</b><span>AI / EO</span></div>
  </div>
  <div className="sidebar-current"><span>ACTIVE WORKSPACE</span><strong>{activeLabel}</strong><ArrowUpRight size={11}/></div>
  <div className="nav-label">WORKSPACE</div>
  <nav className="nav-stack">{items.map(([id,Icon,label])=><button key={id} onClick={()=>onSelect(id)} className={`nav-item ${active===id?'active':''}`} aria-current={active===id?'page':undefined}><span className="nav-icon"><Icon size={17}/></span><span className="nav-text"><b>{label}</b>{active===id&&<small>{id==='mission'?'Mission Control':label}</small>}</span>{active===id&&<i className="nav-active-dot"/>}</button>)}</nav>
  <div className="sidebar-bottom"><div className="security-mini"><ShieldCheck size={15}/><div><b>Evidence first</b><span>Gateway only</span></div></div></div>
 </aside>
}

