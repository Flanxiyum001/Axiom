"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { deriveProvenance } from "../lib/provenance.mjs";

const DEFAULT_API_URL =
  process.env.NEXT_PUBLIC_AXIOM_API_URL || "http://127.0.0.1:8000";
const EXPECT_DEMO_MODE = process.env.NEXT_PUBLIC_AXIOM_DEMO_MODE === "1";
const DEMO_OBJECTIVE = "Reduce model inference latency by 20%";

function formatDate(value) {
  if (!value) return "Not recorded";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
}

function prettyNumber(value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value !== "number") return String(value);
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

function readable(value) {
  return String(value || "").replaceAll("_", " ");
}

export default function DashboardPage() {
  const [apiDraft, setApiDraft] = useState(DEFAULT_API_URL);
  const [apiBase, setApiBase] = useState(DEFAULT_API_URL);
  const [connection, setConnection] = useState("checking");
  const [provider, setProvider] = useState("unknown");
  const [demoMode, setDemoMode] = useState(EXPECT_DEMO_MODE);
  const [objectives, setObjectives] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [history, setHistory] = useState([]);
  const [lastRun, setLastRun] = useState(null);
  const [description, setDescription] = useState("Reduce model inference latency by 20%");
  const [iterations, setIterations] = useState("1");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const normalizedBase = useMemo(
    () => apiBase.trim().replace(/\/+$/, ""),
    [apiBase]
  );

  const request = useCallback(
    async (path, options = {}) => {
      let response;
      try {
        response = await fetch(normalizedBase + path, {
          ...options,
          headers: {
            ...(options.headers || {}),
            ...(options.body ? { "Content-Type": "application/json" } : {}),
          },
        });
      } catch {
        throw new Error(
          "Cannot reach the AXIOM API at " +
            normalizedBase +
            ". Check that the backend is running and the API URL is correct."
        );
      }

      const raw = await response.text();
      let payload = {};
      if (raw) {
        try {
          payload = JSON.parse(raw);
        } catch {
          payload = { detail: raw };
        }
      }
      if (!response.ok) {
        const detail =
          typeof payload.detail === "string"
            ? payload.detail
            : JSON.stringify(payload.detail || payload);
        throw new Error(detail || "API request failed with status " + response.status);
      }
      return payload;
    },
    [normalizedBase]
  );

  const refreshObjectives = useCallback(async (preferredId) => {
    const data = await request("/objectives");
    const list = Array.isArray(data) ? data : [];
    setObjectives(list);
    setActiveId((current) => {
      if (preferredId && list.some((item) => item.id === preferredId)) return preferredId;
      if (current && list.some((item) => item.id === current)) return current;
      return list.length ? list[0].id : null;
    });
    return list;
  }, [request]);

  const checkConnection = useCallback(async () => {
    setConnection("checking");
    setError("");
    try {
      const health = await request("/health");
      if (EXPECT_DEMO_MODE && health.demo_mode !== true) {
        throw new Error("The configured API is not running the fixed judge demo mode.");
      }
      setProvider(health.provider || "unknown");
      setDemoMode(health.demo_mode === true);
      if (health.demo_mode === true) {
        setDescription(DEMO_OBJECTIVE);
        setIterations("1");
      }
      setConnection("connected");
      try {
        await refreshObjectives();
      } catch (loadError) {
        setError("API is reachable, but objectives could not be loaded: " + loadError.message);
      }
    } catch (connectError) {
      setConnection("disconnected");
      setError(connectError.message);
    }
  }, [refreshObjectives, request]);

  const refreshHistory = useCallback(async (objectiveId) => {
    if (!objectiveId) {
      setHistory([]);
      return [];
    }
    const data = await request("/objectives/" + encodeURIComponent(objectiveId) + "/history");
    const records = Array.isArray(data) ? data : [];
    setHistory(records);
    return records;
  }, [request]);

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (!activeId) {
      setHistory([]);
      return;
    }
    refreshHistory(activeId).catch((loadError) => setError(loadError.message));
  }, [activeId, refreshHistory]);

  const activeObjective = objectives.find((item) => item.id === activeId) || null;
  const selectedRun =
    lastRun && lastRun.objective && lastRun.objective.id === activeId
      ? lastRun
      : history.length
        ? history[history.length - 1]
        : null;
  const evaluation = selectedRun ? selectedRun.evaluation : null;
  const hypothesis = selectedRun ? selectedRun.hypothesis : null;
  const evidence = selectedRun ? selectedRun.evidence : null;
  const metricNames = evaluation
    ? Array.from(
        new Set([
          ...Object.keys(evaluation.baseline_metrics || {}),
          ...Object.keys(evaluation.candidate_metrics || {}),
          ...Object.keys(evaluation.deltas || {}),
        ])
      )
    : [];

  const provenance = useMemo(() => deriveProvenance(selectedRun), [selectedRun]);
  const scriptTargetReached = Boolean(evaluation?.target_met);
  const syntheticInterventionSupported =
    provenance?.interventionStatus === "verified_synthetic" &&
    provenance?.workloadType === "synthetic" &&
    evidence?.hypothesis_supported === true;
  const targetStatus =
    provenance?.interventionStatus === "mismatch"
      ? "Intervention mismatch"
      : syntheticInterventionSupported
        ? "Synthetic script metric target met"
        : "Insufficient evidence for optimization";

  async function handleConnect(event) {
    event.preventDefault();
    setApiBase(apiDraft.trim().replace(/\/+$/, ""));
    setNotice("");
    setLastRun(null);
  }

  async function handleCreate(event) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy("create");
    try {
      const result = await request("/objectives", {
        method: "POST",
        body: JSON.stringify({ description: description.trim() }),
      });
      const objective = result.objective;
      if (!objective || !objective.id) {
        throw new Error("The API did not return a valid objective.");
      }
      setObjectives((current) => [
        objective,
        ...current.filter((item) => item.id !== objective.id),
      ]);
      setActiveId(objective.id);
      setHistory([]);
      setLastRun(null);
      setNotice("Objective created. Review it, then run one research iteration.");
    } catch (createError) {
      setError(createError.message);
    } finally {
      setBusy("");
    }
  }

  async function handleRun(objectiveId) {
    if (!objectiveId) return;
    setError("");
    setNotice("");
    setBusy("run:" + objectiveId);
    setLastRun(null);
    try {
      const result = await request(
        "/objectives/" + encodeURIComponent(objectiveId) + "/run",
        {
          method: "POST",
          body: JSON.stringify({ max_iterations: Number(iterations) }),
        }
      );
      if (!result.summary) {
        throw new Error("The API response did not include a research summary.");
      }
      setLastRun(result.summary);
      await refreshHistory(objectiveId);
      await refreshObjectives(objectiveId);
      setNotice("Research run finished. Inspect the hypothesis and measured evidence below.");
    } catch (runError) {
      setError(runError.message);
    } finally {
      setBusy("");
    }
  }

  const providerIsLive = String(provider).toLowerCase() === "nebius";
  const visualPhase = busy.startsWith("run:") ? "running" : selectedRun ? "complete" : "ready";

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true"><span /></div>
          <div>
            <div className="brand-name">AXIOM<span className="brand-period">.</span></div>
            <div className="brand-subtitle">RESEARCH INTELLIGENCE</div>
          </div>
        </div>

        <div className="sidebar-label">YOUR WORKSPACE</div>
        <div className="nav-item nav-item-active">
          <span className="nav-icon" aria-hidden="true">◫</span>
          Experiments
          <span className="nav-count">{objectives.length}</span>
        </div>
        <div className="sidebar-process">
          <div className="sidebar-label">THE METHOD</div>
          <div><span>01</span> Define the question</div>
          <div><span>02</span> Run the experiment</div>
          <div><span>03</span> Follow the evidence</div>
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-quote">“The answer is only as good as the experiment.”</div>
          <div className="footer-line" />
          <div className="footer-label">REASONING ENGINE</div>
          <div className="provider-line">
            <span className={"provider-dot " + (providerIsLive ? "provider-live" : "")} />
            <span>{provider === "unknown" ? "Not detected" : provider}</span>
          </div>
          {!providerIsLive && !demoMode && (
            <p className="provider-hint">
              The backend is not reporting the Nebius provider. Set
              AXIOM_REASONING_PROVIDER=nebius in the backend environment for live Nemotron reasoning.
            </p>
          )}
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>Research lab</strong>
          </div>
          <div className="topbar-right"><span className="topbar-edition">AXIOM / LAB 01</span><div className="connection-status">
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
          </div></div>
        </header>

        <div className="page-content">
          {demoMode && (
            <div className="demo-banner" role="note" data-testid="demo-banner">
              <strong>Fixed synthetic CPU demo</strong>
              <span>Echo reasoning only. This run times a small, fixed arithmetic task on the demo host. It does not measure model inference, GPU performance, quantization, or multithreading.</span>
            </div>
          )}
          <section className="hero" aria-labelledby="hero-title">
            <div className="hero-content">
              <div className="eyebrow"><span className="eyebrow-line" /> THE AUTONOMOUS RESEARCH LAB <span className="hero-edition">/ 001</span></div>
              <h1 id="hero-title">Make curiosity<br/><em>measurable.</em></h1>
              <p className="hero-copy">
                From a question to a hypothesis, a controlled run, and a conclusion you can actually inspect.
              </p>
              <a className="hero-cta" href="#objective-workspace">Start an experiment <span aria-hidden="true">↗</span></a>
              <p style={{ margin: "14px 0 0", color: "#61736e", fontSize: 12, lineHeight: 1.6 }}>
                Or explore <a href="/showcase" style={{ color: "#b95435", fontWeight: 700, textUnderlineOffset: 3 }}>live Nemotron reasoning ↗</a> — an AI-generated proposal, not an executed benchmark.
              </p>
              <div className="hero-meta">
                <span><strong>01</strong> QUESTION</span><i />
                <span><strong>02</strong> EXPERIMENT</span><i />
                <span><strong>03</strong> EVIDENCE</span>
              </div>
            </div>
            <div className={"hero-visual phase-" + visualPhase} aria-hidden="true">
              <div className="visual-grid" />
              <div className="visual-sweep" />
              <div className="visual-label visual-label-top">FIG. 01 <span>AXIOM / RESEARCH ENGINE</span></div>
              <div className="orbit-ruler" />
              <div className="orbit orbit-outer" />
              <div className="orbit orbit-middle" />
              <div className="orbit orbit-inner" />
              <div className="orbit-scan" />
              <svg className="orbit-route" viewBox="0 0 520 422" preserveAspectRatio="xMidYMid meet" focusable="false">
                <path className="route-underlay" d="M 108 128 C 159 48 335 26 404 132 S 443 338 307 359 S 72 308 108 128 Z" />
                <path className="route-trace" d="M 108 128 C 159 48 335 26 404 132 S 443 338 307 359 S 72 308 108 128 Z" />
              </svg>
              <div className="orbit-tick tick-one" /><div className="orbit-tick tick-two" /><div className="orbit-tick tick-three" />
              <div className="orbit-core">
                <span className="core-cross">✳</span>
                <span>AXIOM</span>
                <small>{visualPhase === "running" ? "RESEARCH IN PROGRESS" : visualPhase === "complete" ? "EVIDENCE RECORDED" : "AWAITING OBJECTIVE"}</small>
              </div>
              <div className="visual-coordinate coordinate-one"><b>01</b><span>QUESTION</span></div>
              <div className="visual-coordinate coordinate-two"><b>02</b><span>EXPERIMENT</span></div>
              <div className="visual-coordinate coordinate-three"><b>03</b><span>EVIDENCE</span></div>
              <div className="visual-label visual-label-bottom"><span>OBSERVE → TEST → LEARN</span><span className="visual-live"><i />{visualPhase === "running" ? "RUNNING" : visualPhase === "complete" ? "RESULT READY" : "SYSTEM READY"}</span></div>
            </div>
          </section>

          <section className="api-panel panel">
            <div className="panel-heading">
              <div>
                <div className="section-kicker">CONNECTION</div>
                <h2>Backend endpoint</h2>
              </div>
              <span className={"pill " + (connection === "connected" ? "pill-success" : "pill-neutral")}>
                {connection === "connected" ? "Reachable" : connection === "checking" ? "Checking" : "Needs attention"}
              </span>
            </div>
            {demoMode ? (
              <p className="field-hint">This demo uses its configured API endpoint: {normalizedBase}</p>
            ) : <form className="api-form" onSubmit={handleConnect}>
              <label className="visually-hidden" htmlFor="api-url">AXIOM API URL</label>
              <input
                id="api-url"
                value={apiDraft}
                onChange={(event) => setApiDraft(event.target.value)}
                placeholder="http://127.0.0.1:8000"
                autoComplete="url"
              />
              <button className="button button-secondary" type="submit" disabled={!apiDraft.trim()}>
                Connect
              </button>
              <button
                className="button button-quiet"
                type="button"
                onClick={checkConnection}
                disabled={connection === "checking"}
              >
                Recheck
              </button>
            </form>}
            {!demoMode && <p className="field-hint">
              Local default: start the API with <code>uvicorn backend.main:app --reload</code>.
              For a deployed frontend, configure AXIOM_CORS_ORIGINS on the backend.
            </p>}
          </section>

          {error && (
            <div className="feedback feedback-error" role="alert">
              <strong>Something needs attention</strong>
              <span>{error}</span>
              {connection !== "connected" && (
                <span className="feedback-help">
                  Confirm the backend is running, then use Connect to retry.
                </span>
              )}
            </div>
          )}
          {notice && <div className="feedback feedback-success" role="status">{notice}</div>}

          <div className="workspace-heading" id="objective-workspace">
            <div><span className="section-kicker">YOUR LAB / 01</span><h2>Experiment workspace<span>.</span></h2></div>
            <p>Define the objective. Inspect every result.</p>
          </div>
          <div className="workspace-grid">
            <section className="panel objective-panel">
              <div className="panel-heading">
                <div>
                  <div className="section-kicker">01 / SET THE INTENT</div>
                  <h2>Research objective</h2>
                </div>
                <span className="step-number">01</span>
              </div>
              <p className="panel-intro">
                {demoMode ? "The public demo accepts this one fixed objective." : "Describe the improvement you want to investigate in plain language."}
              </p>
              <form className="objective-form" onSubmit={handleCreate}>
                <label htmlFor="objective-description">What should AXIOM investigate?</label>
                <textarea
                  id="objective-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  readOnly={demoMode}
                  placeholder="Example: Reduce model inference latency by 20% without lowering accuracy"
                  minLength={3}
                  maxLength={1000}
                  rows={4}
                  required
                />
                <div className="form-footer">
                  <span>{demoMode ? "Fixed demo input" : `${description.length}/1000 characters`}</span>
                  <button className="button button-primary" type="submit" disabled={busy !== "" || connection !== "connected" || description.trim().length < 3}>
                    {busy === "create" ? "Creating…" : "Create objective"}
                    <span aria-hidden="true">↗</span>
                  </button>
                </div>
              </form>

              <div className="separator-label"><span /> EXISTING OBJECTIVES <span /></div>

              <div className="objective-list">
                {objectives.length === 0 ? (
                  <div className="empty-list">
                    <div className="empty-symbol">＋</div>
                    <strong>Your workspace is clear.</strong>
                    <p>Create an objective above to start the first research thread.</p>
                  </div>
                ) : (
                  objectives.map((objective, index) => (
                    <button
                      type="button"
                      key={objective.id}
                      className={"objective-item " + (objective.id === activeId ? "objective-item-active" : "")}
                      onClick={() => {
                        setActiveId(objective.id);
                        setLastRun(null);
                        setError("");
                        setNotice("");
                      }}
                    >
                      <span className="objective-index">{String(index + 1).padStart(2, "0")}</span>
                      <span className="objective-item-copy">
                        <strong>{objective.description}</strong>
                        <span>{readable(objective.metric)} · {readable(objective.direction)}</span>
                      </span>
                      <span className="objective-chevron">↗</span>
                    </button>
                  ))
                )}
              </div>
            </section>

            <section className="panel detail-panel">
              <div className="panel-heading">
                <div>
                  <div className="section-kicker">02 / FOLLOW THE EVIDENCE</div>
                  <h2>Experiment evidence</h2>
                </div>
                <span className="step-number">02</span>
              </div>

              {!activeObjective ? (
                <div className="detail-empty">
                  <div className="orbit-mark"><span /><span /><span /></div>
                  <h3>No objective selected</h3>
                  <p>Create an objective or select one from your workspace to see its research history.</p>
                </div>
              ) : (
                <>
                  <div className="selected-objective">
                    <div className="selected-objective-top">
                      <span className="pill pill-neutral">ACTIVE OBJECTIVE</span>
                      <span className="created-date">{formatDate(activeObjective.created_at)}</span>
                    </div>
                    <h3>{activeObjective.description}</h3>
                    <div className="objective-facts">
                      <div>
                        <span>METRIC</span>
                        <strong>{readable(activeObjective.metric)}</strong>
                      </div>
                      <div>
                        <span>DIRECTION</span>
                        <strong>{readable(activeObjective.direction)}</strong>
                      </div>
                      <div>
                        <span>TARGET</span>
                        <strong>{prettyNumber(activeObjective.target)}%</strong>
                      </div>
                    </div>
                    <div className="run-controls">
                      <label htmlFor="iteration-count">Iterations</label>
                      <select
                        id="iteration-count"
                        value={iterations}
                        onChange={(event) => setIterations(event.target.value)}
                        disabled={busy !== ""}
                      >
                        <option value="1">1 iteration · recommended</option>
                        {!demoMode && <option value="2">2 iterations</option>}
                        {!demoMode && <option value="3">3 iterations</option>}
                      </select>
                      <button
                        className="button button-primary"
                        type="button"
                        onClick={() => handleRun(activeObjective.id)}
                        disabled={busy !== "" || connection !== "connected"}
                      >
                        {busy === "run:" + activeObjective.id ? "Running…" : "Run research"}
                        <span aria-hidden="true">↗</span>
                      </button>
                    </div>
                    {busy === "run:" + activeObjective.id && (
                      <div className="run-activity" role="status">
                        <span className="run-activity-icon" aria-hidden="true" />
                        <span><strong>Research loop underway</strong><small>Preparing a hypothesis, running the experiment, and evaluating evidence.</small></span>
                      </div>
                    )}
                    <p className="field-hint">
                      {demoMode
                        ? "One run per objective. Echo prepares the hypothesis and plan; the fixed CPU adapter measures three baseline and three candidate samples."
                        : "A run calls the configured reasoning provider. Multiple iterations may consume more API quota."}
                    </p>
                  </div>

                  {selectedRun ? (
                    <div className="results-stack">
                      <div className="result-heading">
                        <div>
                          <div className="section-kicker">LATEST RESULT</div>
                          <h3>{scriptTargetReached ? (demoMode ? "Synthetic CPU task target reached" : "Script metric target reached") : "Evidence collected"}</h3>
                        </div>
                        <span className={"pill " + (scriptTargetReached && syntheticInterventionSupported ? "pill-success" : "pill-neutral")}>
                          {scriptTargetReached ? (demoMode ? "Fixed synthetic CPU target met" : targetStatus) : selectedRun.stopped ? readable(selectedRun.stop_reason || "completed") : "Reviewed"}
                        </span>
                      </div>

                      {hypothesis && (
                        <div className="insight-card">
                          <div className="insight-card-head">
                            <span className="insight-number">H</span>
                            <span className="section-kicker">HYPOTHESIS</span>
                          </div>
                          <p className="hypothesis-statement">{hypothesis.statement}</p>
                          {hypothesis.rationale && <p className="hypothesis-rationale">{hypothesis.rationale}</p>}
                        </div>
                      )}

                      {evaluation ? (
                        <div className="metrics-section">
                          <div className="result-heading compact">
                            <div>
                              <div className="section-kicker">MEASURED COMPARISON</div>
                              <h3>Baseline vs candidate</h3>
                            </div>
                            {evaluation.improvement_percent !== null && evaluation.improvement_percent !== undefined && (
                              <span className={"improvement-value " + (evaluation.improvement_percent >= 0 ? "improvement-positive" : "improvement-negative")}>
                                {evaluation.improvement_percent > 0 ? "+" : ""}{prettyNumber(evaluation.improvement_percent)}%
                              </span>
                            )}
                          </div>
                          {metricNames.length ? (
                            <div className="metric-table-wrap">
                              <table className="metric-table">
                                <thead>
                                  <tr><th>METRIC</th><th>BASELINE</th><th>CANDIDATE</th><th>DELTA</th></tr>
                                </thead>
                                <tbody>
                                  {metricNames.map((name) => (
                                    <tr key={name}>
                                      <td>{readable(name)}</td>
                                      <td>{prettyNumber((evaluation.baseline_metrics || {})[name])}</td>
                                      <td>{prettyNumber((evaluation.candidate_metrics || {})[name])}</td>
                                      <td>{prettyNumber((evaluation.deltas || {})[name])}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <p className="field-hint">The evaluator did not return metric values for this run.</p>
                          )}
                        </div>
                      ) : (
                        <div className="detail-empty detail-empty-small">
                          <h3>No completed evaluation yet</h3>
                          <p>The loop did not return an evaluation. Check the run status and backend logs.</p>
                        </div>
                      )}

                      {evidence && (
                        <div className="evidence-card">
                          <div className="section-kicker">ANALYST CONCLUSION</div>
                          <div className="evidence-status">
                            <span className={"status-dot " + (evidence.hypothesis_supported ? "status-online" : "status-offline")} />
                            {evidence.hypothesis_supported ? "Hypothesis supported" : "Hypothesis not supported"}
                            <span className="confidence">Confidence {Math.round((evidence.confidence || 0) * 100)}%</span>
                          </div>
                          <p>{evidence.conclusion}</p>
                          {Array.isArray(evidence.observations) && evidence.observations.length > 0 && (
                            <div className="evidence-list">
                              <strong>Observations</strong>
                              <ul>{evidence.observations.map((item, index) => <li key={index}>{item}</li>)}</ul>
                            </div>
                          )}
                          {Array.isArray(evidence.limitations) && evidence.limitations.length > 0 && (
                            <div className="evidence-list">
                              <strong>Limitations</strong>
                              <ul>{evidence.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul>
                            </div>
                          )}
                        </div>
                      )}
                      {selectedRun && provenance && (
                        <div className="insight-card" data-testid="benchmark-provenance">
                          <div className="insight-card-head">
                            <span className="insight-number">P</span>
                            <span className="section-kicker">BENCHMARK PROVENANCE</span>
                          </div>
                          <details className="provenance-details">
                            <summary><span>Inspect full benchmark trace</span><span>{readable(provenance.workloadType)} · {readable(provenance.interventionStatus)} <span aria-hidden="true">↗</span></span></summary>
                            <div className="provenance-grid">
                            <div className="provenance-row">
                              <span className="provenance-label">Intervention evidence</span>
                              <span className="provenance-value">{provenance.interventionDetail}</span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Workload type</span>
                              <span className="provenance-value">{readable(provenance.workloadType)}</span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Lever tested</span>
                              <span className="provenance-value">{readable(provenance.lever)}</span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Provenance check</span>
                              <span className="provenance-value">
                                {provenance.leverConsistency === "consistent"
                                  ? "Consistent: " + Object.entries(provenance.leverSources).map(([source, lever]) => source + "=" + lever).join(", ")
                                  : provenance.leverConsistency === "mismatch"
                                    ? "Mismatch: " + Object.entries(provenance.leverSources).map(([source, lever]) => source + "=" + lever).join(", ")
                                    : "Insufficient recorded detail to verify"}
                              </span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Planned baseline settings</span>
                              <span className="provenance-value">
                                {Object.keys(provenance.baselineSettings).length
                                  ? JSON.stringify(provenance.baselineSettings)
                                  : "Not recorded in plan"}
                              </span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Planned candidate settings</span>
                              <span className="provenance-value">
                                {Object.keys(provenance.candidateSettings).length
                                  ? JSON.stringify(provenance.candidateSettings)
                                  : "Not recorded in plan"}
                              </span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Spec parameters</span>
                              <span className="provenance-value">{JSON.stringify(provenance.parameters)}</span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Execution environment</span>
                              <span className="provenance-value">{JSON.stringify(provenance.environment)}</span>
                            </div>
                            <div className="provenance-row">
                              <span className="provenance-label">Measurement method</span>
                              <span className="provenance-value">{provenance.measurementMethod}; {provenance.runCount} recorded runs</span>
                            </div>
                            </div>
                          </details>
                        </div>
                      )}

                    </div>
                  ) : (
                    <div className="detail-empty detail-empty-small">
                      <div className="empty-symbol">↳</div>
                      <h3>Ready to investigate</h3>
                      <p>Run the objective to generate a hypothesis, execute the experiment, and inspect the result.</p>
                    </div>
                  )}

                  <div className="history-footer">
                    <div>
                      <div className="section-kicker">PROVENANCE</div>
                      <strong>{history.length} recorded experiment {history.length === 1 ? "iteration" : "iterations"}</strong>
                    </div>
                    <button
                      className="button button-quiet"
                      type="button"
                      onClick={() => refreshHistory(activeId).catch((loadError) => setError(loadError.message))}
                    >
                      Refresh history
                    </button>
                  </div>
                </>
              )}
            </section>
          </div>

          <footer className="page-footer">
            <span>AXIOM / AUTONOMOUS RESEARCH SYSTEM</span>
            <span>Built for traceable experiments, not guesses.</span>
          </footer>
        </div>
      </section>
    </main>
  );
}
