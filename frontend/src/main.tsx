import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowUpRight,
  ArrowLeft,
  Plus,
  Search,
  LayoutDashboard,
  FolderOpen,
  BookOpen,
  Users,
  Activity,
  LogOut,
  Scale,
  ShieldCheck,
  FileText,
  Upload,
  Check,
  X,
  ChevronRight,
  Download,
  AlertTriangle,
  LoaderCircle,
  Trash2,
  RefreshCw,
  Languages,
  LockKeyhole,
  CircleHelp,
} from "lucide-react";
import { api, ApiError, setToken, downloadPdf } from "./api";
import { texts, errorText, type TextKey } from "./i18n";
import type { Lang, User, Case, Doc, Analysis, Citation, Job } from "./types";
import "./style.css";
import { UserChat } from "./UserChat";

type T = (key: TextKey) => string;
function Badge({ status, t }: { status: string; t: T }) {
  return (
    <span className={`badge ${status}`}>
      <i />
      {t((status === "completed" ? "completedStatus" : status) as TextKey) ||
        status}
    </span>
  );
}
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label={
            document.documentElement.lang === "ar" ? "إغلاق" : "Fermer"
          }
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Scale size={25} />
      </span>
      <span>
        Amanah<span className="brand-ar">أمانة</span>
      </span>
    </div>
  );
}
const authAction = new URLSearchParams(location.search).get("action");
const initialLinkToken =
  new URLSearchParams(location.hash.slice(1)).get("token") || "";
if (initialLinkToken) history.replaceState(null, "", location.pathname);

function Auth({
  lang,
  t,
  onLogin,
}: {
  lang: Lang;
  t: T;
  onLogin: (u: User) => void;
}) {
  const [mode, setMode] = useState(
    authAction === "verify"
      ? "verify"
      : authAction === "reset"
        ? "reset"
        : "login",
  );
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      if (mode === "login") {
        const r = await api<{ token: string; user: User }>(
          "/auth/login",
          "POST",
          data,
        );
        setToken(r.token);
        onLogin(r.user);
      } else {
        const route =
          mode === "register"
            ? "register"
            : mode === "verify"
              ? "verify"
              : mode === "reset"
                ? "reset"
                : mode === "resend"
                  ? "resend"
                  : "forgot";
        const r = await api<{ message: string }>("/auth/" + route, "POST", {
          ...data,
          token: initialLinkToken,
        });
        setMessage(t(r.message as TextKey));
        if (mode === "reset" || mode === "verify") setMode("login");
      }
    } catch (e) {
      setError(
        errorText(e instanceof ApiError ? e.code : "server_error", lang),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <section className="auth-story">
        <Brand />
        <div>
          <span className="eyebrow light">{t("jurisdiction")}</span>
          <h1>{t("authIntro")}</h1>
          <p>{t("authText")}</p>
          <div className="document-art" aria-hidden="true">
            <div className="art-page">
              <Scale size={36} />
              <span />
              <span />
              <span />
              <div>
                <Check size={14} /> <b>Conformité · الامتثال</b>
              </div>
              <span />
              <span />
            </div>
            <div className="art-seal">
              <ShieldCheck size={32} />
            </div>
          </div>
        </div>
        <small>CONFIDENTIALITÉ · TRAÇABILITÉ · وضوح</small>
      </section>
      <section className="auth-form">
        <span className="eyebrow">{t("tagline")}</span>
        <h2>
          {t(
            mode === "login"
              ? "login"
              : mode === "register"
                ? "register"
                : mode === "verify"
                  ? "verify"
                  : "reset",
          )}
        </h2>
        {message && (
          <div className="success" role="status">
            <Check size={18} />
            {message}
          </div>
        )}
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <form onSubmit={submit}>
          {mode === "register" && (
            <Field label={t("fullName")}>
              <input name="name" required maxLength={120} autoComplete="name" />
            </Field>
          )}
          {!["verify", "reset"].includes(mode) && (
            <Field label={t("email")}>
              <input
                type="email"
                name="email"
                required
                autoComplete="email"
                dir="ltr"
              />
            </Field>
          )}
          {["login", "register", "reset"].includes(mode) && (
            <Field label={t("password")}>
              <input
                type="password"
                name="password"
                required
                minLength={mode === "login" ? 1 : 12}
                maxLength={256}
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />
              {mode !== "login" && <small>{t("passwordHelp")}</small>}
            </Field>
          )}
          <button className="button primary full" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={18} /> : null}
            {t(
              mode === "login"
                ? "login"
                : mode === "register"
                  ? "register"
                  : mode === "verify"
                    ? "verify"
                    : mode === "reset"
                      ? "save"
                      : "send",
            )}
            <ArrowUpRight size={18} />
          </button>
        </form>
        <div className="auth-links">
          <button
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
          >
            {t(mode === "login" ? "register" : "login")}
          </button>
          {mode === "login" && (
            <>
              <button onClick={() => setMode("forgot")}>{t("forgot")}</button>
              <button onClick={() => setMode("resend")}>{t("resend")}</button>
            </>
          )}
        </div>
        <div className="confidential">
          <LockKeyhole size={16} />
          {t("privacyText")}
        </div>
      </section>
    </div>
  );
}

function App() {
  const [lang, setLang] = useState<Lang>(() =>
    localStorage.getItem("amanah_lang") === "ar" ? "ar" : "fr",
  );
  const t: T = (k) => texts[lang][k];
  const [user, setUser] = useState<User | null>(null),
    [boot, setBoot] = useState(true),
    [nav, setNav] = useState("dashboard");
  const [cases, setCases] = useState<Case[]>([]),
    [usage, setUsage] = useState({ today: 0, limit: 5 }),
    [ai, setAi] = useState(false),
    [selected, setSelected] = useState<Case | null>(null),
    [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [references, setReferences] = useState<Doc[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [jobs, setJobs] = useState<Job[]>([]);
  const [modal, setModal] = useState(""),
    [preview, setPreview] = useState<Doc | null>(null),
    [passage, setPassage] = useState<{
      text: string;
      location: string;
      document_name: string;
    } | null>(null),
    [reviewed, setReviewed] = useState(false),
    [replacement, setReplacement] = useState("");
  const [search, setSearch] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [reportTab, setReportTab] = useState("requirements");
  const selectedId = selected?.id,
    analysisId = analysis?.id;
  const activeIds = useRef({ selectedId, analysisId });
  activeIds.current = { selectedId, analysisId };
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("amanah_lang", lang);
  }, [lang]);
  useEffect(() => {
    api<{ user: User }>("/auth/me")
      .then((r) => setUser(r.user))
      .catch(() => setToken(""))
      .finally(() => setBoot(false));
  }, []);
  const refresh = useCallback(async () => {
    if (!user || user.role !== "admin") return;
    const r = await api<{
      cases: Case[];
      usage: { today: number; limit: number };
      ai_configured: boolean;
    }>("/cases");
    setCases(r.cases);
    setUsage(r.usage);
    setAi(r.ai_configured);
    if (selectedId) {
      try {
        const r = await api<Case>("/cases/" + selectedId);
        if (activeIds.current.selectedId === selectedId) setSelected(r);
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 404)) throw e;
      }
    }
    if (analysisId) {
      try {
        const r = await api<{ analysis: Analysis }>("/analyses/" + analysisId);
        if (activeIds.current.analysisId === analysisId)
          setAnalysis(r.analysis);
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 404)) throw e;
      }
    }
    if (user.role === "admin") {
      if (nav === "references") {
        const r = await api<{ documents: Doc[] }>("/admin/references");
        setReferences(r.documents);
      }
      if (nav === "users") {
        const r = await api<{ users: User[] }>("/admin/users");
        setUsers(r.users);
      }
      if (nav === "jobs") {
        const r = await api<{ jobs: Job[] }>("/admin/jobs");
        setJobs(r.jobs);
      }
    }
  }, [user, selectedId, analysisId, nav]);
  const handleError = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      setUser(null);
      setToken("");
    }
    setError(e instanceof ApiError ? e.code : "server_error");
  }, []);
  useEffect(() => {
    refresh().catch(handleError);
  }, [refresh, handleError]);
  useEffect(() => {
    if (!user || user.role !== "admin") return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") refresh().catch(handleError);
    }, 5000);
    return () => clearInterval(timer);
  }, [user, refresh, handleError]);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      handleError(e);
    } finally {
      setBusy(false);
    }
  }
  function go(value: string) {
    setNav(value);
    setSelected(null);
    setAnalysis(null);
    setError("");
    setSearch("");
  }
  async function openCase(id: string) {
    await run(async () => {
      setSelected(await api<Case>("/cases/" + id));
      setAnalysis(null);
      setNav("cases");
    });
  }
  async function openReport(id: string) {
    await run(async () => {
      const r = await api<{ analysis: Analysis }>("/analyses/" + id);
      setAnalysis(r.analysis);
      setReportTab("requirements");
    });
  }
  const status = (c: Case) => c.latest_analysis?.status || "draft";
  const filtered = cases.filter((c) =>
    (c.title + " " + c.description)
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const menu = [
    { id: "dashboard", label: "dashboard", icon: LayoutDashboard },
    { id: "cases", label: "cases", icon: FolderOpen },
  ];
  const adminMenu = [
    { id: "references", label: "references", icon: BookOpen },
    { id: "users", label: "users", icon: Users },
    { id: "jobs", label: "jobs", icon: Activity },
  ];
  const analysisBusy = selected?.analyses?.some((a) =>
    ["running", "queued"].includes(a.status),
  );
  const canAnalyze =
    !!selected?.documents?.length &&
    selected.documents.every((d) => d.status === "ready") &&
    ["offer", "tender"].every((kind) =>
      selected.documents!.some((d) => d.kind === kind),
    );
  async function showDoc(id: string) {
    await run(async () => {
      const r = await api<{ document: Doc }>("/documents/" + id);
      setPreview(r.document);
      setReviewed(false);
      setReplacement("");
      setModal("review");
    });
  }
  async function cite(c: Citation) {
    if (!analysis) return;
    await run(async () => {
      const r = await api<{
        passage: { text: string; location: string; document_name: string };
      }>(
        `/analyses/${analysis.id}/passages/${encodeURIComponent(c.passage_id)}`,
      );
      setPassage(r.passage);
      setModal("citation");
    });
  }
  function CitationButton({ c }: { c: Citation }) {
    return (
      <button className="citation" onClick={() => cite(c)}>
        <BookOpen size={13} />
        <span>
          {c.document_name} · {c.location}
        </span>
        <ArrowUpRight size={13} />
      </button>
    );
  }
  function CaseList() {
    return (
      <div className="case-list">
        {filtered.map((c) => (
          <button
            className="case-row"
            key={c.id}
            onClick={() => openCase(c.id)}
          >
            <span className="file-icon">
              <FolderOpen size={23} />
            </span>
            <span className="case-row-name">
              <strong>{c.title}</strong>
              <small>
                {new Date(c.created_at).toLocaleDateString(
                  lang === "ar" ? "ar-MR" : "fr-FR",
                )}{" "}
                · {c.document_count} {t("documents").toLowerCase()}
              </small>
            </span>
            <Badge status={status(c)} t={t} />
            <ChevronRight size={19} className="directional" />
          </button>
        ))}
        {!filtered.length && (
          <div className="empty">
            <FolderOpen size={34} />
            <h3>{t(cases.length ? "empty" : "noCases")}</h3>
            <p>{!cases.length && t("noCasesText")}</p>
            <button
              className="button primary"
              onClick={() => setModal("create")}
            >
              <Plus size={17} />
              {t("newCase")}
            </button>
          </div>
        )}
      </div>
    );
  }
  if (boot)
    return (
      <div className="boot">
        <Brand />
        <LoaderCircle className="spin" />
      </div>
    );
  if (user?.role === "user")
    return (
      <UserChat
        user={user}
        lang={lang}
        onLanguage={() => setLang(lang === "fr" ? "ar" : "fr")}
        onLogout={() => {
          setToken("");
          setUser(null);
          setError("");
        }}
      />
    );
  return (
    <>
      <button
        className="language-toggle"
        onClick={() => setLang(lang === "fr" ? "ar" : "fr")}
      >
        <Languages size={17} />
        {lang === "fr" ? "العربية" : "Français"}
      </button>
      {!user ? (
        <Auth
          lang={lang}
          t={t}
          onLogin={(u) => {
            setSelected(null);
            setAnalysis(null);
            setCases([]);
            setUser(u);
            setError("");
            setNav("dashboard");
          }}
        />
      ) : (
        <div className="app-shell">
          <aside className="sidebar">
            <Brand />
            <div className="sidebar-content">
              <span className="nav-label">{t("workspace")}</span>
              <nav>
                {menu.map((m) => (
                  <button
                    key={m.id}
                    className={nav === m.id ? "active" : ""}
                    onClick={() => go(m.id)}
                  >
                    <m.icon size={19} />
                    {t(m.label as TextKey)}
                    {m.id === "cases" && (
                      <span className="nav-count">{cases.length}</span>
                    )}
                  </button>
                ))}
              </nav>
              {user.role === "admin" && (
                <>
                  <span className="nav-label admin-label">{t("admin")}</span>
                  <nav>
                    {adminMenu.map((m) => (
                      <button
                        key={m.id}
                        className={nav === m.id ? "active" : ""}
                        onClick={() => go(m.id)}
                      >
                        <m.icon size={19} />
                        {t(m.label as TextKey)}
                      </button>
                    ))}
                  </nav>
                </>
              )}
              <div className="sidebar-help">
                <ShieldCheck size={24} />
                <strong>{t("privacy")}</strong>
                <p>{t("privacyText")}</p>
              </div>
            </div>
            <div className="profile">
              <span className="avatar">
                {user.name.slice(0, 2).toUpperCase()}
              </span>
              <div>
                <strong>{user.name}</strong>
                <small>{user.email}</small>
              </div>
              <button
                className="icon-button"
                aria-label={t("logout")}
                onClick={() =>
                  run(async () => {
                    await api("/auth/logout", "POST");
                    setToken("");
                    setUser(null);
                    setSelected(null);
                    setAnalysis(null);
                  })
                }
              >
                <LogOut size={18} />
              </button>
            </div>
          </aside>
          <div className="main-shell">
            <header className="topbar">
              <span>{t("jurisdiction")}</span>
              <span className="topbar-private">
                <LockKeyhole size={13} />
                {t("privacy")}
              </span>
              <button
                className="mobile-logout icon-button"
                aria-label={t("logout")}
                onClick={() =>
                  run(async () => {
                    await api("/auth/logout", "POST");
                    setToken("");
                    setUser(null);
                  })
                }
              >
                <LogOut size={17} />
              </button>
            </header>
            <main>
              {error && (
                <div className="error banner" role="alert">
                  <AlertTriangle size={18} />
                  <span>{errorText(error, lang)}</span>
                  <button
                    className="icon-button"
                    onClick={() => setError("")}
                    aria-label={t("close")}
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
              {success && (
                <div className="success" role="status">
                  {success}
                </div>
              )}
              {!selected && ["dashboard", "cases"].includes(nav) && (
                <>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">{t("hello")}</span>
                      <h1>{nav === "dashboard" ? t("welcome") : t("cases")}</h1>
                      <p>{t("intro")}</p>
                    </div>
                    <button
                      className="button primary"
                      onClick={() => setModal("create")}
                    >
                      <Plus size={18} />
                      {t("newCase")}
                    </button>
                  </div>
                  {nav === "dashboard" && (
                    <>
                      <section className="process-card">
                        <div className="process-title">
                          <Scale size={28} />
                          <div>
                            <h2>{t("method")}</h2>
                            <p>{t("methodText")}</p>
                          </div>
                        </div>
                        <div className="process-steps">
                          {[
                            { icon: Upload, key: "tender" },
                            { icon: FileText, key: "offer" },
                            { icon: ShieldCheck, key: "summary" },
                          ].map((step, i) => (
                            <React.Fragment key={step.key}>
                              <div>
                                <span className="step-icon">
                                  <step.icon size={20} />
                                </span>
                                <span>{t(step.key as TextKey)}</span>
                              </div>
                              {i < 2 && (
                                <ChevronRight
                                  size={15}
                                  className="step-chevron directional"
                                />
                              )}
                            </React.Fragment>
                          ))}
                        </div>
                        <div className="process-watermark" aria-hidden="true">
                          §
                        </div>
                      </section>
                      <div className="stats">
                        <div>
                          <span>{t("caseCount")}</span>
                          <strong>
                            {cases.length.toString().padStart(2, "0")}
                          </strong>
                          <FolderOpen size={20} />
                        </div>
                        <div>
                          <span>{t("completed")}</span>
                          <strong>
                            {cases
                              .filter(
                                (c) =>
                                  c.latest_analysis?.status === "completed",
                              )
                              .length.toString()
                              .padStart(2, "0")}
                          </strong>
                          <ShieldCheck size={20} />
                        </div>
                        <div>
                          <span>{t("inProgress")}</span>
                          <strong>
                            {cases
                              .filter((c) =>
                                ["queued", "running"].includes(
                                  c.latest_analysis?.status || "",
                                ),
                              )
                              .length.toString()
                              .padStart(2, "0")}
                          </strong>
                          <Activity size={20} />
                        </div>
                        <div>
                          <span>{t("quota")}</span>
                          <strong>
                            {usage.today}
                            <small> / {usage.limit}</small>
                          </strong>
                          <span className="usage-line">
                            <i
                              style={{
                                width: `${Math.min(100, (usage.today / usage.limit) * 100)}%`,
                              }}
                            />
                          </span>
                        </div>
                      </div>
                    </>
                  )}
                  <section className="panel">
                    <div className="panel-heading">
                      <h2>{t(nav === "dashboard" ? "recent" : "allCases")}</h2>
                      <label className="search">
                        <Search size={17} />
                        <input
                          aria-label={t("search")}
                          placeholder={t("search")}
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </label>
                    </div>
                    <CaseList />
                  </section>
                  <div className="notice">
                    <CircleHelp size={21} />
                    <div>
                      <strong>{t("notice")}</strong>
                      <p>{t("noticeText")}</p>
                    </div>
                  </div>
                </>
              )}
              {selected && !analysis && (
                <>
                  <button
                    className="text-button back"
                    onClick={() => {
                      setSelected(null);
                      setAnalysis(null);
                    }}
                  >
                    <ArrowLeft size={16} className="directional" />
                    {t("back")}
                  </button>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">
                        {t("cases")} · {t(selected.language)}
                      </span>
                      <h1>{selected.title}</h1>
                      <p>{selected.description}</p>
                    </div>
                    <button
                      className="icon-button danger"
                      aria-label={t("delete")}
                      disabled={busy || analysisBusy}
                      onClick={() => setModal("delete-case")}
                    >
                      <Trash2 size={19} />
                    </button>
                  </div>
                  <div className="case-workspace">
                    <section className="panel">
                      <div className="panel-heading">
                        <h2>{t("documents")}</h2>
                      </div>
                      {(["tender", "offer"] as const).map((kind) => (
                        <div className="document-group" key={kind}>
                          <h3>
                            <FileText size={17} />
                            {t(kind)}
                          </h3>
                          {selected.documents
                            ?.filter((d) => d.kind === kind)
                            .map((d) => (
                              <div className="document-row" key={d.id}>
                                <button
                                  className="document-name"
                                  onClick={() => showDoc(d.id)}
                                >
                                  {d.name}
                                  <small>
                                    {d.page_count > 0
                                      ? `${d.name.toLowerCase().endsWith(".docx") ? "≈ " : ""}${d.page_count} ${t("pages")}`
                                      : ""}
                                  </small>
                                </button>
                                <Badge status={d.status} t={t} />
                                {d.status === "failed" && (
                                  <button
                                    className="icon-button"
                                    aria-label={t("retry")}
                                    disabled={busy || analysisBusy}
                                    onClick={() =>
                                      run(async () => {
                                        await api(
                                          "/documents/" + d.id + "/retry",
                                          "POST",
                                        );
                                      })
                                    }
                                  >
                                    <RefreshCw size={16} />
                                  </button>
                                )}
                                <button
                                  className="icon-button danger"
                                  aria-label={t("delete")}
                                  disabled={busy || analysisBusy}
                                  onClick={() => {
                                    setPreview(d);
                                    setModal("delete-document");
                                  }}
                                >
                                  <X size={16} />
                                </button>
                                {d.error && (
                                  <p className="inline-error">
                                    {errorText(d.error, lang)}
                                  </p>
                                )}
                              </div>
                            ))}
                          <label
                            className={`upload-zone ${analysisBusy ? "disabled" : ""}`}
                          >
                            <Upload size={22} />
                            <strong>
                              {busy ? t("uploadBusy") : t("upload")}
                            </strong>
                            <small>{t("fileHelp")}</small>
                            <input
                              type="file"
                              aria-label={`${t("upload")} — ${t(kind)}`}
                              accept=".pdf,.docx"
                              disabled={busy || analysisBusy}
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (!file) return;
                                const data = new FormData();
                                data.set("file", file);
                                data.set("kind", kind);
                                e.target.value = "";
                                run(async () => {
                                  await api(
                                    "/cases/" + selected.id + "/documents",
                                    "POST",
                                    data,
                                  );
                                });
                              }}
                            />
                          </label>
                        </div>
                      ))}
                    </section>
                    <aside className="analysis-sidebar">
                      <section className="panel analysis-launch">
                        <span className="launch-icon">
                          <Scale size={27} />
                        </span>
                        <h2>{t("summary")}</h2>
                        <p>{t("analysisHelp")}</p>
                        <button
                          className="button primary full"
                          disabled={
                            busy ||
                            analysisBusy ||
                            !canAnalyze ||
                            !ai ||
                            usage.today >= usage.limit
                          }
                          onClick={() =>
                            run(async () => {
                              const r = await api<{ analysis: Analysis }>(
                                "/cases/" + selected.id + "/analyses",
                                "POST",
                              );
                              setAnalysis(r.analysis);
                            })
                          }
                        >
                          {analysisBusy ? (
                            <LoaderCircle className="spin" size={17} />
                          ) : (
                            <ArrowUpRight size={18} />
                          )}{" "}
                          {t("start")}
                        </button>
                        {!ai && (
                          <p className="configuration-note">
                            {t("aiUnavailable")}
                          </p>
                        )}
                        <small>
                          {t("quota")} : {usage.today}/{usage.limit}
                        </small>
                      </section>
                      <section className="panel history">
                        <h2>{t("history")}</h2>
                        {selected.analyses?.length ? (
                          selected.analyses.map((a) => (
                            <button key={a.id} onClick={() => openReport(a.id)}>
                              <span>
                                {t("version")} {a.version}
                                <small>
                                  {new Date(a.created_at).toLocaleDateString(
                                    lang,
                                  )}
                                </small>
                              </span>
                              <Badge status={a.status} t={t} />
                            </button>
                          ))
                        ) : (
                          <p>{t("noAnalysis")}</p>
                        )}
                      </section>
                    </aside>
                  </div>
                  <div className="notice">
                    <ShieldCheck size={21} />
                    <p>{t("noticeText")}</p>
                  </div>
                </>
              )}
              {selected && analysis && (
                <>
                  <button
                    className="text-button back"
                    onClick={() => setAnalysis(null)}
                  >
                    <ArrowLeft size={16} className="directional" />
                    {selected.title}
                  </button>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">
                        {t("version")} {analysis.version} · {selected.title}
                      </span>
                      <h1>{t("summary")}</h1>
                    </div>
                    {analysis.status === "completed" && (
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() => run(() => downloadPdf(analysis.id))}
                      >
                        <Download size={17} />
                        {t("export")}
                      </button>
                    )}
                  </div>
                  {analysis.status !== "completed" ? (
                    <section className="panel processing">
                      <span
                        className={`processing-icon ${analysis.status === "failed" ? "failed" : ""}`}
                      >
                        {analysis.status === "failed" ? (
                          <AlertTriangle size={32} />
                        ) : (
                          <LoaderCircle size={32} className="spin" />
                        )}
                      </span>
                      <h2>{t(analysis.status as TextKey)}</h2>
                      {analysis.error && (
                        <p>{errorText(analysis.error, lang)}</p>
                      )}
                      <progress
                        max={100}
                        value={analysis.progress}
                        aria-label={t("progress")}
                      />
                      {analysis.status === "failed" &&
                        analysis.attempts < 3 && (
                          <button
                            className="button primary"
                            disabled={busy}
                            onClick={() =>
                              run(async () => {
                                await api(
                                  "/analyses/" + analysis.id + "/retry",
                                  "POST",
                                );
                              })
                            }
                          >
                            <RefreshCw size={17} />
                            {t("retry")}
                          </button>
                        )}
                    </section>
                  ) : (
                    analysis.report && (
                      <div
                        dir={analysis.report.language === "ar" ? "rtl" : "ltr"}
                        lang={analysis.report.language}
                      >
                        <section className="report-summary">
                          <ShieldCheck size={27} />
                          <p>{analysis.report.summary}</p>
                        </section>
                        <div className="report-tabs" role="tablist">
                          {["requirements", "missing", "risks", "sources"].map(
                            (tab) => (
                              <button
                                key={tab}
                                role="tab"
                                aria-selected={reportTab === tab}
                                onClick={() => setReportTab(tab)}
                              >
                                {t(tab as TextKey)}
                              </button>
                            ),
                          )}
                        </div>
                        {reportTab === "requirements" &&
                          analysis.report.findings.map((f, i) => (
                            <article
                              className="panel finding"
                              key={f.requirement_id}
                            >
                              <div className="finding-top">
                                <span className="requirement-number">
                                  {String(i + 1).padStart(2, "0")}
                                </span>
                                <h3>{f.title}</h3>
                                <Badge status={f.status} t={t} />
                              </div>
                              <p>{f.explanation}</p>
                              <div className="citations">
                                <CitationButton c={f.tender_citation} />
                                {f.citations
                                  .filter(
                                    (c) =>
                                      c.passage_id !==
                                        f.tender_citation.passage_id ||
                                      c.quote !== f.tender_citation.quote,
                                  )
                                  .map((c, i) => (
                                    <CitationButton key={i} c={c} />
                                  ))}
                              </div>
                              {f.correction && (
                                <div className="correction">
                                  <Check size={16} />
                                  <div>
                                    <strong>{t("correction")}</strong>
                                    <p>{f.correction}</p>
                                  </div>
                                </div>
                              )}
                            </article>
                          ))}
                        {reportTab === "missing" && (
                          <section className="panel report-section">
                            <h2>{t("missing")}</h2>
                            {analysis.report.findings.flatMap((f) => f.missing)
                              .length ? (
                              <ul>
                                {analysis.report.findings
                                  .flatMap((f) => f.missing)
                                  .map((item, i) => (
                                    <li key={i}>{item}</li>
                                  ))}
                              </ul>
                            ) : (
                              <p>{t("noMissing")}</p>
                            )}
                          </section>
                        )}
                        {reportTab === "risks" &&
                          [...analysis.report.findings]
                            .sort(
                              (a, b) =>
                                ["high", "medium", "low"].indexOf(a.severity) -
                                ["high", "medium", "low"].indexOf(b.severity),
                            )
                            .map((f) => (
                              <article
                                className="panel finding"
                                key={f.requirement_id}
                              >
                                <Badge status={f.severity} t={t} />
                                <h3>{f.title}</h3>
                                <p>{f.explanation}</p>
                                <div className="correction">
                                  <strong>{t("correction")}</strong>
                                  <p>{f.correction}</p>
                                </div>
                              </article>
                            ))}
                        {reportTab === "sources" && (
                          <section className="panel report-section">
                            <h2>{t("references")}</h2>
                            {analysis.report.references.length ? (
                              analysis.report.references.map((r) => (
                                <div className="reference-info" key={r.id}>
                                  <strong>{r.title}</strong>
                                  <p>
                                    {r.authority} · {r.date} · {r.version}
                                  </p>
                                  <small>{r.applicability}</small>
                                </div>
                              ))
                            ) : (
                              <p>{t("noSources")}</p>
                            )}
                            <h2>{t("limitations")}</h2>
                            <ul>
                              {analysis.report.limitations.map((l, i) => (
                                <li key={i}>{l}</li>
                              ))}
                            </ul>
                          </section>
                        )}
                        <div className="notice">
                          <CircleHelp size={20} />
                          <p>{t("noticeText")}</p>
                        </div>
                      </div>
                    )
                  )}
                </>
              )}
              {nav === "references" && !selected && (
                <>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">{t("admin")}</span>
                      <h1>{t("references")}</h1>
                      <p>{t("refIntro")}</p>
                    </div>
                    <button
                      className="button primary"
                      onClick={() => setModal("reference")}
                    >
                      <Plus size={18} />
                      {t("uploadRef")}
                    </button>
                  </div>
                  <div className="reference-grid">
                    {references.map((d) => (
                      <article className="panel reference-card" key={d.id}>
                        <div className="reference-top">
                          <BookOpen size={23} />
                          <Badge status={d.metadata.publication} t={t} />
                        </div>
                        <h2>{d.metadata.title}</h2>
                        <p>{d.metadata.authority}</p>
                        <small>
                          {d.metadata.date} · {d.metadata.version} ·{" "}
                          {t(d.metadata.language as TextKey)}
                        </small>
                        <p className="applicability">
                          {d.metadata.applicability}
                        </p>
                        <Badge status={d.status} t={t} />
                        {d.error && (
                          <p className="inline-error">
                            {errorText(d.error, lang)}
                          </p>
                        )}
                        <div className="card-actions">
                          <button
                            className="text-button"
                            onClick={() => showDoc(d.id)}
                          >
                            {t("review")}
                            <ArrowUpRight size={15} />
                          </button>
                          {d.metadata.publication === "published" && (
                            <button
                              className="text-button"
                              disabled={busy}
                              onClick={() =>
                                run(async () => {
                                  await api(
                                    "/admin/references/" + d.id,
                                    "PATCH",
                                    { publication: "archived" },
                                  );
                                })
                              }
                            >
                              {t("archive")}
                            </button>
                          )}
                        </div>
                      </article>
                    ))}
                  </div>
                  {!references.length && (
                    <section className="panel empty">
                      <BookOpen size={35} />
                      <h3>{t("noReferences")}</h3>
                    </section>
                  )}
                </>
              )}
              {nav === "users" && (
                <>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">{t("admin")}</span>
                      <h1>{t("users")}</h1>
                    </div>
                  </div>
                  <section className="panel">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>{t("name")}</th>
                            <th>{t("email")}</th>
                            <th>{t("consumption")}</th>
                            <th>{t("active")}</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {users.map((u) => (
                            <tr key={u.id}>
                              <td>
                                <strong>{u.name}</strong>
                                <small>
                                  {u.role === "admin"
                                    ? t("admin")
                                    : u.verified
                                      ? t("verifiedLabel")
                                      : t("unverified")}
                                </small>
                              </td>
                              <td dir="ltr">{u.email}</td>
                              <td>{u.analysis_count}</td>
                              <td>
                                <Badge
                                  status={u.suspended ? "suspended" : "active"}
                                  t={t}
                                />
                              </td>
                              <td>
                                {u.role !== "admin" && (
                                  <button
                                    className="button secondary small"
                                    disabled={busy}
                                    onClick={() =>
                                      run(async () => {
                                        await api(
                                          "/admin/users/" + u.id,
                                          "PATCH",
                                          { suspended: !u.suspended },
                                        );
                                      })
                                    }
                                  >
                                    {t(u.suspended ? "activate" : "suspend")}
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}
              {nav === "jobs" && (
                <>
                  <div className="page-heading">
                    <div>
                      <span className="eyebrow">{t("admin")}</span>
                      <h1>{t("jobs")}</h1>
                      <p>{t("jobIntro")}</p>
                    </div>
                  </div>
                  <section className="panel">
                    {jobs.length ? (
                      jobs.map((j) => (
                        <div className="job-row" key={j.id}>
                          <Activity size={19} />
                          <div>
                            <strong>
                              {j.type === "analysis"
                                ? t("summary")
                                : t("documents")}
                            </strong>
                            <small>{j.id.slice(0, 8)}</small>
                            {j.error && <p>{errorText(j.error, lang)}</p>}
                          </div>
                          <Badge status={j.status} t={t} />
                          {j.status === "failed" && (
                            <button
                              className="button secondary small"
                              disabled={busy}
                              onClick={() =>
                                run(async () => {
                                  await api(
                                    `/admin/jobs/${j.type}/${j.id}/retry`,
                                    "POST",
                                  );
                                })
                              }
                            >
                              {t("retry")}
                            </button>
                          )}
                        </div>
                      ))
                    ) : (
                      <div className="empty">
                        <Check size={30} />
                        <p>{t("noJobs")}</p>
                      </div>
                    )}
                  </section>
                </>
              )}
              <footer>
                <span>AMANAH · أمانة</span>
                <span>{t("tagline")}</span>
              </footer>
            </main>
          </div>
        </div>
      )}
      {modal && (
        <Modal
          title={t(
            modal === "create"
              ? "newCase"
              : modal === "reference"
                ? "uploadRef"
                : modal === "citation"
                  ? "source"
                  : modal.startsWith("delete")
                    ? "delete"
                    : "review",
          )}
          onClose={() => {
            if (!busy) setModal("");
          }}
        >
          {error && (
            <div className="error" role="alert">
              {errorText(error, lang)}
            </div>
          )}
          {modal === "create" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(e.currentTarget));
                run(async () => {
                  const r = await api<{ id: string }>("/cases", "POST", data);
                  setSelected(await api<Case>("/cases/" + r.id));
                  setNav("cases");
                  setModal("");
                });
              }}
            >
              <Field label={t("title")}>
                <input name="title" required maxLength={180} autoFocus />
              </Field>
              <Field label={t("description")}>
                <textarea name="description" rows={3} maxLength={3000} />
              </Field>
              <Field label={t("language")}>
                <select name="language" defaultValue={lang}>
                  <option value="fr">Français</option>
                  <option value="ar">العربية</option>
                </select>
              </Field>
              <div className="modal-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setModal("")}
                >
                  {t("cancel")}
                </button>
                <button className="button primary" disabled={busy}>
                  {t("create")}
                  <Plus size={17} />
                </button>
              </div>
            </form>
          )}
          {modal === "reference" && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                run(async () => {
                  await api("/admin/references", "POST", form);
                  setModal("");
                });
              }}
            >
              <div className="form-grid">
                <Field label={t("refTitle")}>
                  <input name="title" required maxLength={180} />
                </Field>
                <Field label={t("authority")}>
                  <input name="authority" required maxLength={180} />
                </Field>
                <Field label={t("date")}>
                  <input type="date" name="date" required />
                </Field>
                <Field label={t("refVersion")}>
                  <input name="version" required maxLength={60} />
                </Field>
              </div>
              <Field label={t("language")}>
                <select name="language" defaultValue={lang}>
                  <option value="fr">Français</option>
                  <option value="ar">العربية</option>
                </select>
              </Field>
              <Field label={t("applicability")}>
                <textarea
                  name="applicability"
                  required
                  maxLength={1000}
                  rows={3}
                />
              </Field>
              <Field label={t("documents")}>
                <input type="file" name="file" accept=".pdf,.docx" required />
                <small>{t("fileHelp")}</small>
              </Field>
              <div className="modal-actions">
                <button className="button primary" disabled={busy}>
                  <Upload size={17} />
                  {t("uploadRef")}
                </button>
              </div>
            </form>
          )}
          {modal === "review" && preview && (
            <div>
              <div className="preview-title">
                <strong>{preview.name}</strong>
                <Badge status={preview.status} t={t} />
              </div>
              {preview.error && (
                <p className="inline-error">{errorText(preview.error, lang)}</p>
              )}
              <div className="extracted-text">
                {preview.chunks?.map((chunk, i) => (
                  <Field key={chunk.id} label={chunk.location}>
                    <textarea
                      rows={5}
                      value={chunk.text}
                      readOnly={
                        preview.kind !== "reference" ||
                        preview.metadata.publication !== "draft"
                      }
                      onChange={(e) => {
                        setReviewed(false);
                        const chunks = [...preview.chunks!];
                        chunks[i] = { ...chunk, text: e.target.value };
                        setPreview({ ...preview, chunks });
                      }}
                    />
                  </Field>
                ))}
              </div>
              {preview.kind === "reference" &&
              preview.status === "ready" &&
              preview.metadata.publication === "draft" ? (
                <>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={reviewed}
                      onChange={(e) => setReviewed(e.target.checked)}
                    />
                    {t("reviewed")}
                  </label>
                  <Field label={t("replace")}>
                    <select
                      value={replacement}
                      onChange={(e) => setReplacement(e.target.value)}
                    >
                      <option value="">{t("noReplacement")}</option>
                      {references
                        .filter(
                          (d) =>
                            d.id !== preview.id &&
                            d.metadata.publication === "published",
                        )
                        .map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.metadata.title} · {d.metadata.version}
                          </option>
                        ))}
                    </select>
                  </Field>
                  <div className="modal-actions">
                    <button
                      className="button secondary"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api(
                            "/admin/references/" + preview.id,
                            "PATCH",
                            { publication: "draft", chunks: preview.chunks },
                          );
                          setSuccess(t("edited"));
                        })
                      }
                    >
                      {t("save")}
                    </button>
                    <button
                      className="button primary"
                      disabled={busy || !reviewed}
                      onClick={() =>
                        run(async () => {
                          await api(
                            "/admin/references/" + preview.id,
                            "PATCH",
                            {
                              publication: "published",
                              reviewed,
                              chunks: preview.chunks,
                              replaces: replacement || undefined,
                            },
                          );
                          setModal("");
                        })
                      }
                    >
                      {t("publish")}
                    </button>
                  </div>
                </>
              ) : (
                <p className="muted">
                  {preview.kind === "reference" && t("referenceVersion")}
                </p>
              )}
              <div className="modal-actions">
                {preview.status === "failed" && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        await api(
                          "/documents/" + preview.id + "/retry",
                          "POST",
                        );
                        setModal("");
                      })
                    }
                  >
                    <RefreshCw size={16} />
                    {t("retry")}
                  </button>
                )}
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      const r = await api<{ url: string }>(
                        "/documents/" + preview.id + "/download",
                        "POST",
                      );
                      const a = document.createElement("a");
                      a.href = r.url;
                      a.download = preview.name;
                      a.click();
                    })
                  }
                >
                  <Download size={16} />
                  {t("view")}
                </button>
              </div>
            </div>
          )}
          {modal === "citation" && passage && (
            <div className="passage">
              <strong>
                {passage.document_name} · {passage.location}
              </strong>
              <blockquote>{passage.text}</blockquote>
            </div>
          )}
          {modal.startsWith("delete") && (
            <>
              <p>
                {t(
                  modal === "delete-case" ? "deleteConfirm" : "deleteDocument",
                )}
              </p>
              <div className="modal-actions">
                <button
                  className="button secondary"
                  onClick={() => setModal("")}
                >
                  {t("cancel")}
                </button>
                <button
                  className="button destructive"
                  disabled={busy}
                  onClick={() =>
                    run(async () => {
                      if (modal === "delete-case") {
                        await api("/cases/" + selected!.id, "DELETE");
                        setSelected(null);
                      } else {
                        await api("/documents/" + preview!.id, "DELETE");
                      }
                      setModal("");
                    })
                  }
                >
                  <Trash2 size={16} />
                  {t("delete")}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
      {busy && (
        <div className="busy-indicator" role="status">
          <LoaderCircle className="spin" size={15} />
          {t("loading")}
        </div>
      )}
    </>
  );
}

class Boundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <div className="empty">
        <h1>Amanah · أمانة</h1>
        <p>Rechargez la page pour continuer. / أعد تحميل الصفحة للمتابعة.</p>
        <button className="button primary" onClick={() => location.reload()}>
          Recharger / إعادة التحميل
        </button>
      </div>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Boundary>
      <App />
    </Boundary>
  </React.StrictMode>,
);
