"use client";

import { useState } from "react";
import ThemeToggle from "../theme-toggle";
import "./showcase.css";

const FIELDS = [
  ["01 / Hypothesis", "hypothesis"],
  ["02 / Proposed experiment", "experiment"],
  ["03 / Primary metric", "metric"],
  ["04 / Safety boundary", "safety_check"],
  ["05 / Limitation", "limitation"],
];

export default function NemotronShowcasePage() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function runShowcase() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/showcase/nemotron", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || "The model request could not be completed.");
      if (!payload?.result || !payload?.model) throw new Error("The showcase returned an incomplete response.");
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The model request could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="showcase-shell">
      <header className="showcase-topbar">
        <a className="showcase-brand" href="/" aria-label="AXIOM research lab home">
          <span className="showcase-brand-mark" aria-hidden="true">✳</span>
          AXIOM<span className="showcase-brand-dot">.</span>
        </a>
        <div className="showcase-topbar-right">
          <nav aria-label="Research navigation">
            <a href="/#objective-workspace">Research lab</a>
            <span aria-hidden="true">/</span>
            <span aria-current="page">Live model showcase</span>
          </nav>
          <ThemeToggle />
        </div>
      </header>

      <main className="showcase-main">
        <section className="showcase-hero" aria-labelledby="showcase-heading">
          <div className="showcase-hero-copy">
            <p className="showcase-eyebrow"><span className="showcase-status-dot" /> AXIOM / MODEL LAB 02</p>
            <h1 id="showcase-heading">Reasoning, <em>live.</em><br />Evidence, <em>honest.</em></h1>
            <p className="showcase-lede">
              Ask NVIDIA Nemotron 3 Super to design a controlled ML experiment,
              through Nebius Token Factory. Inspect its proposal without confusing
              an AI-generated plan with an executed benchmark.
            </p>
            <button className="showcase-action" type="button" onClick={runShowcase} disabled={busy} aria-busy={busy}>
              {busy ? "Requesting model proposal…" : result ? "Request model proposal again" : "Generate live experiment proposal"}
              <span aria-hidden="true">{busy ? "◌" : "↗"}</span>
            </button>
            <p className="showcase-request-note">
              A real provider request may take several seconds. Responses are cached during
              a five-minute, per-process cooldown; repeat requests may display a cached result.
            </p>
          </div>
          <div className="showcase-diagram" aria-hidden="true">
            <div className="showcase-diagram-ring showcase-diagram-ring-one" />
            <div className="showcase-diagram-ring showcase-diagram-ring-two" />
            <div className="showcase-diagram-ring showcase-diagram-ring-three" />
            <div className="showcase-diagram-center">N<span>3</span></div>
            <span className="showcase-diagram-label showcase-diagram-label-one">OBJECTIVE</span>
            <span className="showcase-diagram-label showcase-diagram-label-two">HYPOTHESIS</span>
            <span className="showcase-diagram-label showcase-diagram-label-three">PLAN / NOT RUN</span>
          </div>
        </section>

        {error && <p className="showcase-error" role="alert">{error}</p>}

        <section className="showcase-results" aria-labelledby="showcase-results-heading">
          <div className="showcase-section-heading">
            <div>
              <p className="showcase-section-kicker">02 / OUTPUT</p>
              <h2 id="showcase-results-heading">Structured reasoning</h2>
            </div>
            <span className="showcase-pill">{result ? (result.cached ? "Cached model output" : "Provider response received") : "Awaiting request"}</span>
          </div>

          {result ? (
            <div className="showcase-output" aria-live="polite">
              <div className="showcase-output-meta">
                <span>{result.provider} / {result.model}</span>
                <span>{result.generated_at ? new Date(result.generated_at).toLocaleString() : "Time unavailable"}</span>
              </div>
              <div className="showcase-field-grid">
                {FIELDS.map(([label, field]) => (
                  <article className="showcase-field" key={field}>
                    <h3>{label}</h3>
                    <p>{result.result[field]}</p>
                  </article>
                ))}
              </div>
              <p className="showcase-evidence" data-testid="showcase-evidence">
                <strong>Evidence status:</strong> {result.evidence_status}
              </p>
            </div>
          ) : (
            <div className="showcase-empty">
              <span aria-hidden="true">✳</span>
              <h3>No model proposal requested yet</h3>
              <p>Run the bounded request above to inspect a hypothesis, experiment plan, metric, safety boundary and limitation.</p>
            </div>
          )}
        </section>

        <section className="showcase-boundary" aria-label="Evidence boundary">
          <span>IMPORTANT DISTINCTION</span>
          <p>This showcase returns a <strong>live LLM-generated proposal</strong>, not executed code,
          real-model inference measurements, TensorRT optimization or GPU benchmark results.
          The separate <a href="/#objective-workspace">research workspace</a> runs a labeled synthetic CPU demonstration.</p>
        </section>
      </main>
      <footer className="showcase-footer"><span>AXIOM / RESEARCH INTELLIGENCE</span><span>QUESTION → HYPOTHESIS → EVIDENCE</span></footer>
    </div>
  );
}
