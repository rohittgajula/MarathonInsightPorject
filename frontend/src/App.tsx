import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api, clearToken, getToken } from "./api/client";
import { Activities } from "./pages/Activities";
import { ActivityDetail } from "./pages/ActivityDetail";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Races } from "./pages/Races";
import { usePointerGlow } from "./lib/usePointerGlow";
import type { Race } from "./lib/types";

const NAV = [
  { to: "/", label: "Tomorrow", end: true },
  { to: "/activities", label: "Activities", end: false },
  { to: "/races", label: "Races", end: false },
];

function SidebarRaceCard() {
  const { data } = useQuery({
    queryKey: ["targetRace"],
    queryFn: () => api.get<Race | null>("/races/target/"),
  });
  if (!data || data.is_past) return null;
  return (
    <div className="side-card">
      <div className="eyebrow">Target race</div>
      <div style={{ fontWeight: 700, fontSize: 13.5, marginTop: 4 }}>{data.name}</div>
      <div className="faint">{data.distance_label} · {data.race_date}</div>
      <div className="mono" style={{ fontSize: 24, fontWeight: 750, letterSpacing: "-.03em", marginTop: 8 }}>
        {data.weeks_until}
      </div>
      <div className="faint">weeks to go</div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  usePointerGlow();
  const location = useLocation();

  if (!authed) {
    return <div className="main"><Login onSuccess={() => setAuthed(true)} /></div>;
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <NavLink to="/" className="brand">Run Project</NavLink>
        <nav className="side-nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}
                     className={({ isActive }) => (isActive ? "active" : "")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="side-foot">
          <SidebarRaceCard />
          <button className="ghost" onClick={() => { clearToken(); setAuthed(false); }}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">
        <div className="page" key={location.pathname}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/activities" element={<Activities />} />
          <Route path="/activity/:id" element={<ActivityDetail />} />
          <Route path="/races" element={<Races />} />
        </Routes>
        </div>
      </main>
    </div>
  );
}
