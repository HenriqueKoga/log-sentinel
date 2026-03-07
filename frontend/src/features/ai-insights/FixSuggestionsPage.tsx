import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Close as CloseIcon } from "@mui/icons-material";
import { MenuItem, Pagination, TextField } from "@mui/material";
import { useProjects } from "../projects/api";
import { useBillingPlan } from "../billing/api";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { getErrorMessage } from "../../shared/api/errors";
import { FixSuggestion, useAnalyzeFixSuggestion, useFixSuggestions } from "./api";

type RangeKey = "24h" | "7d" | "30d";

type SortBy = "occurrences" | "last_seen" | "first_seen" | "confidence" | "title";
type SortOrder = "asc" | "desc";

const RANGE_OPTIONS: { key: RangeKey; days: number }[] = [
  { key: "24h", days: 1 },
  { key: "7d", days: 7 },
  { key: "30d", days: 30 },
];

export function FixSuggestionsPage() {
  const { t, i18n } = useTranslation();
  const [projectId, setProjectId] = useState<number | "">("");
  const [range, setRange] = useState<RangeKey>("7d");
  const [sortBy, setSortBy] = useState<SortBy>("occurrences");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [page, setPage] = useState(1);
  const pageSize = 10;
  const [selected, setSelected] = useState<FixSuggestion | null>(null);

  const projects = useProjects();
  const billingPlan = useBillingPlan();

  const { from, to } = useMemo(() => {
    const toDate = new Date();
    const option = RANGE_OPTIONS.find((o) => o.key === range) ?? RANGE_OPTIONS[1];
    const fromDate = new Date(toDate.getTime() - option.days * 24 * 60 * 60 * 1000);
    return {
      from: fromDate.toISOString(),
      to: toDate.toISOString(),
    };
  }, [range]);

  const queryParams = useMemo(
    () => ({
      project_id: projectId === "" ? undefined : projectId,
      from,
      to,
      lang: i18n.language || "pt-BR",
      sort_by: sortBy,
      order: sortOrder,
      page,
      page_size: pageSize,
    }),
    [projectId, from, to, i18n.language, sortBy, sortOrder, page, pageSize],
  );
  const suggestionsQuery = useFixSuggestions(queryParams);
  const analyzeMutation = useAnalyzeFixSuggestion(queryParams);

  if (suggestionsQuery.isLoading) {
    return <LoadingState label={t("common.loading")} />;
  }

  if (suggestionsQuery.error) {
    return <ErrorState message={getErrorMessage(suggestionsQuery.error)} />;
  }

  const items = suggestionsQuery.data?.items ?? [];
  const total = suggestionsQuery.data?.total ?? 0;
  const llmEnabled = billingPlan.data?.enable_llm_enrichment ?? false;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="flex max-h-[calc(100vh-7rem)] min-h-0 flex-col">
      <div className="flex flex-shrink-0 flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {t("ai.fixSuggestions.title", "Fix suggestions")}
          </h1>
          <p className="text-sm text-slate-400">
            {t(
              "ai.fixSuggestions.subtitle",
              "Grouped recurring errors with heuristic/LLM suggestions to help you fix them.",
            )}
          </p>
        </div>
        <div className="flex-1" />
        <TextField
          select
          size="small"
          label={t("logs.project")}
          value={projectId}
          onChange={(e) => setProjectId(e.target.value === "" ? "" : Number(e.target.value))}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="">{t("logs.allProjects", "All projects")}</MenuItem>
          {(projects.data ?? []).map((p) => (
            <MenuItem key={p.id} value={p.id}>
              {p.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label={t("ai.fixSuggestions.period", "Period")}
          value={range}
          onChange={(e) => setRange(e.target.value as RangeKey)}
          sx={{ minWidth: 140 }}
        >
          {RANGE_OPTIONS.map((opt) => (
            <MenuItem key={opt.key} value={opt.key}>
              {t(`ai.fixSuggestions.range${opt.key.toUpperCase()}` as const)}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label={t("ai.fixSuggestions.sortBy", "Sort by")}
          value={sortBy}
          onChange={(e) => {
            setSortBy(e.target.value as SortBy);
            setPage(1);
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="occurrences">{t("ai.fixSuggestions.sortOccurrences", "Occurrences")}</MenuItem>
          <MenuItem value="last_seen">{t("ai.fixSuggestions.columns.lastSeen", "Last seen")}</MenuItem>
          <MenuItem value="first_seen">{t("ai.fixSuggestions.columns.firstSeen", "First seen")}</MenuItem>
          <MenuItem value="confidence">{t("ai.fixSuggestions.columns.confidence", "Confidence")}</MenuItem>
          <MenuItem value="title">{t("ai.fixSuggestions.columns.error", "Error")}</MenuItem>
        </TextField>
        <TextField
          select
          size="small"
          label={t("ai.fixSuggestions.order", "Order")}
          value={sortOrder}
          onChange={(e) => {
            setSortOrder(e.target.value as SortOrder);
            setPage(1);
          }}
          sx={{ minWidth: 120 }}
        >
          <MenuItem value="desc">{t("ai.fixSuggestions.orderDesc", "Descending")}</MenuItem>
          <MenuItem value="asc">{t("ai.fixSuggestions.orderAsc", "Ascending")}</MenuItem>
        </TextField>
      </div>

      <div className="mt-4 flex flex-col">
        <div className="h-[600px] overflow-auto rounded-2xl border border-white/5 bg-black/30">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-black/60 backdrop-blur">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.error", "Error")}
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.summary", "Summary")}
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.occurrences", "Occurrences")}
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.firstSeen", "First seen")}
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.lastSeen", "Last seen")}
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.confidence", "Confidence")}
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr
                  key={s.fingerprint}
                  className="cursor-pointer border-t border-white/5 hover:bg-white/5"
                  onClick={() => setSelected(s)}
                >
                  <td className="px-3 py-2 align-top text-sm font-medium text-slate-100">
                    {s.title}
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-slate-300">
                    <div className="line-clamp-3">{s.summary}</div>
                    <div className="mt-1 text-[11px] text-slate-400">
                      <span className="font-semibold">
                        {t("ai.fixSuggestions.causeLabel", "Probable cause")}:
                      </span>{" "}
                      {s.probable_cause}
                    </div>
                    <div className="mt-1 text-[11px] text-slate-400">
                      <span className="font-semibold">
                        {t("ai.fixSuggestions.fixLabel", "Suggested fix")}:
                      </span>{" "}
                      {s.suggested_fix}
                    </div>
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-slate-200">{s.occurrences}</td>
                  <td className="px-3 py-2 align-top text-xs text-slate-300">
                    {new Date(s.first_seen).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 align-top text-xs text-slate-300">
                    {new Date(s.last_seen).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 align-middle text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="inline-flex rounded-full bg-emerald-500/15 px-2 py-0.5 text-emerald-300">
                        {(s.confidence * 100).toFixed(0)}%
                      </span>
                      {s.analyzed && (
                        <span className="inline-flex rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] text-violet-300" title={t("ai.fixSuggestions.analyzedByAi", "Analyzed by AI")}>
                          AI
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td
                    className="px-3 py-8 text-center text-sm text-slate-500"
                    colSpan={6}
                  >
                    {t(
                      "ai.fixSuggestions.empty",
                      "No recurring error clusters found for this period.",
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-shrink-0 justify-end">
          {total > 0 && (
            <Pagination
              count={totalPages}
              page={page}
              onChange={(_, value) => setPage(value)}
              color="primary"
              showFirstButton
              showLastButton
            />
          )}
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-[210] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="max-h-[80vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-white/10 bg-slate-950/95 p-6 shadow-2xl">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-slate-50">{selected.title}</h2>
                <p className="mt-1 text-xs text-slate-400">
                  {t("ai.fixSuggestions.occurrences", "Occurrences")}:{" "}
                  <span className="font-semibold text-slate-100">{selected.occurrences}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="inline-flex h-8 w-8 cursor-pointer items-center justify-center rounded-full border border-white/20 bg-black/60 text-slate-200 hover:border-white/40 hover:bg-black/80"
                aria-label={t("common.cancel", "Close")}
              >
                <CloseIcon fontSize="small" />
              </button>
            </div>

            <div className="space-y-4 text-sm text-slate-200">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.columns.summary", "Summary")}
                </h3>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-100">{selected.summary}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.causeLabel", "Probable cause")}
                </h3>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-100">
                  {selected.probable_cause}
                </p>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {t("ai.fixSuggestions.fixLabel", "Suggested fix")}
                </h3>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-100">
                  {selected.suggested_fix}
                </p>
              </div>

              {selected.code_snippet && (
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {t("ai.fixSuggestions.codeLabel", "Code")}
                  </h3>
                  <pre className="mt-1 max-h-64 overflow-auto rounded-lg bg-black/60 p-3 text-xs text-slate-100">
                    {selected.code_snippet}
                  </pre>
                </div>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-400">
                  {t("ai.fixSuggestions.columns.confidence", "Confidence")}:{" "}
                  <span className="font-semibold text-emerald-300">
                    {(selected.confidence * 100).toFixed(0)}%
                  </span>
                </span>
                {selected.analyzed && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-violet-300">
                    ✦ {t("ai.fixSuggestions.analyzedByAi", "Analyzed by AI")}
                  </span>
                )}
              </div>
              {!selected.analyzed && (
                <button
                  type="button"
                  disabled={!llmEnabled || analyzeMutation.isPending}
                  onClick={() => {
                    analyzeMutation.mutate(
                      {
                        fingerprint: selected.fingerprint,
                        project_id: projectId === "" ? undefined : projectId,
                      },
                      {
                        onSuccess: (updated) => {
                          setSelected(updated);
                        },
                      },
                    );
                  }}
                  className={`inline-flex items-center justify-center rounded-full px-4 py-2 text-xs font-semibold ${
                    !llmEnabled
                      ? "cursor-not-allowed bg-white/5 text-slate-500"
                      : "cursor-pointer bg-primary/30 text-slate-100 hover:bg-primary/40"
                  }`}
                >
                  {analyzeMutation.isPending
                    ? t("ai.fixSuggestions.analyzing", "Analyzing…")
                    : t("ai.fixSuggestions.analyzeWithAi", "Analyze with AI")}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

