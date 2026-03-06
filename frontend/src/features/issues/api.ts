import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type IssueStatus = "open" | "snoozed" | "resolved";
export type IssueSeverity = "low" | "medium" | "high" | "critical";

export type IssueListItem = {
  id: number;
  project_id: number;
  title: string;
  severity: IssueSeverity;
  status: IssueStatus;
  last_seen: string;
  total_count: number;
  priority_score: number;
};

export type IssuesAggregates = {
  total: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
};

export type IssuesListResponse = {
  items: IssueListItem[];
  aggregates: IssuesAggregates;
};

export type IssueDetailSample = {
  received_at: string;
  level: string;
  message: string;
  exception_type: string | null;
  stacktrace: string | null;
};

export type IssueEnrichment = {
  model_name: string;
  summary: string;
  suspected_cause: string;
  checklist: unknown;
  created_at: string;
};

export type IssueDetail = {
  id: number;
  project_id: number;
  title: string;
  severity: IssueSeverity;
  status: IssueStatus;
  first_seen: string;
  last_seen: string;
  total_count: number;
  priority_score: number;
  snoozed_until: string | null;
  samples: IssueDetailSample[];
  enrichment: IssueEnrichment | null;
};

export type IssueOccurrencesPoint = { bucket_start: string; count: number };
export type IssueOccurrencesResponse = { points: IssueOccurrencesPoint[] };

export type IssuesStatusFilter = "all" | "open" | "closed";
export type IssuesSortBy = "priority" | "severity" | "last_seen";

export function useIssues(params: {
  projectId?: number | null;
  page: number;
  pageSize: number;
  statusFilter?: IssuesStatusFilter;
  sortBy?: IssuesSortBy;
}) {
  const { projectId, page, pageSize, statusFilter = "all", sortBy = "priority" } = params;
  const status =
    statusFilter === "open" ? ["open", "snoozed"] : statusFilter === "closed" ? ["resolved"] : undefined;
  return useQuery({
    queryKey: ["issues", { projectId: projectId ?? null, page, pageSize, statusFilter, sortBy }],
    queryFn: async () => {
      const params: Record<string, string | number | string[] | undefined> = {
        project_id: projectId ?? undefined,
        page,
        page_size: pageSize,
        status,
        sort_by: sortBy,
      };
      const search = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null) return;
        if (Array.isArray(value)) {
          value.forEach((v) => search.append(key, String(v)));
        } else {
          search.append(key, String(value));
        }
      });
      const { data } = await http.get<IssuesListResponse>(`/api/v1/issues?${search.toString()}`);
      return data;
    },
  });
}

export function useIssue(issueId: number) {
  return useQuery({
    queryKey: ["issues", issueId],
    queryFn: async () => {
      const { data } = await http.get<IssueDetail>(`/api/v1/issues/${issueId}`);
      return data;
    },
    enabled: Number.isFinite(issueId) && issueId > 0,
  });
}

export function useIssueOccurrences(issueId: number, range: "24h" | "7d" | "30d") {
  return useQuery({
    queryKey: ["issues", issueId, "occurrences", range],
    queryFn: async () => {
      const { data } = await http.get<IssueOccurrencesResponse>(`/api/v1/issues/${issueId}/occurrences`, {
        params: { range },
      });
      return data;
    },
    enabled: Number.isFinite(issueId) && issueId > 0,
  });
}

export function useResolveIssue(issueId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await http.post(`/api/v1/issues/${issueId}/actions/resolve`);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
      await qc.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export function useReopenIssue(issueId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await http.post(`/api/v1/issues/${issueId}/actions/reopen`);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
      await qc.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export function useSnoozeIssue(issueId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (durationMinutes: number) => {
      await http.post(`/api/v1/issues/${issueId}/actions/snooze`, { duration_minutes: durationMinutes });
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
      await qc.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export type EnrichIssuePayload = { log_id?: number };

export function useEnrichIssue(issueId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload?: EnrichIssuePayload) => {
      const { data } = await http.post<{ enrichment: IssueEnrichment }>(
        `/api/v1/issues/${issueId}/enrich`,
        payload ?? {}
      );
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
      await qc.invalidateQueries({ queryKey: ["issues", issueId] });
    },
  });
}

export type CreateIssuePayload = {
  project_id: number;
  title: string;
  severity: IssueSeverity;
};

export type SuggestIssuePayload = { context: string };
export type SuggestIssueResult = { title: string; severity: IssueSeverity };

export function useCreateIssue() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateIssuePayload) => {
      const { data } = await http.post<IssueListItem>("/api/v1/issues", payload);
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}

export function useCreateIssueFromLog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (logId: number) => {
      const { data } = await http.post<IssueListItem>("/api/v1/issues/from-log", { log_id: logId });
      return data;
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["issues"] });
      await qc.invalidateQueries({ queryKey: ["logs"] });
    },
  });
}

export function useSuggestIssue() {
  return useMutation({
    mutationFn: async (payload: SuggestIssuePayload) => {
      const { data } = await http.post<SuggestIssueResult>("/api/v1/issues/suggest", payload);
      return data;
    },
  });
}

