export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "-";
  const d = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return "-";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(d);
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "-";
  return new Intl.NumberFormat(undefined).format(n);
}

