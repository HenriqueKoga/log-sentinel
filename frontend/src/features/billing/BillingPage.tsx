import { Box, LinearProgress, Paper, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { getErrorMessage } from "../../shared/api/errors";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { formatDateTime, formatNumber } from "../../shared/utils/format";
import { useBillingPlan, useBillingUsage } from "./api";

export function BillingPage() {
  const { t } = useTranslation();
  const plan = useBillingPlan();
  const usage = useBillingUsage();

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {t("billing.title")}
      </Typography>

      {(plan.isLoading || usage.isLoading) && <LoadingState label={t("common.loading")} />}
      {plan.error && <ErrorState message={getErrorMessage(plan.error)} />}
      {usage.error && <ErrorState message={getErrorMessage(usage.error)} />}

      {plan.data && (
        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6">{t("billing.plan")}</Typography>
          <Typography color="text.secondary">
            {t("billing.planType")}: {t(`billing.planType_${plan.data.plan_type}` as const, plan.data.plan_type)} • {t("billing.status")}: {t(`billing.status_${plan.data.status}` as const, plan.data.status)}
          </Typography>
          <Typography color="text.secondary">
            {t("billing.startsAt")}: {formatDateTime(plan.data.starts_at)}
          </Typography>
          <Typography color="text.secondary">
            {t("billing.limit")}: {plan.data.limit === null ? t("billing.unlimited") : formatNumber(plan.data.limit)}
          </Typography>
        </Paper>
      )}

      {usage.data && (
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="h6">{t("billing.usage")}</Typography>
          <Typography color="text.secondary">
            {t("billing.periodStart")}: {formatDateTime(usage.data.period_start)}
          </Typography>
          <Typography sx={{ mt: 1 }}>
            {t("billing.creditsUsed", "Credits used")}: {formatNumber(usage.data.used)}
            {usage.data.limit !== null ? ` / ${formatNumber(usage.data.limit)}` : ""}
          </Typography>
          {(usage.data.events_ingested > 0 || usage.data.llm_enrichments > 0) && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {t("billing.eventsIngested", "Events")}: {formatNumber(usage.data.events_ingested)}
              {" · "}
              {t("billing.llmEnrichments", "LLM analyses")}: {formatNumber(usage.data.llm_enrichments)}
            </Typography>
          )}
          {usage.data.limit !== null && (
            <Box sx={{ mt: 1 }}>
              <LinearProgress
                variant="determinate"
                value={Math.min(100, (usage.data.used / Math.max(1, usage.data.limit)) * 100)}
              />
            </Box>
          )}
        </Paper>
      )}
    </Box>
  );
}

