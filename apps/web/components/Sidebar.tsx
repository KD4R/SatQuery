"use client";

import {
  Activity,
  Bell,
  FileText,
  Globe2,
  History,
  LayoutDashboard,
  ShieldCheck,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

type NavItem = {
  id: string;
  icon: LucideIcon;
  label: string;
};

const items: NavItem[] = [
  { id: "mission", icon: LayoutDashboard, label: "Mission" },
  { id: "map", icon: Globe2, label: "Map" },
  { id: "monitor", icon: Activity, label: "Monitoring" },
  { id: "evidence", icon: ShieldCheck, label: "Evidence" },
  { id: "history", icon: History, label: "History" },
  { id: "reports", icon: FileText, label: "Reports" },
];

type SidebarProps = {
  active: string;
  onSelect: (id: string) => void;
};

export default function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <Globe2 size={20} />
        </div>

        <div>
          <b>SatQuery</b>
          <span>AI / EO</span>
        </div>
      </div>

      <div className="nav-label">WORKSPACE</div>

      <nav className="nav-stack">
        {items.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            className={`nav-item ${active === id ? "active" : ""}`}
          >
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-bottom">
        <button className="nav-item">
          <Bell size={17} />
          <span>Alerts</span>
        </button>

        <button className="nav-item">
          <SlidersHorizontal size={17} />
          <span>Settings</span>
        </button>

        <div className="security-mini">
          <ShieldCheck size={15} />

          <div>
            <b>Evidence first</b>
            <span>Gateway only</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
