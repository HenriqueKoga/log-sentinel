import {
  Box,
  LinearProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime, formatNumber } from "../../shared/utils/format";
import { useBillingPlan, useBillingUsage, useCreditBar, useLlmUsageSummary } from "./api";

function barColor(pct: number): "success" | "warning" | "error" {
  if (pct >= 90) return "error";
  if (pct >= 70) return "warning";
  return "success";
}

export function BillingPage() {
  const { t } = useTranslation();
  const plan = useBillingPlan();
  const usage = useBillingUsage();
  const llmUsage = useLlmUsageSummary();
  const creditBar = useCreditBar();

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {t("billing.title")}
      </Typography>

      {(plan.isLoading || usage.isLoading || creditBar.isLoading) && (
        <LoadingState label={t("common.loading")} />
      )}
      {plan.error && <ErrorState message={getErrorMessage(plan.error)} />}
      {usage.error && <ErrorState message={getErrorMessage(usage.error)} />}

      {plan.data && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">{t("billing.plan")}</Typography>
          <Typography color="text.secondary">
            {t("billing.planType")}: {t(`billing.planType_${plan.data.plan_type}` as const, plan.data.plan_type)} •{" "}
            {t("billing.status")}: {t(`billing.status_${plan.data.status}` as const, plan.data.status)}
          </Typography>
          <Typography color="text.secondary">
            {t("billing.startsAt")}: {formatDateTime(plan.data.starts_at)}
          </Typography>
          <Typography color="text.secondary">
            {t("billing.monthlyCreditsLimit", "Limite mensal")}: {formatNumber(plan.data.monthly_credits_limit)}{" "}
            {t("billing.credits", "créditos")}
          </Typography>
        </Paper>
      )}

      {(usage.data || creditBar.data) && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">{t("billing.usage")}</Typography>

          {usage.data && (
            <>
              <Typography color="text.secondary">
                {t("billing.periodStart")}: {formatDateTime(usage.data.period_start)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {t("billing.eventsIngested", "Events")}: {formatNumber(usage.data.events_ingested)}
                {" · "}
                {t("billing.llmEnrichments", "LLM analyses")}: {formatNumber(usage.data.llm_enrichments)}
              </Typography>
            </>
          )}

          {creditBar.data && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                {t("billing.creditUsage", "Uso de créditos")}
              </Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Box sx={{ flexGrow: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={creditBar.data.percentage}
                    color={barColor(creditBar.data.percentage)}
                    sx={{ height: 14, borderRadius: 1 }}
                  />
                </Box>
                <Typography variant="body2" sx={{ whiteSpace: "nowrap", minWidth: 100, textAlign: "right" }}>
                  {creditBar.data.credits_used.toFixed(2)} / {formatNumber(creditBar.data.credits_limit)}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: "block" }}>
                {creditBar.data.percentage.toFixed(1)}%{" "}
                {t("billing.ofMonthlyLimit", "do limite mensal")}
              </Typography>
            </Box>
          )}
        </Paper>
      )}

      {llmUsage.data && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" sx={{ mb: 1 }}>
            {t("billing.llmUsage", "Uso de LLM")}
          </Typography>
          <Typography>
            {t("billing.totalTokens", "Tokens")}:{" "}
            {formatNumber(llmUsage.data.totals.input_tokens + llmUsage.data.totals.output_tokens)}
            {" · "}
            {t("billing.totalCost", "Custo")}: ${llmUsage.data.totals.total_cost.toFixed(4)}
            {" · "}
            {t("billing.creditsUsed", "Créditos")}: {llmUsage.data.totals.credits_used.toFixed(2)}
          </Typography>

          {llmUsage.data.by_model.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t("billing.byModel", "Por modelo")}
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>{t("billing.model", "Modelo")}</TableCell>
                      <TableCell align="right">Input</TableCell>
                      <TableCell align="right">Output</TableCell>
                      <TableCell align="right">{t("billing.cost", "Custo")}</TableCell>
                      <TableCell align="right">{t("billing.credits", "Créditos")}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {llmUsage.data.by_model.map((m) => (
                      <TableRow key={m.model_id}>
                        <TableCell>{m.display_name}</TableCell>
                        <TableCell align="right">{formatNumber(m.input_tokens)}</TableCell>
                        <TableCell align="right">{formatNumber(m.output_tokens)}</TableCell>
                        <TableCell align="right">${m.total_cost.toFixed(4)}</TableCell>
                        <TableCell align="right">{m.credits_used.toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {llmUsage.data.by_feature.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t("billing.byFeature", "Por feature")}
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Feature</TableCell>
                      <TableCell align="right">Input</TableCell>
                      <TableCell align="right">Output</TableCell>
                      <TableCell align="right">{t("billing.cost", "Custo")}</TableCell>
                      <TableCell align="right">{t("billing.credits", "Créditos")}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {llmUsage.data.by_feature.map((f) => (
                      <TableRow key={f.feature}>
                        <TableCell>{f.feature}</TableCell>
                        <TableCell align="right">{formatNumber(f.input_tokens)}</TableCell>
                        <TableCell align="right">{formatNumber(f.output_tokens)}</TableCell>
                        <TableCell align="right">${f.total_cost.toFixed(4)}</TableCell>
                        <TableCell align="right">{f.credits_used.toFixed(2)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}
