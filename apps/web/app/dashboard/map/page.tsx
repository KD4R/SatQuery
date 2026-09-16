'use client';

import dynamic from 'next/dynamic';
import PageShell from '../../../components/PageShell';
import SectionHeader from '../../../components/SectionHeader';
const MapCanvas = dynamic(() => import('../../../components/MapCanvas'), { ssr: false, loading: () => <div className="map-loading-skeleton"><span/><b>Loading map workspace</b><small>Preparing geospatial layers…</small></div> });

export default function MapPage(){
  return <PageShell>
    <SectionHeader eyebrow="02 / GEOSPATIAL WORKSPACE" title="Map workspace" description="Inspect the active AOI, observation footprints, change polygons and confidence layers in one evidence-first view." action={{label:'Open mission console',href:'/dashboard'}}/>
    <div className="map-page-grid">
      <div className="surface map-page-map"><MapCanvas/></div>
      <aside className="map-page-side">
        <div className="surface"><div className="surface-title"><h2>Layer control</h2><span>AOI / ANALYSIS</span></div>
          <div className="split-stat"><span>Active AOI</span><b>2,184 km²</b></div>
          <div className="split-stat"><span>Change detected</span><b>18.7 ha</b></div>
          <div className="split-stat"><span>Confidence</span><b>91%</b></div>
          <div className="split-stat"><span>Preferred sensor</span><b>SAR</b></div>
          <div className="security-banner" style={{marginTop:16}}><span className="code-chip">EPSG:32644</span><div><b>Geometry validated</b><small>AOI is bounded and ready for analysis.</small></div></div>
        </div>
        <div className="surface"><div className="surface-title"><h2>Evidence status</h2><span>RUN SAT-2409</span></div>
          <div className="alert-item"><b>Observation ready</b><small>Sentinel-1 SAR acquisition linked to the active mission.</small></div>
          <div className="alert-item"><b>Change mask verified</b><small>18.7 ha measurement carries model and dataset provenance.</small></div>
          <div className="alert-item warning"><b>Optical quality gate</b><small>67% cloud cover caused the SAR routing decision.</small></div>
        </div>
      </aside>
    </div>
  </PageShell>
}
