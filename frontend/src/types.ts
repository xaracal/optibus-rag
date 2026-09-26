export type Document = {
  id: string;
  module: string;
  text: string;
};

export type RetrievedDocument = Document & {
  score: number;
};

export type QueryResponse = {
  retrieved_docs: RetrievedDocument[];
  answer: string;
};

export type Readiness = {
  ready: boolean;
  documents: number;
  detail: string | null;
};
