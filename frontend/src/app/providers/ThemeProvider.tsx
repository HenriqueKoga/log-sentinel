import { PropsWithChildren, useMemo } from "react";
import { ThemeProvider as MuiThemeProvider, createTheme } from "@mui/material/styles";
import { ThemeModeContext, type ThemeMode } from "./themeModeContext";

export const ThemeProvider = ({ children }: PropsWithChildren) => {
  const mode: ThemeMode = "dark";

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          mode,
          primary: { main: "#7aa2ff" },
          secondary: { main: "#bda6ff" },
        },
        shape: { borderRadius: 10 },
      }),
    [],
  );

  const value = useMemo(() => ({ mode, toggle: () => {} }), []);

  return (
    <ThemeModeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>{children}</MuiThemeProvider>
    </ThemeModeContext.Provider>
  );
};

