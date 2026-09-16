'use client';
import {RefreshCw,TriangleAlert} from 'lucide-react';
export default function Error({reset}:{error:Error&{digest?:string};reset:()=>void}){return <div className="route-error"><TriangleAlert size={20}/><div><b>Mission workspace unavailable</b><span>Something failed while rendering this route.</span></div><button className="ghost-btn" onClick={()=>reset()}><RefreshCw size={13}/> Retry</button></div>}
