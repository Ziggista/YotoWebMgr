import { FormEvent, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import {
  AuthProvidersResponse,
  SessionResponse,
  fetchAuthProviders,
  loginWithPassword,
  quickSelectUser,
} from "./api";
import "./App.css";

const sections = ["Library", "Import", "Cards", "Jobs", "Tags", "Settings"];
const sessionStorageKey = "yotowebmgr.session";

function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="panel">
      <p className="eyebrow">Milestone 1</p>
      <h2>{title}</h2>
      <p>
        This area is scaffolded and ready for feature work. The initial focus is authentication,
        library data, job orchestration, and import flows.
      </p>
    </section>
  );
}

function AuthGate({
  session,
  onSessionChange,
}: {
  session: SessionResponse | null;
  onSessionChange: (session: SessionResponse | null) => void;
}) {
  const [authOptions, setAuthOptions] = useState<AuthProvidersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passwordForm, setPasswordForm] = useState({ username: "", password: "" });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadAuthOptions() {
      try {
        const options = await fetchAuthProviders();
        if (!cancelled) {
          setAuthOptions(options);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load auth options.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadAuthOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleQuickSelect(userSlug: string) {
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await quickSelectUser(userSlug);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const nextSession = await loginWithPassword(passwordForm.username, passwordForm.password);
      onSessionChange(nextSession);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (session) {
    return (
      <section className="auth-panel">
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Signed in</p>
            <h2>{session.user.display_name}</h2>
          </div>
          <button className="ghost-button" onClick={() => onSessionChange(null)} type="button">
            Switch user
          </button>
        </div>
        <p className="auth-status">
          Signed in with <strong>{session.user.auth_method}</strong>. {session.message}
        </p>
      </section>
    );
  }

  return (
    <section className="auth-panel">
      <p className="eyebrow">Authentication</p>
      <h2>Select a household user</h2>
      <p className="auth-copy">
        Start simple for now: choose Krystin or Dale from the home page. Password auth and OAuth
        remain scaffolded behind the same API shape so they can replace this flow cleanly later.
      </p>

      {loading ? <p className="auth-status">Loading auth options...</p> : null}
      {error ? <p className="auth-error">{error}</p> : null}

      <div className="user-grid">
        {authOptions?.users.map((user) => (
          <button
            key={user.slug}
            className="user-card"
            disabled={!user.can_quick_select || submitting}
            onClick={() => void handleQuickSelect(user.slug)}
            type="button"
          >
            <span className="user-name">{user.display_name}</span>
            <span className="user-meta">@{user.username}</span>
            <span className="user-meta">
              {user.has_password ? "Password configured" : "Quick select only"}
            </span>
          </button>
        ))}
      </div>

      <form className="password-form" onSubmit={(event) => void handlePasswordSubmit(event)}>
        <div className="auth-panel-header">
          <div>
            <p className="eyebrow">Scaffolded</p>
            <h3>Password sign-in</h3>
          </div>
          <span className="status-pill">
            {authOptions?.providers.find((provider) => provider.key === "password")?.configured
              ? "Ready"
              : "Not configured"}
          </span>
        </div>
        <label>
          Username
          <input
            autoComplete="username"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, username: event.target.value }))
            }
            value={passwordForm.username}
          />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            onChange={(event) =>
              setPasswordForm((current) => ({ ...current, password: event.target.value }))
            }
            type="password"
            value={passwordForm.password}
          />
        </label>
        <button className="primary-button" disabled={submitting} type="submit">
          Sign in with password
        </button>
      </form>

      <div className="oauth-strip">
        <span className="status-pill status-pill-muted">Future</span>
        <p>OAuth 2.0 provider support is reserved in the backend contract and can be enabled later.</p>
      </div>
    </section>
  );
}

export default function App() {
  const [session, setSession] = useState<SessionResponse | null>(() => {
    const stored = window.localStorage.getItem(sessionStorageKey);
    return stored ? (JSON.parse(stored) as SessionResponse) : null;
  });

  useEffect(() => {
    if (session) {
      window.localStorage.setItem(sessionStorageKey, JSON.stringify(session));
      return;
    }
    window.localStorage.removeItem(sessionStorageKey);
  }, [session]);

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">YotoWebMgr</p>
        <h1>Household audio management for Yoto MYO cards.</h1>
        <p className="hero-copy">
          Import preserved originals, prepare Yoto-ready media, plan cards, and track playlist
          history from one place.
        </p>
      </header>

      <AuthGate onSessionChange={setSession} session={session} />

      {session ? (
        <nav className="nav-grid" aria-label="Primary">
          {sections.map((section) => {
            const path = section === "Library" ? "/" : `/${section.toLowerCase()}`;
            return (
              <NavLink
                key={section}
                to={path}
                className={({ isActive }) => `nav-card${isActive ? " nav-card-active" : ""}`}
              >
                {section}
              </NavLink>
            );
          })}
        </nav>
      ) : null}

      <main>
        <Routes>
          <Route
            path="/"
            element={session ? <PlaceholderPage title="Library" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/import"
            element={session ? <PlaceholderPage title="Import" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/cards"
            element={session ? <PlaceholderPage title="Cards" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/jobs"
            element={session ? <PlaceholderPage title="Jobs" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/tags"
            element={session ? <PlaceholderPage title="Tags" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/settings"
            element={
              session ? <PlaceholderPage title="Settings" /> : <PlaceholderPage title="Home" />
            }
          />
        </Routes>
      </main>
    </div>
  );
}
