"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "axiom-theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState("dark");

  useEffect(() => {
    const sync = () => setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark");
    sync();
    const onStorage = (event) => {
      if (event.key === STORAGE_KEY) {
        document.documentElement.dataset.theme = event.newValue === "light" ? "light" : "dark";
        sync();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function toggle() {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    setTheme(next);
    try { window.localStorage.setItem(STORAGE_KEY, next); } catch { /* Storage may be unavailable. */ }
  }

  return (
    <button className="theme-toggle" type="button" role="switch" aria-label="Dark mode" aria-checked={theme === "dark"} onClick={toggle}>
      <span className="theme-toggle-label">{theme === "dark" ? "DARK" : "LIGHT"}</span>
      <span className="theme-toggle-track" aria-hidden="true"><span className="theme-toggle-thumb">{theme === "dark" ? "☾" : "☀"}</span></span>
    </button>
  );
}
