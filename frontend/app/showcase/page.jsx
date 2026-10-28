"use client";

import { useState } from "react";

export default function NemotronShowcasePage() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function runShowcase() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/showcase/nemotron", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Showcase request failed.");
      setResult(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Showcase request failed.");
    } finally {
      setBusy(false);
    }
  }

  const fields = [
    ["Hypothesis", "hypothesis"],
    ["Proposed experiment", "experiment"],
    ["Primary metric", "metric"],
    ["Safety boundary", "safety_check"],
    ["Limitation", "limitation"],
  ];

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: "48px 24px", color: "#edf4ec" }}>
      <p style={{ color: "#ccf477", fontFamily: "monospace", letterSpacing: 2 }}>AXIOM / LIVE MODEL SHOWCASE</p>
      <h1 style={{ fontSize: "clamp(32px, 6vw, 52px)", lineHeight: 1.1 }}>A live Nemotron reasoning call.</h1>
      <p style={{ color: "#aab9ab", lineHeight: 1.8, maxWidth: 720 }}>
        This page sends one fixed, bounded request to NVIDIA Nemotron 3 Super through Nebius Token Factory.
        The model proposes an experiment plan; AXIOM does not execute generated code here.
      </p>
      <button
        onClick={runShowcase}
        disabled={busy}
        style={{ marginTop: 16, border: 0, borderRadius: 8, padding: "12px 18px", fontWeight: 700, background: "#ccf477", color: "#152012", cursor: busy ? "wait" : "pointer" }}
      >
        {busy ? "Waiting for Nemotron…" : result ? "Request another response" : "Run live Nemotron request"}
      </button>
      <p style={{ color: "#aab9ab", fontSize: 13, lineHeight: 1.7 }}>
        Requests are rate-limited per server process. The first successful response is cached during the cooldown.
        Never enter secrets on this page.
      </p>
      {error && <p role="alert" style={{ color: "#ffb4a9", border: "1px solid #633d37", borderRadius: 8, padding: 12 }}>{error}</p>}
      {result && (
        <section aria-live="polite" style={{ marginTop: 28, border: "1px solid #344438", borderRadius: 12, padding: 22, background: "#101613" }}>
          <p style={{ color: "#ccf477", fontFamily: "monospace", fontSize: 12 }}>{result.provider} · {result.model}</p>
          <h2 style={{ fontSize: 22 }}>Structured model output</h2>
          {fields.map(([label, key]) => (
            <div key={key} style={{ borderTop: "1px solid #243128", padding: "14px 0" }}>
              <h3 style={{ fontSize: 14, margin: "0 0 6px" }}>{label}</h3>
              <p style={{ color: "#cbd8c9", lineHeight: 1.8, margin: 0, whiteSpace: "pre-wrap" }}>{result.result[key]}</p>
            </div>
          ))}
          <p style={{ borderTop: "1px solid #243128", paddingTop: 14, color: "#ccf477", fontSize: 12 }}>
            Evidence status: {result.evidence_status}
          </p>
          <p style={{ color: "#8e9e90", fontSize: 12 }}>Generated: {new Date(result.generated_at).toLocaleString()}</p>
        </section>
      )}
      <p style={{ marginTop: 32, color: "#8e9e90", fontSize: 12 }}>
        AXIOM research console · Live model showcase only · No benchmark or GPU optimization claim is made.
      </p>
    </main>
  );
}
