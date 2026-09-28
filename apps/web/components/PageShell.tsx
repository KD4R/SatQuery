/* eslint-disable */
'use client';
import {usePathname,useRouter} from 'next/navigation';
import {useEffect} from 'react';
import DashboardTopBar from './DashboardTopBar';
import PageTelemetry from './PageTelemetry';

/**
 * Sub-page shell for the dashboard family. One nav bar (DashboardTopBar:
 * brand + section chips + icon actions, active tab from the pathname); the
 * UTC/gateway/state telemetry is a quiet subset at the bottom of the page.
 * The old MISSION CONTROL header is gone.
 */

const titles:Record<string,string>={
 '/dashboard':'Mission overview','/dashboard/map':'Map workspace','/dashboard/monitoring':'Persistent monitoring','/dashboard/evidence':'Evidence chain','/dashboard/history':'Mission history','/dashboard/reports':'Reports & decision briefs','/dashboard/alerts':'Alerts & events','/dashboard/settings':'Settings & preferences','/dashboard/admin':'Admin & security'
};

export default function PageShell({children}:{children:React.ReactNode}){
 const router=useRouter(); const pathname=usePathname();
 useEffect(()=>{['/dashboard','/dashboard/map','/dashboard/monitoring','/dashboard/evidence','/dashboard/history','/dashboard/reports','/dashboard/alerts','/dashboard/settings','/dashboard/admin'].forEach(path=>router.prefetch(path))},[router]);
 return <>
  <DashboardTopBar activeHref={pathname}/>
  <div className="app-shell app-shell--flat">
  <main className="main" id="mission-main" tabIndex={-1}>
   <div className="content">{children}</div>
   <PageTelemetry/>
   <footer className="app-footer"><div><b>SatQuery AI</b><span>Evidence-first satellite intelligence</span></div><div><span>Gateway-only browser access</span><span>•</span><span>Traceable outputs</span><span>•</span><span>Accessible UI</span></div></footer>
  </main>
  </div>
 </>
}
