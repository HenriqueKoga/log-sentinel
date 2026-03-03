import { PropsWithChildren } from "react";
import { ThemeProvider as MuiThemeProvider, createTheme } from "@mui/material/styles";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1976d2",
    },
    secondary: {
      main: "#9c27b0",
    },
  },
});

export const ThemeProvider = ({ children }: PropsWithChildren) => {
  return <MuiThemeProvider theme={theme}>{children}</MuiThemeProvider>;
};

