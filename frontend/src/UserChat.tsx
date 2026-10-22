import { useCallback, useEffect, useRef, useState } from "react";
import {
  Scale,
  Send,
  Paperclip,
  Plus,
  History,
  X,
  FileText,
  ShieldCheck,
  LogOut,
  Languages,
  Trash2,
  LoaderCircle,
  ArrowUpRight,
  Download,
  BookOpen,
  RefreshCw,
  ChevronDown,
  MessageSquare,
} from "lucide-react";
import { api, ApiError, downloadPdf } from "./api";
import { texts, errorText, type TextKey } from "./i18n";
import { chatTexts, type ChatKey } from "./chat-i18n";
import type { User, Lang, Doc, Analysis, Citation } from "./types";
import "./chat.css";

type ChatSummary = { id: string; title: string; language: Lang };
type Message = {
  id: string;
  role: string;
  kind: string;
  content: string;
  language: Lang;
  status: string;
  error: string | null;
  citations: Citation[];
  attempts: number;
  analysis?: Analysis;
};
type Conversation = ChatSummary & {
  messages: Message[];
  documents: Doc[];
  previous_analyses: Analysis[];
};
type Source = { text: string; location: string; document_name: string };

export function UserChat({
  user,
  lang,
  onLanguage,
  onLogout,
}: {
  user: User;
  lang: Lang;
  onLanguage: () => void;
  onLogout: () => void;
}) {
  const t = (key: TextKey) => texts[lang][key];
  const c = (key: ChatKey) => chatTexts[lang][key];
  const [conversations, setConversations] = useState<ChatSummary[]>([]),
    [conversation, setConversation] = useState<Conversation | null>(null),
    [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [configured, setConfigured] = useState(false),
    [history, setHistory] = useState(false),
    [picker, setPicker] = useState(false),
    [source, setSource] = useState<Source | null>(null);
  const idRef = useRef<string | null>(null),
    fileRef = useRef<HTMLInputElement>(null),
    kindRef = useRef("offer"),
    creation = useRef<Promise<string> | null>(null),
    bottom = useRef<HTMLDivElement>(null),
    dialog = useRef<HTMLDialogElement>(null),
    composer = useRef<HTMLTextAreaElement>(null);
  const storageKey = "amanah_chat_" + user.id;
  const loadList = useCallback(async () => {
    const r = await api<{ chats: ChatSummary[]; ai_configured: boolean }>(
      "/chats",
    );
    setConversations(r.chats);
    setConfigured(r.ai_configured);
    return r.chats;
  }, []);
  const load = useCallback(
    async (id: string) => {
      try {
        const r = await api<Conversation>("/chats/" + id);
        if (idRef.current === id) setConversation(r);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404 && idRef.current === id) {
          idRef.current = null;
          setActiveId(null);
          setConversation(null);
          localStorage.setItem(storageKey, "new");
        } else throw e;
      }
    },
    [storageKey],
  );
  const fail = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) {
        onLogout();
        return;
      }
      setError(e instanceof ApiError ? e.code : "server_error");
    },
    [onLogout],
  );
  useEffect(() => {
    let cancelled = false;
    loadList()
      .then((items) => {
        if (cancelled) return;
        const saved = localStorage.getItem(storageKey);
        const id =
          saved === "new"
            ? null
            : items.find((item) => item.id === saved)?.id ||
              items[0]?.id ||
              null;
        idRef.current = id;
        setActiveId(id);
        if (id) load(id).catch(fail);
      })
      .catch(fail);
    return () => {
      cancelled = true;
    };
  }, [loadList, load, storageKey, fail]);
  useEffect(() => {
    if (!activeId) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") load(activeId).catch(fail);
    }, 3000);
    return () => clearInterval(timer);
  }, [activeId, load, fail]);
  const pending =
    !!conversation?.messages.some(
      (m) =>
        ["queued", "running"].includes(m.status) ||
        (m.analysis && ["queued", "running"].includes(m.analysis.status)),
    ) ||
    !!conversation?.previous_analyses.some((a) =>
      ["queued", "running"].includes(a.status),
    );
  const messageStamp = conversation?.messages
    .map((m) => m.id + ":" + m.status + ":" + m.analysis?.status)
    .join("|");
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeId, messageStamp]);
  useEffect(() => {
    if (source) dialog.current?.showModal();
    else dialog.current?.close();
  }, [source]);
  async function refresh() {
    await loadList();
    if (idRef.current) await load(idRef.current);
  }
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }
  function select(id: string | null) {
    idRef.current = id;
    setActiveId(id);
    setConversation(null);
    setDraft("");
    setError("");
    setPicker(false);
    setHistory(false);
    localStorage.setItem(storageKey, id || "new");
    if (id) load(id).catch(fail);
  }
  async function ensureConversation() {
    if (idRef.current) return idRef.current;
    if (!creation.current) {
      creation.current = api<{ id: string }>("/chats", "POST", {
        language: lang,
      })
        .then((r) => {
          idRef.current = r.id;
          setActiveId(r.id);
          localStorage.setItem(storageKey, r.id);
          return r.id;
        })
        .finally(() => {
          creation.current = null;
        });
    }
    return creation.current;
  }
  async function send(value = draft, intent = "message") {
    if (!value.trim() || busy || pending) return;
    await run(async () => {
      const id = await ensureConversation();
      await api("/chats/" + id + "/messages", "POST", {
        content: value.trim(),
        language: lang,
        intent,
      });
      setDraft("");
    });
    composer.current?.focus();
  }
  function chooseFile(kind: string) {
    kindRef.current = kind;
    setPicker(false);
    fileRef.current?.click();
  }
  async function upload(file: File) {
    await run(async () => {
      const id = await ensureConversation();
      const form = new FormData();
      form.set("file", file);
      form.set("kind", kindRef.current);
      await api("/cases/" + id + "/documents", "POST", form);
    });
  }
  async function showCitation(
    citation: Citation,
    message?: Message,
    analysis?: Analysis,
  ) {
    await run(async () => {
      const path = analysis
        ? `/analyses/${analysis.id}/passages/${encodeURIComponent(citation.passage_id)}`
        : `/chats/${activeId}/messages/${message!.id}/passages/${encodeURIComponent(citation.passage_id)}`;
      const r = await api<{ passage: Source }>(path);
      setSource(r.passage);
    });
  }
  function CitationLink({
    citation,
    message,
    analysis,
  }: {
    citation: Citation;
    message?: Message;
    analysis?: Analysis;
  }) {
    return (
      <button
        className="citation"
        onClick={() => showCitation(citation, message, analysis)}
      >
        <BookOpen size={13} />
        <span>
          {citation.document_name} · {citation.location}
        </span>
        <ArrowUpRight size={13} />
      </button>
    );
  }
  function Opinion({ analysis }: { analysis: Analysis }) {
    const report = analysis.report;
    return (
      <div className="chat-opinion">
        {analysis.status !== "completed" ? (
          <>
            <div className="chat-working">
              {analysis.status === "failed" ? (
                <RefreshCw size={18} />
              ) : (
                <LoaderCircle size={18} className="spin" />
              )}
              <strong>
                {analysis.status === "failed" ? t("failed") : c("preparing")}
              </strong>
            </div>
            {analysis.error && <p>{errorText(analysis.error, lang)}</p>}
            {analysis.status !== "failed" && (
              <progress
                max={100}
                value={analysis.progress}
                aria-label={t("progress")}
              />
            )}{" "}
            {analysis.status === "failed" && analysis.attempts < 3 && (
              <button
                className="text-button"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await api("/analyses/" + analysis.id + "/retry", "POST");
                  })
                }
              >
                {c("retry")}
              </button>
            )}
          </>
        ) : (
          report && (
            <div
              dir={report.language === "ar" ? "rtl" : "ltr"}
              lang={report.language}
            >
              <p className="chat-answer">{report.summary}</p>
              <div className="chat-report-actions">
                <button
                  className="button secondary small"
                  disabled={busy}
                  onClick={() => run(() => downloadPdf(analysis.id))}
                >
                  <Download size={15} />
                  {t("export")}
                </button>
                <small>
                  {t("version")} {analysis.version}
                </small>
              </div>
              <details className="chat-report-details">
                <summary>
                  {c("inspect")}
                  <ChevronDown size={16} />
                </summary>
                {report.findings.map((f) => (
                  <article className="chat-finding" key={f.requirement_id}>
                    <div>
                      <h3>{f.title}</h3>
                      <span className={"badge " + f.status}>
                        {t(f.status as TextKey)}
                      </span>
                    </div>
                    <p>{f.explanation}</p>
                    <div className="citations">
                      <CitationLink
                        citation={f.tender_citation}
                        analysis={analysis}
                      />
                      {f.citations
                        .filter(
                          (c) =>
                            c.passage_id !== f.tender_citation.passage_id ||
                            c.quote !== f.tender_citation.quote,
                        )
                        .map((citation, index) => (
                          <CitationLink
                            key={index}
                            citation={citation}
                            analysis={analysis}
                          />
                        ))}
                    </div>
                    {f.missing.length > 0 && (
                      <>
                        <strong>{t("missing")}</strong>
                        <ul>
                          {f.missing.map((m, index) => (
                            <li key={index}>{m}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {f.correction && (
                      <div className="correction">
                        <div>
                          <strong>{t("correction")}</strong>
                          <p>{f.correction}</p>
                        </div>
                      </div>
                    )}
                  </article>
                ))}
                <h3>{t("references")}</h3>
                {report.references.length ? (
                  report.references.map((r) => (
                    <p key={r.id}>
                      {r.title} · {r.authority} · {r.version}
                    </p>
                  ))
                ) : (
                  <p>{t("noSources")}</p>
                )}
                <h3>{t("limitations")}</h3>
                <ul>
                  {report.limitations.map((l, index) => (
                    <li key={index}>{l}</li>
                  ))}
                </ul>
              </details>
            </div>
          )
        )}
      </div>
    );
  }
  const docs = conversation?.documents || [];
  const readable =
    docs.length > 0 &&
    docs.every((d) => d.status === "ready") &&
    ["offer", "tender"].every((kind) => docs.some((d) => d.kind === kind));
  const describeError = (code: string) =>
    code in chatTexts[lang] ? c(code as ChatKey) : errorText(code, lang);
  return (
    <div className="chat-app">
      <header className="chat-header">
        <div className="brand">
          <span className="brand-mark">
            <Scale size={25} />
          </span>
          <span>
            Amanah<span className="brand-ar">أمانة</span>
          </span>
        </div>
        <span className="chat-private">
          <ShieldCheck size={14} />
          {c("private")}
        </span>
        <div className="chat-header-actions">
          <button
            className="icon-button"
            aria-label={c("newChat")}
            title={c("newChat")}
            disabled={busy}
            onClick={() => select(null)}
          >
            <Plus size={20} />
          </button>
          <button
            className="icon-button"
            aria-label={c("history")}
            title={c("history")}
            aria-expanded={history}
            onClick={() => setHistory(!history)}
          >
            <History size={19} />
          </button>
          <button className="chat-lang" onClick={onLanguage}>
            <Languages size={16} />
            {lang === "fr" ? "العربية" : "Français"}
          </button>
          <button
            className="icon-button"
            aria-label={t("logout")}
            title={t("logout")}
            onClick={() =>
              run(async () => {
                await api("/auth/logout", "POST");
                onLogout();
              })
            }
          >
            <LogOut size={18} />
          </button>
        </div>
      </header>
      {history && (
        <>
          <button
            className="chat-drawer-backdrop"
            aria-label={c("close")}
            onClick={() => setHistory(false)}
          />
          <aside className="chat-history">
            <div>
              <h2>{c("history")}</h2>
              <button
                className="icon-button"
                aria-label={c("close")}
                onClick={() => setHistory(false)}
              >
                <X size={18} />
              </button>
            </div>
            <button
              className="button primary full"
              disabled={busy}
              onClick={() => select(null)}
            >
              <Plus size={17} />
              {c("newChat")}
            </button>
            {conversations.length ? (
              conversations.map((item) => (
                <div
                  className={
                    "chat-history-item " +
                    (item.id === activeId ? "active" : "")
                  }
                  key={item.id}
                >
                  <button onClick={() => select(item.id)}>
                    <MessageSquare size={17} />
                    <span>{item.title}</span>
                  </button>
                  <button
                    className="icon-button"
                    aria-label={c("delete")}
                    disabled={busy}
                    onClick={() => {
                      if (window.confirm(c("deleteChat")))
                        run(async () => {
                          await api("/cases/" + item.id, "DELETE");
                          if (idRef.current === item.id) select(null);
                        });
                    }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            ) : (
              <p>{c("noHistory")}</p>
            )}
          </aside>
        </>
      )}
      <main className="chat-main">
        <section className="chat-thread" aria-label={c("messages")}>
          <div className="chat-intro">
            <span className="chat-intro-mark">
              <Scale size={29} />
            </span>
            <span className="eyebrow">{c("subtitle")}</span>
            <h1>{c("welcome")}</h1>
            <p>{c("intro")}</p>
          </div>
          <div className="chat-message assistant">
            <div className="chat-speaker">
              <span>
                <Scale size={14} />
              </span>
              {c("assistant")}
            </div>
            <p className="chat-answer">{c("greeting")}</p>
          </div>
          {conversation?.previous_analyses.map((analysis) => (
            <div className="chat-message assistant" key={analysis.id}>
              <div className="chat-speaker">
                <span>
                  <Scale size={14} />
                </span>
                {c("assistant")}
              </div>
              <Opinion analysis={analysis} />
            </div>
          ))}
          {conversation?.messages.map((message) => (
            <article
              className={"chat-message " + message.role}
              key={message.id}
              dir={message.language === "ar" ? "rtl" : "ltr"}
              lang={message.language}
            >
              <div className="chat-speaker">
                <span>
                  {message.role === "user" ? (
                    user.name.slice(0, 1)
                  ) : (
                    <Scale size={14} />
                  )}
                </span>
                {message.role === "user" ? c("you") : c("assistant")}
              </div>
              {message.kind === "analysis" && message.analysis ? (
                <Opinion analysis={message.analysis} />
              ) : message.status === "failed" ? (
                <div>
                  <p>{describeError(message.error || "server_error")}</p>
                  {message.attempts < 3 && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api(
                            `/chats/${activeId}/messages/${message.id}/retry`,
                            "POST",
                          );
                        })
                      }
                    >
                      <RefreshCw size={14} />
                      {c("retry")}
                    </button>
                  )}
                </div>
              ) : ["queued", "running"].includes(message.status) ? (
                <p className="chat-working">
                  <LoaderCircle size={16} className="spin" />
                  {c("thinking")}
                </p>
              ) : (
                <>
                  <p className="chat-answer">
                    {message.kind === "notice"
                      ? (chatTexts[message.language] as Record<string, string>)[
                          message.content
                        ] || errorText(message.content, message.language)
                      : message.content}
                  </p>
                  {message.citations?.length > 0 && (
                    <div className="citations">
                      {message.citations.map((citation, index) => (
                        <CitationLink
                          key={index}
                          citation={citation}
                          message={message}
                        />
                      ))}
                    </div>
                  )}
                </>
              )}
            </article>
          ))}
          {!conversation?.messages.length && !docs.length && (
            <div className="chat-suggestions">
              <button onClick={() => send(c("helpQuestion"))}>
                <CircleHelpIcon />
                {c("helpQuestion")}
                <ArrowUpRight size={15} />
              </button>
              <button
                onClick={() => {
                  setDraft(c("emptyQuestion"));
                  composer.current?.focus();
                }}
              >
                <ShieldCheck size={17} />
                {c("emptyQuestion")}
                <ArrowUpRight size={15} />
              </button>
            </div>
          )}
          <div ref={bottom} />
        </section>
        <div className="chat-composer-area">
          {error && (
            <div className="error" role="alert">
              <span>{describeError(error)}</span>
              <button
                className="icon-button"
                aria-label={c("close")}
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {docs.length > 0 && (
            <div className="chat-attachments" aria-label={c("attachments")}>
              {docs.map((doc) => (
                <div className={"chat-attachment " + doc.status} key={doc.id}>
                  <FileText size={19} />
                  <div>
                    <strong>{doc.name}</strong>
                    <small>
                      {t(doc.kind as "offer" | "tender")} ·{" "}
                      {doc.status === "ready"
                        ? c("saved")
                        : doc.status === "failed"
                          ? c("failed")
                          : c("reading")}
                    </small>
                    {doc.error && (
                      <small className="inline-error">
                        {errorText(doc.error, lang)}
                      </small>
                    )}
                  </div>
                  {["queued", "extracting"].includes(doc.status) && (
                    <LoaderCircle size={14} className="spin" />
                  )}
                  {doc.status === "failed" && (
                    <button
                      className="icon-button"
                      aria-label={c("retry")}
                      disabled={busy || pending}
                      onClick={() =>
                        run(async () => {
                          await api("/documents/" + doc.id + "/retry", "POST");
                        })
                      }
                    >
                      <RefreshCw size={14} />
                    </button>
                  )}
                  <button
                    className="icon-button"
                    aria-label={c("remove") + " " + doc.name}
                    disabled={busy || pending}
                    onClick={() =>
                      run(async () => {
                        await api("/documents/" + doc.id, "DELETE");
                      })
                    }
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
          <form
            className="chat-composer"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <textarea
              ref={composer}
              aria-label={c("placeholder")}
              placeholder={c("placeholder")}
              value={draft}
              maxLength={6000}
              rows={2}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="chat-composer-toolbar">
              <div className="chat-attach-control">
                <button
                  type="button"
                  className="icon-button"
                  aria-label={c("attach")}
                  title={c("attach")}
                  aria-expanded={picker}
                  disabled={busy || pending}
                  onClick={() => setPicker(!picker)}
                >
                  <Paperclip size={20} />
                </button>
                {picker && (
                  <div className="chat-file-menu">
                    <button type="button" onClick={() => chooseFile("offer")}>
                      <FileText size={17} />
                      {c("offer")}
                    </button>
                    <button type="button" onClick={() => chooseFile("tender")}>
                      <BookOpen size={17} />
                      {c("tender")}
                    </button>
                    <small>PDF · DOCX · 25 Mo</small>
                  </div>
                )}
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx"
                  className="chat-hidden-input"
                  aria-label={c("attachments")}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (file) upload(file);
                  }}
                />
                <span className="chat-toolbar-help">{t("fileHelp")}</span>
              </div>
              <div>
                {readable && (
                  <button
                    type="button"
                    className="chat-analyze"
                    disabled={busy || pending}
                    onClick={() => send(c("analysisPrompt"), "analysis")}
                  >
                    <Scale size={15} />
                    {c("analyze")}
                  </button>
                )}
                <button
                  type="submit"
                  className="chat-send"
                  aria-label={c("send")}
                  disabled={busy || pending || !draft.trim()}
                >
                  {busy || pending ? (
                    <LoaderCircle size={18} className="spin" />
                  ) : (
                    <Send size={18} />
                  )}
                </button>
              </div>
            </div>
          </form>
          <div className="chat-bottom-note">
            <span>{configured ? c("disclaimer") : c("unavailable")}</span>
            <small>{c("enterHint")}</small>
          </div>
        </div>
      </main>
      <dialog
        ref={dialog}
        className="chat-source-dialog"
        onCancel={() => setSource(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setSource(null);
        }}
      >
        <div className="modal-head">
          <h2>{c("reference")}</h2>
          <button
            className="icon-button"
            aria-label={c("close")}
            onClick={() => setSource(null)}
          >
            <X size={18} />
          </button>
        </div>
        {source && (
          <div className="passage">
            <strong>
              {source.document_name} · {source.location}
            </strong>
            <blockquote>{source.text}</blockquote>
          </div>
        )}
      </dialog>
    </div>
  );
}
function CircleHelpIcon() {
  return <MessageSquare size={17} />;
}
