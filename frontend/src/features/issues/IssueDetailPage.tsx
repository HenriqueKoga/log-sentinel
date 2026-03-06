import { ArrowBack as ArrowBackIcon } from "@mui/icons-material";
import { Alert, Box, Button, Chip, Divider, MenuItem, Paper, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime, formatNumber } from "../../shared/utils/format";
import { useBillingPlan } from "../billing/api";
import {
  IssueSeverity,
  IssueStatus,
  useEnrichIssue,
  useIssue,
  useIssueOccurrences,
  useReopenIssue,
  useResolveIssue,
  useSnoozeIssue,
} from "./api";

function severityColor(s: IssueSeverity): "default" | "warning" | "error" {
  if (s === "critical" || s === "high") return "error";
  if (s === "medium") return "warning";
  return "default";
}

function statusColor(s: IssueStatus): "default" | "success" | "warning" {
  if (s === "resolved") return "success";
  if (s === "snoozed") return "warning";
  return "default";
}

export function IssueDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const issueId = Number(useParams().issueId);
  const issue = useIssue(issueId);
  const plan = useBillingPlan();
  const llmEnabled = plan.data?.enable_llm_enrichment ?? false;
  const enrichIssue = useEnrichIssue(issueId);

  const [range, setRange] = useState<"24h" | "7d" | "30d">("24h");
  const occurrences = useIssueOccurrences(issueId, range);

  const resolve = useResolveIssue(issueId);
  const reopen = useReopenIssue(issueId);
  const snooze = useSnoozeIssue(issueId);
  const [snoozeMinutes, setSnoozeMinutes] = useState(60);

  const handleAnalyzeWithAi = () => {
    if (!llmEnabled || enrichIssue.isPending) return;
    enrichIssue.mutate(undefined, {
      onSuccess: () => {
        void issue.refetch();
      },
    });
  };

  if (issue.isLoading) return <LoadingState label={t("common.loading")} />;
  if (issue.error) return <ErrorState message={getErrorMessage(issue.error)} />;
  if (!issue.data) return <ErrorState message="ISSUE_NOT_FOUND" />;

  const it = issue.data;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        minHeight: 0,
        flex: 1,
        overflowY: "auto",
      }}
    >
      <Button
        startIcon={<ArrowBackIcon />}
        onClick={() => navigate("/issues")}
        sx={{ alignSelf: "flex-start", mb: 2, cursor: "pointer" }}
      >
        {t("issues.backToList", "Back to issues")}
      </Button>
      <Box sx={{ display: "flex", alignItems: "flex-start", gap: 2, mb: 2 }}>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5">{it.title}</Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            <Chip size="small" color={severityColor(it.severity)} label={`${t("issues.severity")}: ${it.severity}`} />
            <Chip size="small" color={statusColor(it.status)} label={`${t("issues.status")}: ${it.status}`} />
            {it.snoozed_until && (
              <Chip size="small" label={`${t("issues.snoozedUntil")}: ${formatDateTime(it.snoozed_until)}`} />
            )}
          </Stack>
        </Box>
        <Stack direction="row" spacing={1}>
          {llmEnabled && (
            <Button
              variant="contained"
              color="primary"
              disabled={enrichIssue.isPending}
              onClick={handleAnalyzeWithAi}
              sx={{ cursor: "pointer" }}
            >
              {enrichIssue.isPending
                ? t("logs.analyzing", "Analyzing…")
                : t("logs.analyzeWithAi", "Analyze with AI")}
            </Button>
          )}
          <Button
            color="success"
            variant="outlined"
            disabled={resolve.isPending || it.status === "resolved"}
            onClick={async () => resolve.mutateAsync()}
            sx={{ cursor: "pointer" }}
          >
            {t("issues.resolve")}
          </Button>
          <Button
            color="info"
            variant="outlined"
            disabled={reopen.isPending || it.status === "open"}
            onClick={async () => reopen.mutateAsync()}
            sx={{ cursor: "pointer" }}
          >
            {t("issues.reopen")}
          </Button>
        </Stack>
      </Box>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t("issues.firstSeen")}
            </Typography>
            <Typography>{formatDateTime(it.first_seen)}</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t("issues.lastSeen")}
            </Typography>
            <Typography>{formatDateTime(it.last_seen)}</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t("issues.total")}
            </Typography>
            <Typography>{formatNumber(it.total_count)}</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {t("issues.priority")}
            </Typography>
            <Typography>{it.priority_score.toFixed(2)}</Typography>
          </Box>
        </Stack>
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
          <Typography variant="h6">{t("issues.occurrences")}</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <TextField
            select
            size="small"
            label={t("issues.range")}
            value={range}
            onChange={(e) => setRange(e.target.value as "24h" | "7d" | "30d")}
            sx={{ width: 160 }}
          >
            <MenuItem value="24h">{t("issues.range24h")}</MenuItem>
            <MenuItem value="7d">{t("issues.range7d")}</MenuItem>
            <MenuItem value="30d">{t("issues.range30d")}</MenuItem>
          </TextField>
        </Box>

        {occurrences.isLoading && <LoadingState />}
        {occurrences.error && <ErrorState message={getErrorMessage(occurrences.error)} />}
        {occurrences.data && (
          <Box sx={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={occurrences.data.points}>
                <XAxis dataKey="bucket_start" hide />
                <YAxis width={40} />
                <Tooltip formatter={(v) => formatNumber(Number(v))} labelFormatter={(l) => formatDateTime(String(l))} />
                <Line type="monotone" dataKey="count" stroke="#7aa2ff" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </Box>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 1 }}>
          <Typography variant="h6">{t("issues.snooze")}</Typography>
          <Box sx={{ flexGrow: 1 }} />
          <TextField
            size="small"
            type="number"
            label={t("issues.snoozeMinutes")}
            value={snoozeMinutes}
            onChange={(e) => setSnoozeMinutes(Number(e.target.value))}
            sx={{ width: 180 }}
          />
          <Button variant="contained" disabled={snooze.isPending} onClick={async () => snooze.mutateAsync(snoozeMinutes)} sx={{ cursor: "pointer" }}>
            {t("issues.snoozeAction")}
          </Button>
        </Box>
        {snooze.error && <ErrorState message={getErrorMessage(snooze.error)} />}
      </Paper>

      {it.enrichment && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">{t("issues.enrichment")}</Typography>
          <Typography color="text.secondary" sx={{ mb: 1 }}>
            {it.enrichment.model_name} • {formatDateTime(it.enrichment.created_at)}
          </Typography>
          <Divider sx={{ mb: 2 }} />
          <Typography sx={{ whiteSpace: "pre-wrap" }}>{it.enrichment.summary}</Typography>
          <Typography variant="subtitle2" sx={{ mt: 2 }}>
            {t("issues.suspectedCause")}
          </Typography>
          <Typography sx={{ whiteSpace: "pre-wrap" }}>{it.enrichment.suspected_cause}</Typography>
        </Paper>
      )}

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t("issues.samples")}
        </Typography>
        {it.samples.length === 0 && <Alert severity="info">{t("issues.noSamples")}</Alert>}
        {it.samples.map((s, idx) => (
          <Box key={idx} sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {formatDateTime(s.received_at)} • {s.level}
              {s.exception_type ? ` • ${s.exception_type}` : ""}
            </Typography>
            <Typography sx={{ whiteSpace: "pre-wrap" }}>{s.message}</Typography>
            {s.stacktrace && (
              <Paper variant="outlined" sx={{ p: 1.5, mt: 1, bgcolor: "background.default" }}>
                <Typography component="pre" sx={{ m: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>
                  {s.stacktrace}
                </Typography>
              </Paper>
            )}
            <Divider sx={{ mt: 2 }} />
          </Box>
        ))}
      </Paper>
    </Box>
  );
}

