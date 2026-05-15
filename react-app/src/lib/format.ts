export function requireValue(value: string, label: string): void {
  if (!value.trim()) {
    throw new Error(`${label} is required`);
  }
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return String(value);
  }

  return dt.toLocaleDateString();
}

export function formatTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }

  return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return String(value);
  }

  return dt.toLocaleString();
}

export function formatHours(value: number | string | null | undefined): string {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n)) {
    return "0";
  }
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

export function todayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function buildTimeBlocks(intervalMinutes: number): string[] {
  const slots = (24 * 60) / intervalMinutes;
  const blocks: string[] = [];

  for (let i = 0; i < slots; i += 1) {
    const minuteOfDay = i * intervalMinutes;
    const hour = String(Math.floor(minuteOfDay / 60)).padStart(2, "0");
    const minute = String(minuteOfDay % 60).padStart(2, "0");
    blocks.push(`${hour}:${minute}`);
  }

  return blocks;
}

export function normalizeSkillIds(ids: string[]): string[] {
  return [...new Set(ids.map((id) => String(id)))].sort();
}
