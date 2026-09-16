import Link from 'next/link';
export default function NotFound(){return <div className="route-error"><div><b>Mission view not found</b><span>This route is not registered in the SatQuery workspace.</span></div><Link className="ghost-btn" href="/dashboard">Mission Control</Link></div>}
