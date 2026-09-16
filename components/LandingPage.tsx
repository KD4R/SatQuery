'use client';
import Link from 'next/link';
import {ArrowDownRight,ArrowRight,ChevronRight,Database,Globe2,Layers3,LockKeyhole,Orbit,Play,RadioTower,ShieldCheck,Sparkles,TimerReset,Zap} from 'lucide-react';
import styles from './LandingPage.module.css';
import {useCallback,useEffect,useState} from 'react';
import {motion} from 'motion/react';
import gsap from 'gsap';
import dynamic from 'next/dynamic';

const PremiumOrbitalScene = dynamic(() => import('./PremiumOrbitalScene'), {ssr:false});
import {useRouter} from 'next/navigation';
export default function LandingPage(){
 const router=useRouter();
 const [demo,setDemo]=useState(false);
 const [demoStep,setDemoStep]=useState(0);
 useEffect(()=>{
  router.prefetch('/dashboard');
  const ctx=gsap.context(()=>{
   gsap.from('.heroCopyPremium',{opacity:0,y:24,duration:.8,ease:'power3.out',delay:.12});
   gsap.from('.heroVisualPremium',{opacity:0,x:28,duration:1,ease:'power3.out',delay:.2});
   gsap.from('.premiumReveal',{opacity:0,y:18,stagger:.08,duration:.65,ease:'power2.out',delay:.34});
  });
  return()=>ctx.revert()
 },[router]);
 const launchConsole=useCallback((event:React.MouseEvent<HTMLAnchorElement>)=>{
  event.preventDefault();
  // Route immediately. The dashboard owns its own mission progress UI, so the landing page
  // does not block navigation with a full-screen handoff animation.
  router.push('/dashboard');
 },[router]);
 const demoStages=['QUERY RECEIVED','MISSION PLAN VALIDATED','AOI RESOLVED','OBSERVATIONS DISCOVERED','SENSOR ARBITRATION','EVIDENCE VERIFIED'];
 return <main className={styles.page}>
  <div className={styles.stars}/>
  <nav className={styles.nav}>
   <Link href="/" className={styles.logo}><span className={styles.logoMark}><Orbit size={17}/></span><span><b>SatQuery</b><small>SATELLITE INTELLIGENCE · X-1</small></span></Link>
   <div className={styles.navCenter}><span>MISSION SYSTEM</span><i/> <span>EO / SAR</span></div>
   <Link href="/dashboard" className={styles.navCta} onClick={launchConsole}>Mission console <ArrowRight size={14}/></Link>
  </nav>
  <section className={styles.commandHero}>
   <div className={styles.commandGrid} aria-hidden="true"/>
   <div className={`${styles.commandCopy} heroCopyPremium`}>
    <div className={styles.commandKicker}><span/> MISSION BRIEF</div>
    <h1>Ask a question.<br/>Get an answer<br/><i>with its evidence.</i></h1>
    <p>Flood mapping from Sentinel-1 radar. Radar sees through cloud, and floods come with cloud.</p>
    <Link href="/dashboard" className={styles.commandButton} onClick={launchConsole}>Enter mission console <ArrowRight size={14}/></Link>
    <div className={styles.commandMeta}><span>DEMO FIXTURE</span><b>TRACE SAT-2409</b></div>
   </div>
   <div className={`${styles.commandVisual} heroVisualPremium`}>
    <div className={styles.commandHalo}/>
    <div className={styles.sceneFrame}><PremiumOrbitalScene/></div>
    <div className={`${styles.telemetry} ${styles.t1}`}><span>AOI</span><b>GUNTUR · 2,184 KM²</b><small>16.33° N · 80.27° E</small></div>
    <div className={`${styles.telemetry} ${styles.t2}`}><span>SENSOR ROUTE</span><b>SENTINEL-1 / SAR</b><small>Cloud gate exceeded</small></div>
    <div className={`${styles.telemetry} ${styles.t3}`}><span>EVIDENCE</span><b>3 VERIFIED LINKS</b><small>Trace SAT-2409</small></div>
   </div>
   <aside className={styles.systemPanel}>
    <div className={styles.panelKicker}>MEASURED PERFORMANCE</div>
    <div className={styles.perfRow}><span>HELD-OUT IOU</span><b>0.435</b><small>India + Somalia, regions never trained on</small></div>
    <div className={styles.perfRow}><span>CLASSICAL BASELINE</span><b>0.204</b><small>Otsu log-ratio thresholding</small></div>
    <div className={styles.perfRow}><span>HAND-LABELLED CHIPS</span><b>400</b><small>Sen1Floods11 · 10 regions</small></div>
    <div className={styles.panelKicker}>SYSTEM CHECKS</div>
    <div className={styles.checks}>
      {['CONTRACT SCHEMA','GATEWAY ROUTE TABLE','COASTLINE GEOMETRY','ORBITAL PROPAGATION','OBSERVATION INDEX','MODEL — HAND-ONLY-V2','CONFIDENCE CALIBRATION','EVIDENCE GRAPH'].map((label,i)=><div key={label}><span>{String(i+1).padStart(2,'0')}</span><b>{label}</b><em>{i===6?'58% · PARTIAL':'100% · ACTIVE'}</em></div>)}
    </div>
   </aside>
   <div className={styles.commandStatus}><span>◯</span><b>OBSERVATIONS INDEXED</b><strong>000.004.784</strong><i/> <b>CONSTELLATION</b><strong>SENTINEL-1 · SENTINEL-2</strong><small>SIH 2026 · EPSG:4326</small></div>
  </section>
  <section className={styles.ticker}><div><span>QUERY</span><b>Show me the flooded areas around Guntur and explain why you chose SAR.</b></div><ChevronRight/><div><span>DECISION</span><b>SAR selected · 67% optical cloud</b></div><ChevronRight/><div><span>RESULT</span><b>18.7 ha newly inundated</b></div></section>
  <section id="capabilities" className={styles.section}><div className={styles.sectionKicker}></div><div className={styles.sectionTitle}><h2>One command center.<br/><i>Every layer of the mission.</i></h2><p>Designed around the evidence chain: mission intent, observations, sensor arbitration, analysis, confidence and provenance live together instead of being scattered across tools.</p></div><div className={styles.capGrid}><motion.div className="premiumReveal"><Card icon={<Globe2/>} number="01" title="Map-first intelligence" text="Inspect AOIs, observations, change masks and confidence directly on the map."/></motion.div><motion.div className="premiumReveal"><Card icon={<Sparkles/>} number="02" title="Mission Copilot" text="Translate natural-language questions into bounded, auditable mission plans."/></motion.div><motion.div className="premiumReveal"><Card icon={<ShieldCheck/>} number="03" title="Evidence before assertion" text="Every headline result carries source observations, metadata and a traceable decision path."/></motion.div><motion.div className="premiumReveal"><Card icon={<RadioTower/>} number="04" title="Sensor arbitration" text="Explain optical versus SAR choices using quality gates, cloud cover and uncertainty."/></motion.div></div></section>
  <section id="workflow" className={styles.workflow}><div className={styles.sectionKicker}></div><div className={styles.workflowHead}><h2>From question to <i>evidence.</i></h2><span>FLAGSHIP FLOW / P5</span></div><div className={styles.flow}>{[['01','QUERY','Natural language'],['02','AOI','Resolve & validate'],['03','OBSERVE','Discover scenes'],['04','ROUTE','Optical / SAR'],['05','ANALYZE','Measure change'],['06','PROVE','Evidence + confidence']].map((x,i)=><div className={styles.flowItem} key={x[0]}><span>{x[0]}</span><b>{x[1]}</b><small>{x[2]}</small>{i<5&&<ArrowRight size={15}/>}</div>)}</div></section>
  <section id="evidence" className={styles.evidence}><div className={styles.evidenceVisual}><div className={styles.evidenceWindow}><div className={styles.windowBar}><span/><span/><span/><b>WHY? / EVIDENCE CHAIN</b></div><div className={styles.evidenceRows}><Row n="01" label="Sentinel-1 acquisition" value="VERIFIED"/><Row n="02" label="SAR route rationale" value="VERIFIED"/><Row n="03" label="Flood extent measurement" value="SUPPORTING"/></div><div className={styles.confidenceMini}><div><span>CONFIDENCE</span><b>91%</b></div><div className={styles.confidenceBar}><i/></div><small>Uncertainty is surfaced, not hidden.</small></div><div className={styles.traceLine}><span/><div><b>trace_id</b><small>tr_7f91e2 · run SAT-2409</small></div><div><b>model_version</b><small>geo-v2.1</small></div></div></div></div><div className={styles.evidenceCopy}><div className={styles.sectionKicker}></div><h2>Don't just show<br/><i>the answer.</i></h2><p>Show the chain that makes the answer defensible. SatQuery keeps observations, decisions, measurements and model metadata connected from query to report.</p><div className={styles.proofList}><div><ShieldCheck/><span><b>Verified observations</b><small>Dataset and acquisition provenance</small></span></div><div><LockKeyhole/><span><b>Auditable decisions</b><small>Correlation IDs across every stage</small></span></div><div><TimerReset/><span><b>Uncertainty aware</b><small>Low confidence never becomes confident prose</small></span></div></div></div></section>
  <section className={styles.finalCta}><div><div className={styles.sectionKicker}></div><h2>Ask the Earth<br/><i>what changed.</i></h2></div><Link href="/dashboard" className={styles.ctaOrb} onClick={launchConsole}><span><Play size={20}/></span><b>Open Mission Console</b><small>Start with the flagship demo</small></Link></section>
  <footer className={styles.footer}><div><span className={styles.logoMark}><Orbit size={16}/></span><b>SatQuery AI</b></div><span>Evidence-first satellite intelligence · SIH 2026</span><span>Gateway only · secure by design</span></footer>
  {demo&&<div className={styles.missionLaunchOverlay} aria-live="polite"><div className={styles.launchNoise}/><div className={styles.launchPanel}><div className={styles.launchPanelTop}><span>SECURE MISSION HANDOFF</span><em>DEMO FIXTURE · NO LIVE CLAIM</em></div><div className={styles.launchOrb}><div/><span>{String(Math.min(100,Math.round((demoStep/6)*100))).padStart(3,'0')}%</span></div><div className={styles.launchCopy}><small>QUERY</small><p>Flood impact around Guntur + SAR rationale</p></div><div className={styles.launchStages}>{demoStages.map((stage,i)=><div key={stage} className={i<demoStep?'done':i===demoStep?'active':''}><span>{i<demoStep?'✓':String(i+1).padStart(2,'0')}</span><b>{stage}</b></div>)}</div><div className={styles.launchFooter}><span>TRACE SAT-2409</span><span>Evidence-first execution</span></div></div></div>}
 </main>
}
function Card({icon,number,title,text}:{icon:React.ReactNode;number:string;title:string;text:string}){return <motion.article className={styles.card} whileHover={{y:-6}} whileTap={{scale:.99}} transition={{type:"spring",stiffness:320,damping:24}}><div className={styles.cardTop}><span>{number}</span>{icon}</div><h3>{title}</h3><p>{text}</p><ArrowUpRight/></motion.article>}
function Row({n,label,value}:{n:string;label:string;value:string}){return <div className={styles.eRow}><span>{n}</span><b>{label}</b><em>{value}</em></div>}
function ArrowUpRight(){return <ArrowRight size={15}/>} 
