import { useEffect, useState } from "react";
import { fetchAllDocuments, fetchReadiness, runQuery } from "./api";
import { DocumentPanel } from "./components/DocumentPanel";
import { QueryPanel } from "./components/QueryPanel";
import { Results } from "./components/Results";
import type { Document, QueryResponse, Readiness } from "./types";

export function App() {
  const [documents, setDocuments] = useState<Document[] | null>(null);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [asked, setAsked] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchAllDocuments()
      .then((docs) => {
        if (active) setDocuments(docs);
      })
      .catch((error: unknown) => {
        if (active)
          setDocumentsError(
            error instanceof Error ? error.message : "Could not load documents",
          );
      });
    fetchReadiness()
      .then((status) => {
        if (active) setReadiness(status);
      })
      .catch(() => {
        if (active)
          setReadiness({
            ready: false,
            documents: 0,
            detail: "The backend is not reachable.",
          });
      });
    return () => {
      active = false;
    };
  }, []);

  async function submit(value: string) {
    const trimmed = value.trim();
    if (!trimmed || loading) return;
    setQuery(trimmed);
    setQueryError(null);
    setLoading(true);
    try {
      const next = await runQuery(trimmed);
      setResult(next);
      setAsked(trimmed);
    } catch (error: unknown) {
      setQueryError(error instanceof Error ? error.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  const ready = readiness?.ready ?? false;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <svg className="mark" viewBox="0 0 32 32" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="#0c6b63" />
            <path
              d="M7 22c4-9 8-9 9-9s5 0 9-9"
              fill="none"
              stroke="#f4efe4"
              strokeWidth="2"
              strokeLinecap="round"
            />
            <circle cx="16" cy="13" r="2" fill="#f4efe4" />
          </svg>
          <div>
            <p className="brand-name">Optibus</p>
            <p className="brand-kicker">Knowledge desk</p>
          </div>
        </div>
        <p className={ready ? "status ready" : "status"}>
          {readiness === null
            ? "Checking index…"
            : ready
              ? "Index ready"
              : "Index offline"}
        </p>
      </header>
      <div className="workspace">
        <DocumentPanel documents={documents} error={documentsError} />
        <main className="main">
          <div className="main-inner">
            {readiness && !readiness.ready && readiness.detail ? (
              <p className="banner" role="status">
                {readiness.detail}
              </p>
            ) : null}
            <QueryPanel
              query={query}
              loading={loading}
              onQueryChange={setQuery}
              onSubmit={submit}
            />
            {queryError ? (
              <p className="banner error" role="alert">
                {queryError}
              </p>
            ) : null}
            {loading ? (
              <p className="pending">
                Retrieving passages and writing an answer…
              </p>
            ) : null}
            {asked && result ? <Results asked={asked} result={result} /> : null}
          </div>
        </main>
      </div>
    </div>
  );
}
