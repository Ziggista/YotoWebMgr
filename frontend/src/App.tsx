import { FormEvent, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import AudioPlayer from "react-h5-audio-player";
import "react-h5-audio-player/lib/styles.css";
import {
  AppSettings,
  AuthProvidersResponse,
  ImportSourceInfo,
  ImportRequest,
  Job,
  LibraryItem,
  SessionResponse,
  createImport,
  fetchImportSources,
  fetchImports,
  fetchJobs,
  fetchLibraryItems,
  fetchSettings,
  hideImport,
  fetchAuthProviders,
  loginWithPassword,
  quickSelectUser,
  retryJob,
  updateSettings,
  uploadImport,
} from "./api";
import "./App.css";

const sections = ["Library", "Import", "Cards", "Jobs", "Tags", "Settings"];
const sessionStorageKey = "yotowebmgr.session";
const contentTypes = [
  "Audiobook",
  "Music Album",
  "Story Collection",
  "Podcast",
  "Radio Play",
  "Sleep Sounds",
  "Custom Playlist",
  "Other Audio",
];

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

function EmptyState({ message }: { message: string }) {
  return <p className="muted">{message}</p>;
}

function LibraryPage() {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchLibraryItems()
      .then(setItems)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load library."),
      );
  }, []);

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Library</p>
          <h2>Media library</h2>
        </div>
        <span className="status-pill">{items.length} items</span>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      {items.length === 0 ? (
        <EmptyState message="No library items yet. Create an import to seed the library." />
      ) : (
        <div className="item-list">
          {items.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.content_type} · {item.status}
                </p>
                {item.media_url ? (
                  <div className="library-player">
                    <AudioPlayer
                      customAdditionalControls={[]}
                      customVolumeControls={[]}
                      layout="horizontal-reverse"
                      preload="metadata"
                      showJumpControls={false}
                      src={item.media_url}
                    />
                  </div>
                ) : null}
              </div>
              <span className="status-pill status-pill-muted">#{item.id}</span>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ImportPage({ session }: { session: SessionResponse }) {
  const [imports, setImports] = useState<ImportRequest[]>([]);
  const [sources, setSources] = useState<ImportSourceInfo | null>(null);
  const [mode, setMode] = useState<"upload" | "filesystem">("upload");
  const [form, setForm] = useState({
    title: "",
    source_path: "",
    content_type: "Audiobook",
  });
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function refreshImports() {
    setImports(await fetchImports());
  }

  useEffect(() => {
    void Promise.all([refreshImports(), fetchImportSources().then(setSources)]).catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load imports."),
    );
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "upload") {
        if (!selectedFile) {
          throw new Error("Choose a media file to upload.");
        }
        await uploadImport({
          title: form.title,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
          media_file: selectedFile,
        });
      } else {
        await createImport({
          title: form.title,
          source_type: "filesystem",
          source_path: form.source_path || null,
          content_type: form.content_type,
          requested_by_user_slug: session.user.slug,
        });
      }
      setForm({ title: "", source_path: "", content_type: "Audiobook" });
      setSelectedFile(null);
      await refreshImports();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Import failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleHideImport(importId: number) {
    setError(null);
    try {
      await hideImport(importId);
      await refreshImports();
    } catch (hideError) {
      setError(hideError instanceof Error ? hideError.message : "Hide failed.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Import</p>
          <h2>Add media</h2>
        </div>
        <span className="status-pill">{imports.length} imports</span>
      </div>

      <div className="segmented-control" aria-label="Import source">
        <button
          className={mode === "upload" ? "segment-active" : ""}
          onClick={() => setMode("upload")}
          type="button"
        >
          Upload
        </button>
        <button
          className={mode === "filesystem" ? "segment-active" : ""}
          onClick={() => setMode("filesystem")}
          type="button"
        >
          Filesystem
        </button>
      </div>

      <form className="import-form" onSubmit={(event) => void handleSubmit(event)}>
        <div className="import-grid">
          <label>
            Title
            <input
              onChange={(event) =>
                setForm((current) => ({ ...current, title: event.target.value }))
              }
              required
              value={form.title}
            />
          </label>
          <label>
            Content type
            <select
              onChange={(event) =>
                setForm((current) => ({ ...current, content_type: event.target.value }))
              }
              value={form.content_type}
            >
              {contentTypes.map((contentType) => (
                <option key={contentType}>{contentType}</option>
              ))}
            </select>
          </label>
        </div>

        {mode === "upload" ? (
          <div className="drop-panel">
            <label className="file-picker">
              <span>{selectedFile ? selectedFile.name : "Choose media file"}</span>
              <input
                accept={sources?.allowed_extensions.join(",")}
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                type="file"
              />
            </label>
            <p className="muted">
              Uploads are staged in {sources?.browser_upload_path ?? "/media/imports/uploads"}.
            </p>
          </div>
        ) : (
          <div className="drop-panel">
            <label>
              Source path
              <input
                onChange={(event) =>
                  setForm((current) => ({ ...current, source_path: event.target.value }))
                }
                placeholder={`${sources?.filesystem_drop_path ?? "/media/imports/drop"}/example.m4b`}
                value={form.source_path}
              />
            </label>
            <p className="muted">
              Filesystem imports are limited to {sources?.filesystem_drop_path ?? "/media/imports/drop"}.
            </p>
          </div>
        )}

        <div className="form-actions">
          <span className="muted">Queued as {session.user.display_name}</span>
          <button className="primary-button" disabled={submitting} type="submit">
            {submitting ? "Queueing" : "Queue import"}
          </button>
        </div>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}

      <h3 className="subsection-title">Recent imports</h3>
      <div className="item-list">
        {imports.length === 0 ? (
          <EmptyState message="No imports queued yet." />
        ) : (
          imports.map((item) => (
            <article className="list-row" key={item.id}>
              <div>
                <h3>{item.title}</h3>
                <p className="muted">
                  {item.source_type} · {item.content_type} · {item.status}
                </p>
              </div>
              <div className="row-actions">
                <span className="status-pill status-pill-muted">
                  Job {item.related_job_id ?? "pending"}
                </span>
                <button
                  aria-label={`Hide ${item.title}`}
                  className="danger-icon-button"
                  onClick={() => void handleHideImport(item.id)}
                  title="Hide and mark ready for deletion"
                  type="button"
                >
                  x
                </button>
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}

function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refreshJobs() {
    setJobs(await fetchJobs());
  }

  useEffect(() => {
    void refreshJobs().catch((loadError) =>
      setError(loadError instanceof Error ? loadError.message : "Failed to load jobs."),
    );
  }, []);

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshJobs();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Retry failed.");
    }
  }

  return (
    <section className="panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Jobs</p>
          <h2>Background work</h2>
        </div>
        <button className="ghost-button" onClick={() => void refreshJobs()} type="button">
          Refresh
        </button>
      </div>
      {error ? <p className="auth-error">{error}</p> : null}
      {jobs.length === 0 ? (
        <EmptyState message="No jobs yet." />
      ) : (
        <div className="item-list">
          {jobs.map((job) => (
            <article className="list-row" key={job.id}>
              <div>
                <h3>{job.type}</h3>
                <p className="muted">
                  {job.status} · {job.progress_percent}% · {job.progress_message}
                </p>
              </div>
              {job.status === "failed" ? (
                <button className="ghost-button" onClick={() => void handleRetry(job.id)} type="button">
                  Retry
                </button>
              ) : (
                <span className="status-pill status-pill-muted">#{job.id}</span>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void fetchSettings()
      .then(setSettings)
      .catch((loadError) =>
        setError(loadError instanceof Error ? loadError.message : "Failed to load settings."),
      );
  }, []);

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!settings) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      setSettings(await updateSettings(settings));
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  if (!settings) {
    return (
      <section className="panel">
        <p className="eyebrow">Settings</p>
        <h2>Processing defaults</h2>
        <EmptyState message="Loading settings..." />
      </section>
    );
  }

  return (
    <section className="panel">
      <p className="eyebrow">Settings</p>
      <h2>Processing defaults</h2>
      <form className="data-form" onSubmit={(event) => void handleSave(event)}>
        <label>
          Target duration hours
          <input
            min="0"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_duration_hours: Number(event.target.value) } : current,
              )
            }
            step="0.1"
            type="number"
            value={settings.target_duration_hours}
          />
        </label>
        <label>
          Target size MB
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, target_size_mb: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.target_size_mb}
          />
        </label>
        <label>
          Audiobook bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, audiobook_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.audiobook_bitrate_kbps}
          />
        </label>
        <label>
          Music bitrate kbps
          <input
            min="1"
            onChange={(event) =>
              setSettings((current) =>
                current ? { ...current, music_bitrate_kbps: Number(event.target.value) } : current,
              )
            }
            type="number"
            value={settings.music_bitrate_kbps}
          />
        </label>
        <label className="checkbox-row">
          <input
            checked={settings.normalise_loudness_default}
            onChange={(event) =>
              setSettings((current) =>
                current
                  ? { ...current, normalise_loudness_default: event.target.checked }
                  : current,
              )
            }
            type="checkbox"
          />
          Normalise loudness by default
        </label>
        <button className="primary-button" disabled={saving} type="submit">
          Save settings
        </button>
      </form>
      {error ? <p className="auth-error">{error}</p> : null}
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
            element={session ? <LibraryPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/import"
            element={
              session ? <ImportPage session={session} /> : <PlaceholderPage title="Home" />
            }
          />
          <Route
            path="/cards"
            element={session ? <PlaceholderPage title="Cards" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/jobs"
            element={session ? <JobsPage /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/tags"
            element={session ? <PlaceholderPage title="Tags" /> : <PlaceholderPage title="Home" />}
          />
          <Route
            path="/settings"
            element={session ? <SettingsPage /> : <PlaceholderPage title="Home" />}
          />
        </Routes>
      </main>
    </div>
  );
}
