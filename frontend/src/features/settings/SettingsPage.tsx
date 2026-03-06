import { Box, Paper, Switch, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { ErrorState, LoadingState } from "../../shared/components/States";
import { getErrorMessage } from "../../shared/api/errors";
import { useBillingPlan, useUpdateSettings } from "../billing/api";

export function SettingsPage() {
  const { t } = useTranslation();
  const plan = useBillingPlan();
  const updateSettings = useUpdateSettings();

  const handleLlmToggle = (event: React.ChangeEvent<HTMLInputElement>) => {
    updateSettings.mutate({ enable_llm_enrichment: event.target.checked });
  };

  if (plan.isLoading) return <LoadingState label={t("common.loading")} />;
  if (plan.error) return <ErrorState message={getErrorMessage(plan.error)} />;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 2 }}>
        {t("settings.title", "Settings")}
      </Typography>

      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ mb: 2 }}>
          {t("settings.llmSection", "AI / LLM")}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Switch
            checked={plan.data?.enable_llm_enrichment ?? false}
            onChange={handleLlmToggle}
            disabled={updateSettings.isPending}
            color="primary"
          />
          <Box>
            <Typography>{t("settings.enableLlm", "Enable LLM for log analysis")}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t("settings.enableLlmHint", "Use AI to analyze issues and suggest causes. Uses credits when enabled.")}
            </Typography>
          </Box>
        </Box>
        {updateSettings.isError && (
          <Typography color="error" sx={{ mt: 1 }}>
            {getErrorMessage(updateSettings.error)}
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
