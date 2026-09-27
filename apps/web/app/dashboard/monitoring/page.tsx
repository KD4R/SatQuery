import PageShell from '../../../components/PageShell';
import SectionHeader from '../../../components/SectionHeader';
import {Activity,Clock3,RadioTower,ShieldCheck} from 'lucide-react';

/**
 * Persistent monitoring. The top bar comes from PageShell (single nav bar per
 * page); content is split into labelled sections — overview stats, the watch
 * list, and the acquisition cadence.
 */
export default function MonitoringPage(){
  return <PageShell>
    <SectionHeader eyebrow="03 / PERSISTENT MONITORING" title="Mission watch" description="Keep an AOI under continuous observation and surface meaningful changes without turning noise into alerts." action={{label:'Create monitoring mission',href:'/dashboard'}}/>

    {/* Section 1 — watch overview */}
    <section className="dash-section" aria-label="Watch overview">
      <div className="dash-section-head"><span className="dash-section-index">01</span><h2>Watch overview</h2></div>
      <div className="stat-grid">
        <div className="stat-box"><span>ACTIVE MISSIONS</span><b>04</b><small>2 high priority</small></div>
        <div className="stat-box"><span>ACQUISITIONS</span><b>18</b><small>last 30 days</small></div>
        <div className="stat-box"><span>ALERTS</span><b>03</b><small>1 requires review</small></div>
        <div className="stat-box"><span>HEALTH</span><b>99.2%</b><small>gateway uptime</small></div>
      </div>
    </section>

    {/* Section 2 — watches and cadence */}
    <section className="dash-section" aria-label="Watches and cadence">
      <div className="dash-section-head"><span className="dash-section-index">02</span><h2>Watches &amp; acquisition</h2></div>
      <div className="surface-grid two">
        <div className="surface">
          <div className="surface-title"><h2>Monitoring missions</h2><span>LIVE</span></div>
          {[['Guntur flood watch','SAR · every 6h','ACTIVE'],['Krishna delta change','Optical + SAR · daily','ACTIVE'],['Urban expansion AOI','Optical · weekly','PAUSED'],['Coastal anomaly watch','SAR · every 12h','ACTIVE']].map((x,i)=>
            <div className="list-card" key={x[0]}>
              <div className="list-icon">{i===0?<RadioTower size={15}/>:<Activity size={15}/>}</div>
              <div><b>{x[0]}</b><small>{x[1]}</small></div>
              <span className={`badge ${x[2]==='ACTIVE'?'success':'warn'}`}>{x[2]}</span>
            </div>
          )}
        </div>
        <div className="surface">
          <div className="surface-title"><h2>Acquisition cadence</h2><span>NEXT 7 DAYS</span></div>
          <div className="chart">{[35,52,44,70,88,61,76,92,68,82,49,64].map((h,i)=><i key={i} style={{height:`${h}%`}}/>)}</div>
          <div className="split-stat"><span><Clock3 size={12}/> Next scene</span><b>03h 42m</b></div>
          <div className="split-stat"><span><ShieldCheck size={12}/> Alert policy</span><b>Evidence gated</b></div>
        </div>
      </div>
    </section>
  </PageShell>
}
