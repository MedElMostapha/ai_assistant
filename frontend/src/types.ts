export type Lang = "fr" | "ar";
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  suspended: boolean;
  verified: boolean;
  analysis_count?: number;
};
export type Doc = {
  id: string;
  name: string;
  kind: string;
  status: string;
  error: string | null;
  page_count: number;
  metadata: Record<string, string>;
  chunks?: { id: string; location: string; text: string }[];
};
export type Citation = {
  passage_id: string;
  quote: string;
  document_name: string;
  location: string;
  kind: string;
};
export type Finding = {
  requirement_id: string;
  title: string;
  status: string;
  severity: string;
  explanation: string;
  missing: string[];
  correction: string;
  citations: Citation[];
  tender_citation: Citation;
};
export type Report = {
  summary: string;
  findings: Finding[];
  limitations: string[];
  references: Record<string, string>[];
  language: Lang;
};
export type Analysis = {
  id: string;
  version: number;
  status: string;
  progress: number;
  error: string | null;
  created_at: string;
  attempts: number;
  report?: Report;
};
export type Case = {
  id: string;
  title: string;
  description: string;
  language: Lang;
  created_at: string;
  document_count: number;
  latest_analysis: Analysis | null;
  documents?: Doc[];
  analyses?: Analysis[];
};
export type Job = {
  id: string;
  type: string;
  status: string;
  error: string | null;
  attempts?: number;
};
