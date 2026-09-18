"use strict";

function $(id) { return document.getElementById(id); }

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function banner(containerId, message, kind) {
  const el = $(containerId);
  if (!el) return;
  if (!message) { el.innerHTML = ""; return; }
  el.innerHTML = '<div class="banner ' + kind + '">' + escapeHtml(message) + "</div>";
}

// ===== Base URL =====

function getBaseUrl() {
  return (localStorage.getItem("dr_base_url") || "http://127.0.0.1:8000/api").replace(/\/+$/, "");
}

function setBaseUrl(url) {
  localStorage.setItem("dr_base_url", url);
}

// ===== Session =====

function getSession() {
  return { token: localStorage.getItem("dr_token"), username: localStorage.getItem("dr_username") };
}

function setSession(token, username) {
  if (token) {
    localStorage.setItem("dr_token", token);
    localStorage.setItem("dr_username", username);
  } else {
    localStorage.removeItem("dr_token");
    localStorage.removeItem("dr_username");
  }
}

/** Call at the top of a protected page. Bounces to login.html if there's no
 * local session, so an unauthenticated visitor never sees the app shell. */
function requireAuth() {
  const session = getSession();
  if (!session.token || !session.username) {
    window.location.replace("login.html");
    return null;
  }
  return session;
}

/** Call at the top of an auth page (login/register/reset). If a session
 * already looks valid, skip straight to the app instead of asking again. */
function redirectIfAuthed() {
  const session = getSession();
  if (session.token && session.username) {
    window.location.replace("app.html");
    return true;
  }
  return false;
}

/** The local token is present but the API just rejected it (expired/revoked
 * server-side) - clear it and send the person back to a real sign-in page
 * with an explanation, instead of leaving a half-authenticated app on screen. */
function sessionExpired() {
  setSession(null, null);
  window.location.href = "login.html?expired=1";
}

// ===== API request helper =====

async function apiRequest(method, path, { body, auth, form } = {}) {
  const headers = {};
  let fetchBody;

  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    fetchBody = new URLSearchParams(body).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    fetchBody = JSON.stringify(body);
  }

  if (auth) {
    const session = getSession();
    if (!session.token) throw new Error("Not signed in.");
    headers["Authorization"] = "Bearer " + session.token;
  }

  let response;
  try {
    response = await fetch(getBaseUrl() + path, { method, headers, body: fetchBody });
  } catch (networkErr) {
    throw new Error("Could not reach the API at " + getBaseUrl() + ". Is the server running and is the base URL correct?");
  }

  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }

  if (!response.ok) {
    const detail = (data && data.detail) ? data.detail : (typeof data === "string" ? data : "Request failed");
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = response.status;
    throw err;
  }
  return data;
}

// ===== Top bar (present on every page) =====

async function checkHealth() {
  const dot = $("statusDot");
  if (!dot) return;
  try {
    const res = await fetch(getBaseUrl() + "/health");
    dot.className = "status-dot " + (res.ok ? "up" : "down");
  } catch (e) {
    dot.className = "status-dot down";
  }
}

function initTopbar() {
  const input = $("baseUrlInput");
  if (input) {
    input.value = getBaseUrl();
    input.addEventListener("change", () => { setBaseUrl(input.value); checkHealth(); });
  }
  const toggleBtn = $("apiSettingsBtn");
  const panel = $("apiSettingsPanel");
  if (toggleBtn && panel) {
    toggleBtn.addEventListener("click", () => { panel.hidden = !panel.hidden; });
  }
  checkHealth();
  setInterval(checkHealth, 15000);
}
