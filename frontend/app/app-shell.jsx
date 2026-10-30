import ThemeToggle from "./theme-toggle";

// Shared navigation and branding for both AXIOM capabilities. The research
// workspace owns its API state; this shell does not change its data flow.
export default function AppShell({
  section = "workspace",
  objectiveCount = 0,
  provider = "unknown",
  demoMode = false,
  connection = "checking",
  children,
}) {
  const workspace = section === "workspace";
  const providerIsLive = String(provider).toLowerCase() === "nebius";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand-lockup brand-link" href="/#objective-workspace" aria-label="AXIOM home">
          <div className="brand-mark" aria-hidden="true"><span /></div>
          <div>
            <div className="brand-name">AXIOM<span className="brand-period">.</span></div>
            <div className="brand-subtitle">RESEARCH INTELLIGENCE</div>
          </div>
        </a>

        <nav className="sidebar-navigation" aria-label="AXIOM capabilities">
          <div className="sidebar-label">YOUR WORKSPACE</div>
          <a
            className={"nav-item" + (workspace ? " nav-item-active" : "")}
            href="/#objective-workspace"
            aria-current={workspace ? "page" : undefined}
            title="Research Workspace"
          >
            <span className="nav-icon" aria-hidden="true">◫</span>
            Research Workspace
            {workspace && <span className="nav-count">{objectiveCount}</span>}
          </a>
          <a
            className={"nav-item" + (!workspace ? " nav-item-active" : "")}
            href="/showcase"
            aria-current={!workspace ? "page" : undefined}
            title="AI Research Assistant"
          >
            <span className="nav-icon" aria-hidden="true">✳</span>
            AI Research Assistant
          </a>
        </nav>

        <div className="sidebar-process">
          <div className="sidebar-label">{workspace ? "THE METHOD" : "AI-ASSISTED PLANNING"}</div>
          <div><span>01</span>{workspace ? "Define the question" : "Start with an objective"}</div>
          <div><span>02</span>{workspace ? "Run the experiment" : "Generate a proposal"}</div>
          <div><span>03</span>{workspace ? "Follow the evidence" : "Review before execution"}</div>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-quote">“The answer is only as good as the experiment.”</div>
          <div className="footer-line" />
          <div className="footer-label">{workspace ? "REASONING ENGINE" : "PROPOSAL MODEL"}</div>
          <div className="provider-line">
            <span className={"provider-dot " + (workspace && providerIsLive ? "provider-live" : "")} />
            <span>{workspace ? (provider === "unknown" ? "Not detected" : provider) : "Nemotron 3 Super"}</span>
          </div>
          {workspace ? (!providerIsLive && !demoMode && (
            <p className="provider-hint">
              The backend is not reporting the Nebius provider. Set
              AXIOM_REASONING_PROVIDER=nebius in the backend environment for live Nemotron reasoning.
            </p>
          )) : (
            <p className="provider-hint">
              NVIDIA model via Nebius Token Factory. Generates proposals only; does not execute experiments.
            </p>
          )}
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <a className="mobile-brand" href="/#objective-workspace" aria-label="AXIOM home">
            AXIOM<span className="brand-period">.</span>
          </a>
          <div className="breadcrumbs">
            {workspace ? (
              <>
                <span>Workspace</span>
                <span className="breadcrumb-divider">/</span>
                <strong>Research lab</strong>
              </>
            ) : (
              <>
                <a href="/#objective-workspace">Research lab</a>
                <span className="breadcrumb-divider">/</span>
                <strong>AI Research Assistant</strong>
              </>
            )}
          </div>
          <div className="topbar-right">
            <span className="topbar-edition">
              AXIOM / {workspace ? "LAB 01" : "ASSISTANT 02"}
            </span>
            {workspace ? (
              <div className="connection-status">
                <span
                  className={
                    "status-dot " +
                    (connection === "connected"
                      ? "status-online"
                      : connection === "checking"
                        ? "status-checking"
                        : "status-offline")
                  }
                />
                {connection === "connected"
                  ? "API connected"
                  : connection === "checking"
                    ? "Checking API"
                    : "API disconnected"}
              </div>
            ) : (
              <div className="connection-status assistant-status">
                <span className="status-dot" />
                Proposal generation only
              </div>
            )}
            <ThemeToggle />
          </div>
          <nav className="mobile-capability-nav" aria-label="AXIOM capabilities">
            <a href="/#objective-workspace" aria-current={workspace ? "page" : undefined}>Research Workspace</a>
            <a href="/showcase" aria-current={!workspace ? "page" : undefined}>AI Research Assistant</a>
          </nav>
        </header>
        {children}
      </section>
    </div>
  );
}
