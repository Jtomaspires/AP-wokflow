/** Backend timestamps are UTC, often serialized without Z. Show them in local time. */
export function formatLocal(iso: string): string {
  const hasZone = /(?:Z|[+-]\d{2}:\d{2})$/.test(iso);
  const instant = new Date(hasZone ? iso : `${iso}Z`);
  if (Number.isNaN(instant.getTime())) {
    return iso;
  }
  return instant.toLocaleString();
}
