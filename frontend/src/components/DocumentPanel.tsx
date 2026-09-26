import type { Document } from "../types";

type DocumentPanelProps = {
  documents: Document[] | null;
  error: string | null;
};

export function DocumentPanel({ documents, error }: DocumentPanelProps) {
  const groups = documents ? groupDocuments(documents) : [];

  return (
    <aside className="sidebar">
      <div className="side-head">
        <h1>Documents</h1>
        <p>
          {documents
            ? `${documents.length} embedded notes`
            : "Loading the corpus"}
        </p>
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      {documents === null && !error ? (
        <p className="muted">Loading documents…</p>
      ) : null}
      {documents && documents.length === 0 ? (
        <p className="muted">No documents are loaded.</p>
      ) : null}
      {groups.map((group) => (
        <section key={group.module} className="module">
          <h2>
            <span className="tag" data-module={group.module}>
              {group.module}
            </span>
            <span className="count">{group.documents.length}</span>
          </h2>
          <ul>
            {group.documents.map((document) => (
              <li key={document.id} className="doc">
                <p className="doc-id">{document.id}</p>
                <p className="doc-text">{document.text}</p>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </aside>
  );
}

function groupDocuments(
  documents: Document[],
): Array<{ module: string; documents: Document[] }> {
  const groups = new Map<string, Document[]>();
  for (const document of documents) {
    const list = groups.get(document.module);
    if (list) list.push(document);
    else groups.set(document.module, [document]);
  }
  return Array.from(groups, ([module, docs]) => ({ module, documents: docs }));
}
