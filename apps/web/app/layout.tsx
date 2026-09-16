import type { Metadata } from 'next';
import 'maplibre-gl/dist/maplibre-gl.css';
import './globals.css';
import PageTransition from '../components/PageTransition';

export const metadata: Metadata={title:'SatQuery AI — Mission Control',description:'Evidence-first satellite intelligence command center'};

const themeBootstrap = `(function(){try{var k='satquery-theme';var m=document.cookie.match(/(?:^|; )satquery-theme=(light|dark)(?:;|$)/);var t=localStorage.getItem(k)|| (m&&m[1]);if(t!=='light'&&t!=='dark'){t=window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t;}catch(e){}})()`;

export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{__html:themeBootstrap}} /></head><body><PageTransition />{children}</body></html>}
