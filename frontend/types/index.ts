export type Mode = "with_master" | "without_master";
export type PageKey = "dashboard" | "analisis" | "validasi-nama" | "validasi-nilai" | "preview" | "download";

export type Approval = {
  mapping_id: string;
  approved: boolean;
  matched_name?: string | null;
  matched_class?: string | null;
};

export type AnalysisResult = {
  session_id: string;
  mode: Mode;
  summary: Record<string, any>;
  mapping: Record<string, any>[];
  recommendations: Record<string, any>[];
  duplicates: Record<string, any>[];
  validation_scores: Record<string, any>[];
  validation_codes: Record<string, any>[];
  missing_scores: Record<string, any>[];
  preview: Record<string, any>;
  dashboard: Record<string, any>;
};
