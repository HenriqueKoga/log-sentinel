import i18n from "i18next";
import React, { PropsWithChildren } from "react";
import { initReactI18next, I18nextProvider } from "react-i18next";
import en from "./locales/en/common.json";
import ptBR from "./locales/pt-BR/common.json";

const defaultLang = import.meta.env.VITE_I18N_DEFAULT_LANG || "pt-BR";

i18n.use(initReactI18next).init({
  resources: {
    en: { common: en },
    "pt-BR": { common: ptBR },
  },
  lng: defaultLang,
  fallbackLng: ["pt-BR", "en"],
  ns: ["common"],
  defaultNS: "common",
  interpolation: { escapeValue: false },
});

export const I18nProvider = ({ children }: PropsWithChildren) => {
  return React.createElement(I18nextProvider, { i18n }, children);
};

