import { useQuery } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type LogRow = {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  project_id: number;
  project_name: string;
  source: string;
  ai_summary?: string | null;
};

export type LogsListResponse = {
  items: LogRow[];
  total: number;
};

export type LogsListParams = {
  project_id?: number;
  level?: string[];
  q?: string;
  from?: string;
  to?: string;
  page?: number;
  page_size?: number;
  without_issue?: boolean;
};

export function useLogs(params: LogsListParams = {}) {
  const { project_id, level, q, from, to, page = 1, page_size = 50, without_issue } = params;
  return useQuery({
    queryKey: ["logs", project_id, level, q, from, to, page, page_size, without_issue],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (project_id != null) searchParams.set("project_id", String(project_id));
      if (level?.length) level.forEach((l) => searchParams.append("level", l));
      if (q?.trim()) searchParams.set("q", q.trim());
      if (from) searchParams.set("from", from);
      if (to) searchParams.set("to", to);
      searchParams.set("page", String(page));
      searchParams.set("page_size", String(page_size));
      if (without_issue) searchParams.set("without_issue", "true");
      const { data } = await http.get<LogsListResponse>(
        `/api/v1/logs?${searchParams.toString()}`
      );
      return data;
    },
  });
}

export type LogDetailEnrichment = {
  model_name: string;
  summary: string;
  suspected_cause: string;
  checklist: string[];
  created_at: string;
};

export type LogDetailResponse = {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  exception_type: string | null;
  stacktrace: string | null;
  raw_json: Record<string, unknown>;
  project_id: number;
  project_name: string;
  source: string;
  related_issue: { id: number; title: string } | null;
  enrichment: LogDetailEnrichment | null;
};

export function useLogDetail(logId: number | null) {
  return useQuery({
    queryKey: ["logs", "detail", logId],
    queryFn: async () => {
      const id = logId!;
      const { data } = await http.get<LogDetailResponse>(`/api/v1/logs/${id}`);
      return data;
    },
    enabled: logId != null,
  });
}
