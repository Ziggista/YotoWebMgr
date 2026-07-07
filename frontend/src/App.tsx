import { NavLink, Route, Routes } from "react-router-dom";
import "./App.css";

const sections = ["Library", "Import", "Cards", "Jobs", "Tags", "Settings"];

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

export default function App() {
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

      <main>
        <Routes>
          <Route path="/" element={<PlaceholderPage title="Library" />} />
          <Route path="/import" element={<PlaceholderPage title="Import" />} />
          <Route path="/cards" element={<PlaceholderPage title="Cards" />} />
          <Route path="/jobs" element={<PlaceholderPage title="Jobs" />} />
          <Route path="/tags" element={<PlaceholderPage title="Tags" />} />
          <Route path="/settings" element={<PlaceholderPage title="Settings" />} />
        </Routes>
      </main>
    </div>
  );
}

