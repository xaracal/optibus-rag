const EXAMPLES = [
  "Which routes should change for morning peak demand?",
  "What rest rules apply to driver shifts?",
  "Which buses or depots have maintenance or fuel issues?",
  "How will the city marathon affect downtown service?",
];

type QueryPanelProps = {
  query: string;
  loading: boolean;
  onQueryChange: (value: string) => void;
  onSubmit: (value: string) => void;
};

export function QueryPanel({
  query,
  loading,
  onQueryChange,
  onSubmit,
}: QueryPanelProps) {
  return (
    <section className="ask">
      <h1>Ask the corpus</h1>
      <p className="lede">
        Questions are embedded, matched to the closest domain notes, and
        answered from those passages only.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(query);
        }}
      >
        <label htmlFor="query">Query</label>
        <textarea
          id="query"
          value={query}
          placeholder="Ask about routes, driver shifts, or live operations"
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit(query);
            }
          }}
        />
        <div className="composer-row">
          <p className="hint">Enter runs the query. Shift+Enter adds a line.</p>
          <button
            className="primary"
            type="submit"
            disabled={loading || query.trim().length === 0}
          >
            {loading ? "Running…" : "Run query"}
          </button>
        </div>
      </form>
      <div className="examples">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="example"
            onClick={() => onSubmit(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </section>
  );
}
