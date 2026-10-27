function parseBackendTime(iso: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

/** Backend timestamps are UTC, often serialized without Z. Show them in local time. */
export function formatLocal(iso: string): string {
  const instant = parseBackendTime(iso);
  if (Number.isNaN(instant.getTime())) {
    return iso;
  }
  return instant.toLocaleString();
}

export function formatRelative(iso: string): string {
  const instant = parseBackendTime(iso);
  if (Number.isNaN(instant.getTime())) return iso;

  const seconds = Math.round((instant.getTime() - Date.now()) / 1000);
  const ranges: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["week", 604_800],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, size] of ranges) {
    if (Math.abs(seconds) >= size) {
      return formatter.format(Math.round(seconds / size), unit);
    }
  }
  return formatter.format(seconds, "second");
}
