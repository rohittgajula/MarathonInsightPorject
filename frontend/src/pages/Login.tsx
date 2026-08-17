import { useState } from "react";
import { login } from "../api/client";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      onSuccess();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card stack center-narrow" onSubmit={submit}>
      <div>
        <div className="eyebrow">Run Project</div>
        <h1 style={{ fontSize: 22 }}>Sign in</h1>
      </div>
      <label className="stack" style={{ gap: 5 }}>
        <span className="faint">Username</span>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus required />
      </label>
      <label className="stack" style={{ gap: 5 }}>
        <span className="faint">Password</span>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      {error && <p className="error" style={{ margin: 0 }}>{error}</p>}
      <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}
