import { TFunction } from "i18next";

const AUTH_ERROR_CODES = {
  AUTH_INVALID_CREDENTIALS: "invalidCredentials",
  AUTH_EMAIL_EXISTS: "emailExists",
} as const;

type AuthErrorCode = keyof typeof AUTH_ERROR_CODES;

export function getAuthErrorMessage(
  response: Response,
  body: { detail?: unknown },
  t: TFunction,
): string {
  const detail = body?.detail;
  if (Array.isArray(detail)) {
    const isPasswordTooShort = detail.some(
      (item: unknown) =>
        Array.isArray((item as { loc?: string[] }).loc) &&
        (item as { loc: string[] }).loc.includes("password") &&
        ((item as { type?: string }).type?.includes("min_length") ||
          String((item as { msg?: string }).msg ?? "").toLowerCase().includes("at least")),
    );
    if (isPasswordTooShort) return t("auth.errorPasswordTooShort");
    return t("auth.errorValidation");
  }
  if (detail && typeof detail === "object" && "code" in detail) {
    const code = (detail as { code: string }).code;
    const authKey = AUTH_ERROR_CODES[code as AuthErrorCode];
    if (authKey) {
      return t(`auth.${authKey}`);
    }
  }
  return t("auth.errorGeneric");
}
