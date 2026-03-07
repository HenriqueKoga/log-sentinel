import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { http } from "../../shared/api/http";

export type FixSuggestion = {
  fingerprint: string;
  title: string;
  summary: string;
  probable_cause: string;
  suggested_fix: string;
  code_snippet: string | null;
  language: string | null;
  confidence: number;
  occurrences: number;
  first_seen: string;
  last_seen: string;
  sample_event_id: number | null;
  analyzed: boolean;
};

export type FixSuggestionsResponse = {
  items: FixSuggestion[];
  total: number;
};

export type FixSuggestionsParams = {
  project_id?: number;
  from?: string;
  to?: string;
  lang: string;
  sort_by?: string;
  order?: string;
  page?: number;
  page_size?: number;
};

export function useFixSuggestions(params: FixSuggestionsParams) {
  const { project_id, from, to, lang, sort_by = "occurrences", order = "desc", page = 1, page_size = 10 } = params;

  return useQuery({
    queryKey: ["ai-fix-suggestions", project_id, from, to, lang, sort_by, order, page, page_size],
    queryFn: async () => {
      const searchParams = new URLSearchParams();
      if (project_id != null) searchParams.set("project_id", String(project_id));
      if (from) searchParams.set("from", from);
      if (to) searchParams.set("to", to);
      if (lang) searchParams.set("lang", lang);
      searchParams.set("sort_by", sort_by);
      searchParams.set("order", order);
      searchParams.set("page", String(page));
      searchParams.set("page_size", String(page_size));

      const { data } = await http.get<FixSuggestionsResponse>(
        `/api/v1/ai-insights/fix-suggestions?${searchParams.toString()}`,
      );
      return data;
    },
  });
}

export type AnalyzeFixSuggestionParams = {
  fingerprint: string;
  project_id?: number;
  from?: string;
  to?: string;
  lang: string;
};

export function useAnalyzeFixSuggestion(params: FixSuggestionsParams) {
  const queryClient = useQueryClient();
  const { from, to, lang } = params;

  return useMutation({
    mutationFn: async (body: { fingerprint: string; project_id?: number }) => {
      const searchParams = new URLSearchParams();
      if (body.project_id != null) searchParams.set("project_id", String(body.project_id));
      if (from) searchParams.set("from", from);
      if (to) searchParams.set("to", to);
      if (lang) searchParams.set("lang", lang);
      const { data } = await http.post<FixSuggestion>(
        `/api/v1/ai-insights/fix-suggestions/analyze?${searchParams.toString()}`,
        { fingerprint: body.fingerprint, project_id: body.project_id ?? null },
      );
      return data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["ai-fix-suggestions"] });
    },
  });
}

