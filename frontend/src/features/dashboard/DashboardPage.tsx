import { Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

export const DashboardPage = () => {
  const { t } = useTranslation();
  return <Typography variant="h5">{t("dashboard.title")}</Typography>;
};

