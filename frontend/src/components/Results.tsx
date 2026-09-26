import type { QueryResponse } from "../types";

type ResultsProps = {
  asked: string;
  result: QueryResponse;
};

export function Results({ asked, result }: ResultsProps) {
  const best = result.retrieved_docs[0]?.score ?? 0;

  return (
    <section className="results" aria-live="polite">
      <article className="answer">
        <p className="eyebrow">Answer</p>
        <h2>{asked}</h2>
        <p className="answer-text">{result.answer}</p>
      </article>
      <div className="passages">
        <h3>Retrieved passages</h3>
        {result.retrieved_docs.length === 0 ? (
          <p className="muted">Nothing was retrieved.</p>
        ) : (
          <ol>
            {result.retrieved_docs.map((document, index) => (
              <li key={`${document.id}-${index}`} className="passage">
                <span className="rank">{index + 1}</span>
                <div>
                  <p className="passage-meta">
                    <span className="tag" data-module={document.module}>
                      {document.module}
                    </span>
                    <span className="doc-id">{document.id}</span>
                  </p>
                  <p className="doc-text">{document.text}</p>
                </div>
                <Similarity score={document.score} best={best} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function Similarity({ score, best }: { score: number; best: number }) {
  const ratio = best > 0 ? Math.max(score, 0) / best : 0;
  return (
    <div className="similarity">
      <span>{score.toFixed(2)}</span>
      <span className="meter" aria-hidden="true">
        <span style={{ width: `${Math.round(ratio * 100)}%` }} />
      </span>
    </div>
  );
}
