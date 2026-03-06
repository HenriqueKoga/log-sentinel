import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { AuthProvider } from "./app/providers/AuthProvider";
import { QueryProvider } from "./app/providers/QueryProvider";
import { ThemeProvider } from "./app/providers/ThemeProvider";
import { I18nProvider } from "./i18n";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <I18nProvider>
      <AuthProvider>
        <QueryProvider>
          <ThemeProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ThemeProvider>
        </QueryProvider>
      </AuthProvider>
    </I18nProvider>
  </React.StrictMode>,
);

