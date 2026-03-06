import axios from "axios";

export type ApiErrorCode = string;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

export function getErrorCode(err: unknown): ApiErrorCode | null {
  if (!axios.isAxiosError(err)) return null;
  const data: unknown = err.response?.data;
  if (!isRecord(data)) return null;
  const detail = data["detail"];
  if (!isRecord(detail)) return null;
  const code = detail["code"];
  return typeof code === "string" ? code : null;
}

export function getErrorMessage(err: unknown): string {
  const code = getErrorCode(err);
  if (code) return code;
  if (err instanceof Error && typeof err.message === "string") return err.message;
  return "UNKNOWN_ERROR";
}

