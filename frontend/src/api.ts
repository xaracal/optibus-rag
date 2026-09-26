import type { Document, QueryResponse, Readiness } from "./types";

const PAGE_SIZE = 200;

async function send(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  return response;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        const messages = detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item
              ? String(item.msg)
              : "",
          )
          .filter(Boolean);
        if (messages.length > 0) return messages.join(" ");
      }
    }
  } catch {
    // The body was not JSON.
  }
  return `Request failed (${response.status})`;
}

export async function fetchAllDocuments(): Promise<Document[]> {
  const documents: Document[] = [];
  for (;;) {
    const response = await send(
      `/api/documents?offset=${documents.length}&limit=${PAGE_SIZE}`,
    );
    const page = (await response.json()) as Document[];
    documents.push(...page);
    const total = Number(response.headers.get("X-Total-Count"));
    const done = Number.isFinite(total)
      ? documents.length >= total
      : page.length < PAGE_SIZE;
    if (done || page.length === 0) return documents;
  }
}

export async function fetchReadiness(): Promise<Readiness> {
  const response = await fetch("/api/ready");
  return (await response.json()) as Readiness;
}

export async function runQuery(query: string): Promise<QueryResponse> {
  const response = await send("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  return (await response.json()) as QueryResponse;
}
