export const tc = (s: number) => {
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${String(m).padStart(2, "0")}:${r.toFixed(1).padStart(4, "0")}`;
};

export const smpte = (s: number, fps = 30) => {
  const f = Math.round(s * fps);
  const ff = f % fps, ts = Math.floor(f / fps);
  const h = Math.floor(ts / 3600), m = Math.floor((ts % 3600) / 60), sec = ts % 60;
  return [h, m, sec, ff].map((n) => String(n).padStart(2, "0")).join(":");
};

export const pct = (x: number | null | undefined, digits = 0) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);

export const segText = (segs: { episode: number; start: number; end: number }[]) =>
  segs.map((s) => `Ep ${s.episode} ${tc(s.start)}–${tc(s.end)}`).join(" + ");

export const FLAG_LABEL: Record<string, string> = {
  weak_hook: "Weak hook",
  late_hook: "Hook after 3 s",
  soft_ending: "Soft ending",
  needs_context: "Needs backstory",
  length_out_of_range: "Length out of range",
  interpolated_timing: "Guessed timestamps",
  spoiler_risk: "Spoiler risk",
  jump_cuts: "Stitched",
  visual_hook: "Visual hook",
  llm_disagrees: "AI judges disagree",
  below_min_score: "Below minimum score",
};

export const KIND_LABEL: Record<string, string> = {
  continuous: "One take",
  montage_episode: "Cold open",
  montage_cross: "Across episodes",
};

export async function copy(text: string) {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

export const store = {
  get<T>(k: string, fallback: T): T {
    try { const v = localStorage.getItem(k); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
  },
  set(k: string, v: unknown) {
    try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ }
  },
};
