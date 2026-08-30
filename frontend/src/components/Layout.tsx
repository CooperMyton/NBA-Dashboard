import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/teams", label: "Teams", end: false },
  { to: "/players", label: "Players", end: false },
  { to: "/model-lab", label: "Model Lab", end: false },
  { to: "/predictions", label: "Predictions", end: false },
  { to: "/projection", label: "Projection", end: false },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-2 focus:z-20 focus:rounded focus:bg-accent focus:px-3 focus:py-1 focus:text-accent-fg"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-10 border-b-2 border-fg/90 bg-bg/95 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4">
          <div className="flex items-baseline justify-between pb-1 pt-4">
            <div className="flex items-baseline gap-3">
              <span className="font-display text-2xl font-semibold tracking-tight">Hardwood</span>
              <span className="eyebrow hidden sm:block">NBA Analytics &amp; Win Models</span>
            </div>
            <span className="eyebrow hidden md:block">Est. 2026</span>
          </div>
          <nav aria-label="Primary" className="-mb-px flex gap-6 overflow-x-auto">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `whitespace-nowrap border-b-2 pb-2.5 pt-1 text-sm font-medium transition-colors ${
                    isActive
                      ? "border-accent text-fg"
                      : "border-transparent text-fg-muted hover:text-fg"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-border py-6">
        <div className="mx-auto max-w-6xl px-4 text-xs text-fg-muted">
          Hardwood — a personal NBA analytics project. Data via balldontlie. Predictions are for fun,
          not betting.
        </div>
      </footer>
    </div>
  );
}
