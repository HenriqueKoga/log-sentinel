import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { MenuItem, Pagination, TextField } from "@mui/material";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { getErrorMessage } from "../../shared/api/errors";
import { useBillingPlan } from "../billing/api";
import { useCreateIssueFromLog, useEnrichIssue } from "../issues/api";
import { useProjects } from "../projects/api";
import { useLogDetail, useLogs, type LogRow } from "./api";

export function LogsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [projectId, setProjectId] = useState<number | "">("");
  const [severity, setSeverity] = useState<Set<string>>(
    () => new Set(["error", "warning", "info", "debug"]),
  );
  const [sorting, setSorting] = useState<SortingState>([{ id: "timestamp", desc: true }]);
  const [selectedLogId, setSelectedLogId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const projects = useProjects();
  const { data, isLoading, error } = useLogs({
    project_id: projectId === "" ? undefined : projectId,
    q: search.trim() || undefined,
    level: severity.size > 0 ? Array.from(severity) : undefined,
    page,
    page_size: pageSize,
  });
  const logDetail = useLogDetail(selectedLogId);

  const items = data?.items ?? [];

  const columns = useMemo<ColumnDef<LogRow>[]>(
    () => [
      {
        accessorKey: "timestamp",
        header: t("logs.time"),
        cell: (ctx) => new Date(ctx.getValue<string>()).toLocaleTimeString(),
      },
      {
        accessorKey: "level",
        header: t("logs.level"),
        cell: (ctx) => {
          const value = ctx.getValue<string>();
          const base =
            value === "error"
              ? "bg-red-500/15 text-red-400"
              : value === "warning"
                ? "bg-amber-500/15 text-amber-300"
                : value === "info"
                  ? "bg-sky-500/15 text-sky-300"
                  : "bg-slate-500/15 text-slate-300";
          return (
            <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${base}`}>
              {(value ?? "").toUpperCase()}
            </span>
          );
        },
      },
      {
        accessorKey: "project_name",
        header: t("logs.project"),
      },
      {
        accessorKey: "source",
        header: t("logs.source"),
      },
      {
        accessorKey: "message",
        header: t("logs.message"),
        cell: (ctx) => (
          <span className="line-clamp-2 text-sm text-slate-100">{ctx.getValue<string>()}</span>
        ),
      },
      {
        accessorKey: "ai_summary",
        header: t("logs.aiSummary", "AI analysis"),
        cell: (ctx) => {
          const value = ctx.getValue<string | null | undefined>();
          if (!value) return <span className="text-slate-500">—</span>;
          return (
            <span className="line-clamp-2 text-xs text-slate-400" title={value}>
              {value}
            </span>
          );
        },
      },
    ],
    [t],
  );

  const table = useReactTable({
    data: items,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getRowId: (row) => String(row.id),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const toggleSeverity = (level: string) => {
    setSeverity((prev) => {
      const next = new Set(prev);
      if (next.has(level)) next.delete(level);
      else next.add(level);
      return next;
    });
  };

  if (isLoading) return <LoadingState label={t("common.loading")} />;
  if (error) return <ErrorState message={getErrorMessage(error)} />;

  return (
    <div className="flex max-h-[calc(100vh-7rem)] min-h-0 flex-col">
      <div className="flex flex-shrink-0 flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t("logs.title", "Logs")}</h1>
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
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("logs.searchPlaceholder", "Search logs…")}
          className="h-9 w-64 rounded-full border border-white/10 bg-black/40 px-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary focus:outline-none"
        />
      </div>

      <div className="flex flex-shrink-0 flex-wrap items-center gap-3 pt-2">
        <div className="flex items-center gap-2">
          {["error", "warning", "info", "debug"].map((lvl) => (
            <button
              key={lvl}
              type="button"
              onClick={() => toggleSeverity(lvl)}
              className={`cursor-pointer rounded-full px-2 py-1 text-xs ${
                severity.has(lvl)
                  ? "bg-primary/30 text-slate-100"
                  : "bg-white/5 text-slate-400 hover:bg-white/10"
              }`}
            >
              {lvl.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col pt-4">
        <div className="min-h-0 flex-1 overflow-auto rounded-2xl border border-white/5 bg-black/30">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-black/60 backdrop-blur">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400"
                    >
                      {header.isPlaceholder ? null : header.column.columnDef.header?.toString()}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  role="button"
                  tabIndex={0}
                  className="cursor-pointer border-t border-white/5 hover:bg-white/5"
                  onClick={() => {
                    const id = Number(row.id);
                    if (Number.isFinite(id)) setSelectedLogId(id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      const id = Number(row.id);
                      if (Number.isFinite(id)) setSelectedLogId(id);
                    }
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2 align-top">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
              {table.getRowModel().rows.length === 0 && (
                <tr>
                  <td className="px-3 py-4 text-center text-sm text-slate-500" colSpan={6}>
                    {t("logs.empty", "No logs for this filter.")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-shrink-0 justify-end py-3">
          {data && data.total > 0 ? (
            <Pagination
              count={Math.ceil(data.total / pageSize)}
              page={page}
              onChange={(_, p) => setPage(p)}
              color="primary"
              showFirstButton
              showLastButton
            />
          ) : (
            <span />
          )}
        </div>
      </div>

      {selectedLogId != null && (
        <LogDetailModal
          logId={selectedLogId}
          detail={logDetail.data}
          loading={logDetail.isLoading}
          error={logDetail.error}
          refetchLogDetail={logDetail.refetch}
          onClose={() => setSelectedLogId(null)}
          onOpenIssue={(id) => {
            setSelectedLogId(null);
            navigate(`/issues/${id}`);
          }}
        />
      )}
    </div>
  );
}

type LogDetailModalProps = {
  logId: number;
  detail: import("./api").LogDetailResponse | undefined;
  loading: boolean;
  error: Error | null;
  refetchLogDetail: () => void;
  onClose: () => void;
  onOpenIssue: (issueId: number) => void;
};

function LogDetailModal({
  logId,
  detail,
  loading,
  error,
  refetchLogDetail,
  onClose,
  onOpenIssue,
}: LogDetailModalProps) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const plan = useBillingPlan();
  const issueId = detail?.related_issue?.id ?? 0;
  const enrichIssue = useEnrichIssue(issueId);
  const createFromLog = useCreateIssueFromLog();
  const llmEnabled = plan.data?.enable_llm_enrichment ?? false;
  const canAnalyze = llmEnabled && detail?.related_issue != null;

  const handleCreateIssueFromLog = () => {
    createFromLog.mutate(logId, {
      onSuccess: (created) => {
        void qc.invalidateQueries({ queryKey: ["logs", "detail", logId] });
        onOpenIssue(created.id);
        onClose();
      },
    });
  };

  const handleAnalyzeWithAi = () => {
    if (!detail?.related_issue) return;
    enrichIssue.mutate({ log_id: logId }, {
      onSuccess: () => {
        void qc.invalidateQueries({ queryKey: ["logs", "detail", logId] });
        refetchLogDetail();
      },
    });
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Log details"
    >
      <div
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-slate-900 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-white/10 bg-slate-900/95 px-4 py-3 backdrop-blur">
          <h2 className="text-lg font-semibold text-slate-100">Log #{logId}</h2>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded p-1 text-slate-400 hover:bg-white/10 hover:text-slate-100"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <div className="p-4 space-y-4">
          {loading && (
            <p className="text-sm text-slate-400">{t("common.loading")}</p>
          )}
          {error && (
            <p className="text-sm text-red-400">{getErrorMessage(error)}</p>
          )}
          {detail && !loading && (
            <>
              <section>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  {t("logs.details")}
                </h3>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                  <dt className="text-slate-500">{t("logs.time")}</dt>
                  <dd className="text-slate-100">{new Date(detail.timestamp).toLocaleString()}</dd>
                  <dt className="text-slate-500">{t("logs.level")}</dt>
                  <dd>
                    <span
                      className={
                        detail.level === "error"
                          ? "text-red-400"
                          : detail.level === "warning"
                            ? "text-amber-300"
                            : "text-slate-300"
                      }
                    >
                      {detail.level.toUpperCase()}
                    </span>
                  </dd>
                  <dt className="text-slate-500">{t("logs.project")}</dt>
                  <dd className="text-slate-100">{detail.project_name}</dd>
                  <dt className="text-slate-500">{t("logs.source")}</dt>
                  <dd className="text-slate-100">{detail.source}</dd>
                </dl>
                <p className="mt-2 whitespace-pre-wrap rounded bg-black/30 p-3 text-sm text-slate-200">
                  {detail.message}
                </p>
                {detail.exception_type && (
                  <p className="mt-1 text-sm text-red-300">Exception: {detail.exception_type}</p>
                )}
                {detail.stacktrace && (
                  <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-3 text-xs text-slate-300">
                    {detail.stacktrace}
                  </pre>
                )}
                {Object.keys(detail.raw_json).length > 0 && (
                  <pre className="mt-2 overflow-x-auto rounded bg-black/40 p-3 text-xs text-slate-400">
                    {JSON.stringify(detail.raw_json, null, 2)}
                  </pre>
                )}
              </section>

              {!detail.related_issue && (
                <section>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {t("logs.relatedIssue")}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={handleCreateIssueFromLog}
                      disabled={createFromLog.isPending}
                      className="cursor-pointer rounded-lg border border-primary/50 bg-primary/20 px-3 py-2 text-sm text-primary hover:bg-primary/30 disabled:opacity-50"
                    >
                      {createFromLog.isPending ? t("common.loading") : t("issues.createFromLog", "Create issue from log")}
                    </button>
                  </div>
                  {createFromLog.isError && (
                    <p className="mt-1 text-sm text-red-400">{getErrorMessage(createFromLog.error)}</p>
                  )}
                </section>
              )}

              {detail.related_issue && (
                <section>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                    {t("logs.relatedIssue")}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => onOpenIssue(detail.related_issue!.id)}
                      className="cursor-pointer rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-primary hover:bg-white/10"
                    >
                      {detail.related_issue.title} → {t("logs.viewIssue")}
                    </button>
                    {canAnalyze && (
                      <button
                        type="button"
                        onClick={handleAnalyzeWithAi}
                        disabled={enrichIssue.isPending}
                        className="cursor-pointer rounded-lg border border-primary/50 bg-primary/20 px-3 py-2 text-sm text-primary hover:bg-primary/30 disabled:opacity-50"
                      >
                        {enrichIssue.isPending ? t("logs.analyzing", "Analyzing…") : t("logs.analyzeWithAi", "Analyze with AI")}
                      </button>
                    )}
                  </div>
                  {enrichIssue.isError && (
                    <p className="mt-1 text-sm text-red-400">{getErrorMessage(enrichIssue.error)}</p>
                  )}
                </section>
              )}

              {detail.enrichment && (
                <section>
                  <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                    AI analysis
                  </h3>
                  <div className="rounded-lg border border-white/10 bg-black/30 p-4 space-y-3 text-sm">
                    <p>
                      <span className="text-slate-500">Model: </span>
                      <span className="text-slate-300">{detail.enrichment.model_name}</span>
                    </p>
                    <p>
                      <span className="text-slate-500">Summary: </span>
                      <span className="text-slate-200">{detail.enrichment.summary}</span>
                    </p>
                    <p>
                      <span className="text-slate-500">Suspected cause: </span>
                      <span className="text-slate-200">{detail.enrichment.suspected_cause}</span>
                    </p>
                    {detail.enrichment.checklist.length > 0 && (
                      <div>
                        <span className="text-slate-500">Checklist: </span>
                        <ul className="mt-1 list-inside list-disc text-slate-200">
                          {detail.enrichment.checklist.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <p className="text-xs text-slate-500">
                      {t("logs.generated")} {new Date(detail.enrichment.created_at).toLocaleString()}
                    </p>
                  </div>
                </section>
              )}

              {detail.related_issue && !detail.enrichment && !canAnalyze && (
                <p className="text-sm text-slate-500">
                  {t("logs.noAiAnalysisHint", "No AI analysis for this issue yet. Enable LLM in Settings to analyze on demand.")}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
