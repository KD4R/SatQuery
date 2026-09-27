import PageShell from '../../../components/PageShell';
import SectionHeader from '../../../components/SectionHeader';
import {Activity,Database,KeyRound,LockKeyhole,ShieldCheck,Users} from 'lucide-react';

/**
 * Admin & security. The top bar comes from PageShell (single nav bar per
 * page); content is split into labelled sections — posture stats and the
 * control surfaces.
 */
export default function AdminPage(){
  return <PageShell>
    <SectionHeader eyebrow="09 / ADMINISTRATION" title="Admin & security" description="Operational controls for tenant safety, access posture, audit visibility and platform health."/>

    {/* Section 1 — posture overview */}
    <section className="dash-section" aria-label="Posture overview">
      <div className="dash-section-head"><span className="dash-section-index">01</span><h2>Posture overview</h2></div>
      <div className="stat-grid">
        <div className="stat-box"><span>ORGANIZATION</span><b>01</b><small>active tenant</small></div>
        <div className="stat-box"><span>USERS</span><b>18</b><small>12 active today</small></div>
        <div className="stat-box"><span>AUDIT EVENTS</span><b>2,841</b><small>last 30 days</small></div>
        <div className="stat-box"><span>SECURITY</span><b>GOOD</b><small>no open incidents</small></div>
      </div>
    </section>

    {/* Section 2 — control surfaces */}
    <section className="dash-section" aria-label="Control surfaces">
      <div className="dash-section-head"><span className="dash-section-index">02</span><h2>Controls</h2></div>
      <div className="surface-grid three">
        <AdminCard icon={<Users/>} title="Team & roles" text="RBAC posture, members and role boundaries." value="18 users"/>
        <AdminCard icon={<LockKeyhole/>} title="Tenant isolation" text="Organization-scoped access and policy checks." value="ENFORCED"/>
        <AdminCard icon={<Activity/>} title="Observability" text="Trace, mission, run and job correlation IDs." value="HEALTHY"/>
        <AdminCard icon={<Database/>} title="Data policy" text="Evidence datasets and processing versions." value="PINNED"/>
        <AdminCard icon={<KeyRound/>} title="Auth provider" text="OIDC / JWT session posture." value="VERIFIED"/>
        <AdminCard icon={<ShieldCheck/>} title="Audit log" text="Security-sensitive actions and mission events." value="2,841"/>
      </div>
    </section>
  </PageShell>
}

function AdminCard({icon,title,text,value}:{icon:React.ReactNode;title:string;text:string;value:string}){
  return <div className="surface">
    <div className="list-icon">{icon}</div>
    <h3 style={{fontSize:13,margin:'18px 0 6px'}}>{title}</h3>
    <p style={{fontSize:10,color:'var(--muted)',lineHeight:1.6}}>{text}</p>
    <div className="badge success" style={{marginTop:15}}>{value}</div>
  </div>
}
