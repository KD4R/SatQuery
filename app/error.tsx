'use client';
import {RefreshCw,TriangleAlert} from 'lucide-react';
export default function Error({reset}:{error:Error&{digest?:string};reset:()=>void}){return <main className="app-state"><div className="state-content error"><TriangleAlert size={24}/><span className="state-kicker">SATQUERY AI / RECOVERABLE ERROR</span><h1>Mission workspace hit a problem.</h1><p>The page could not finish rendering. Your mission context is preserved; try the view again.</p><button className="primary-btn" onClick={()=>reset()}><RefreshCw size={14}/> Retry workspace</button></div></main>}
