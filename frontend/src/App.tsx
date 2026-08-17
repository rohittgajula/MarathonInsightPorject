import { useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { clearToken, getToken } from "./api/client";
import { Activities } from "./pages/Activities";
import { ActivityDetail } from "./pages/ActivityDetail";
import { Login } from "./pages/Login";
import { Races } from "./pages/Races";

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());

  if (!authed) {
    return (
      <div className="wrap">
        <Login onSuccess={() => setAuthed(true)} />
      </div>
    );
  }

  return (
    <div className="wrap">
      <nav className="topbar">
        <Link to="/" className="brand">Run Project</Link>
        <div className="navlinks">
          <Link to="/">Activities</Link>
          <Link to="/races">Races</Link>
          <button
            className="linklike"
            onClick={() => { clearToken(); setAuthed(false); }}
          >
            Sign out
          </button>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Activities />} />
        <Route path="/activity/:id" element={<ActivityDetail />} />
        <Route path="/races" element={<Races />} />
      </Routes>
    </div>
  );
}
