import { CssBaseline } from "@mui/material";
import { AppRoutes } from "./routes";
import { RouteTransitionLoader } from "../shared/components/RouteTransitionLoader";

export const App = () => {
  return (
    <>
      <CssBaseline />
      <RouteTransitionLoader />
      <AppRoutes />
    </>
  );
};

