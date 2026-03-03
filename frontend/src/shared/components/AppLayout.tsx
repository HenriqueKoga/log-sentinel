import { AppBar, Box, Container, Toolbar, Typography } from "@mui/material";
import { Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";

export const AppLayout = () => {
  const { t } = useTranslation();

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div">
            {t("app.title")}
          </Typography>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 3, flexGrow: 1 }}>
        <Outlet />
      </Container>
    </Box>
  );
};

