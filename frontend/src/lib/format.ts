export function formatPct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSeason(startYear: number): string {
  const next = String((startYear + 1) % 100).padStart(2, "0");
  return `${startYear}-${next}`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso.length <= 10 ? `${iso}T00:00:00Z` : iso);
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
