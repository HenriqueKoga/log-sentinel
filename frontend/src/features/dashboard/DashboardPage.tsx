import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, LineChart, Line } from "recharts";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { getErrorMessage } from "../../shared/api/errors";
import { useCreditBar } from "../billing/api";
import { useDashboardMetrics } from "./api";
import { useIssues } from "../issues/api";
import { useProjects } from "../projects/api";
import { formatNumber } from "../../shared/utils/format";

const CHART_PERIODS = [
  { minutes: 30, label: "30m" },
  { minutes: 60, label: "1h" },
  { minutes: 360, label: "6h" },
  { minutes: 1440, label: "24h" },
] as const;

export const DashboardPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [chartMinutes, setChartMinutes] = useState(30);

  const projects = useProjects();
  const issues = useIssues({ page: 1, pageSize: 50 });
  const creditBar = useCreditBar();
  const metrics = useDashboardMetrics(chartMinutes);

  const loading = projects.isLoading || issues.isLoading || creditBar.isLoading;
  const error = projects.error ?? issues.error ?? creditBar.error;

  const logVolumeData = metrics.data?.log_volume ?? [];
  const errorRateData = metrics.data?.error_rate ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{t("dashboard.title")}</h1>
      </div>

      {loading && <LoadingState label={t("common.loading")} />}
      {error && <ErrorState message={getErrorMessage(error)} />}

      <div className="grid gap-4 md:grid-cols-4">
        <button
          type="button"
          onClick={() => navigate("/projects")}
          className="cursor-pointer rounded-2xl border border-white/5 bg-gradient-to-br from-white/10 to-white/0 p-4 text-left transition-colors hover:border-white/10"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400">{t("dashboard.projects")}</p>
          <p className="mt-2 text-2xl font-semibold">{formatNumber(projects.data?.length ?? 0)}</p>
          <p className="mt-2 text-xs text-primary">{t("dashboard.manageProjects")}</p>
        </button>
        <button
          type="button"
          onClick={() => navigate("/issues")}
          className="cursor-pointer rounded-2xl border border-white/5 bg-gradient-to-br from-red-500/10 to-white/0 p-4 text-left transition-colors hover:border-white/10"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400">{t("dashboard.recentIssues")}</p>
          <p className="mt-2 text-2xl font-semibold text-red-400">
            {formatNumber(issues.data?.items?.length ?? 0)}
          </p>
          <p className="mt-1 text-xs text-slate-400">{t("dashboard.recentIssuesHint")}</p>
        </button>
        <button
          type="button"
          onClick={() => navigate("/billing")}
          className="cursor-pointer rounded-2xl border border-white/5 bg-gradient-to-br from-amber-500/10 to-white/0 p-4 text-left transition-colors hover:border-white/10"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400">{t("dashboard.credits")}</p>
          {creditBar.data ? (
            <>
              <p className="mt-2 text-lg font-semibold text-amber-300">
                {creditBar.data.credits_used.toFixed(1)}{" "}
                <span className="text-sm font-normal text-slate-500">
                  / {formatNumber(creditBar.data.credits_limit)}
                </span>
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                <div
                  className={`h-full rounded-full transition-all ${
                    creditBar.data.percentage >= 90
                      ? "bg-red-500"
                      : creditBar.data.percentage >= 70
                        ? "bg-amber-400"
                        : "bg-emerald-400"
                  }`}
                  style={{ width: `${Math.min(creditBar.data.percentage, 100)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {creditBar.data.percentage.toFixed(1)}% {t("dashboard.ofLimit")}
              </p>
            </>
          ) : (
            <p className="mt-2 text-2xl font-semibold text-amber-300">—</p>
          )}
        </button>
        <button
          type="button"
          onClick={() => navigate("/alerts")}
          className="cursor-pointer rounded-2xl border border-white/5 bg-gradient-to-br from-accent/20 to-white/0 p-4 text-left transition-colors hover:border-white/10"
        >
          <p className="text-xs uppercase tracking-wide text-slate-400">{t("dashboard.alerts")}</p>
          <p className="mt-2 text-2xl font-semibold text-accent-400">—</p>
          <p className="mt-1 text-xs text-slate-400">{t("dashboard.alertsHint")}</p>
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-white/5 bg-black/30 p-4 lg:col-span-2">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-100">{t("dashboard.logVolume")}</span>
            <div className="flex gap-1">
              {CHART_PERIODS.map(({ minutes, label }) => (
                <button
                  key={minutes}
                  type="button"
                  onClick={() => setChartMinutes(minutes)}
                  className={`cursor-pointer rounded px-2 py-1 text-xs ${
                    chartMinutes === minutes
                      ? "bg-primary/40 text-slate-100"
                      : "bg-white/5 text-slate-400 hover:bg-white/10"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={logVolumeData}>
              <defs>
                <linearGradient id="logVolume" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="ts" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip
                contentStyle={{ backgroundColor: "#020617", borderRadius: 8, border: "1px solid #1e293b" }}
              />
              <Area type="monotone" dataKey="value" stroke="#7C3AED" fill="url(#logVolume)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-100">{t("dashboard.errorRate")}</span>
            <span className="text-xs text-slate-500">
              {CHART_PERIODS.find((p) => p.minutes === chartMinutes)?.label ?? chartMinutes}m %
            </span>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={errorRateData}>
              <XAxis dataKey="ts" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip
                contentStyle={{ backgroundColor: "#020617", borderRadius: 8, border: "1px solid #1e293b" }}
              />
              <Line type="monotone" dataKey="value" stroke="#f97373" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

