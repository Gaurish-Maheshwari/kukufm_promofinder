// Mirrors RunResult.to_dict() in promo_engine/pipeline.py

export interface Segment { episode: number; start: number; end: number; first_beat: number; last_beat: number }

export interface TranscriptLine {
  segment: number; episode: number; start: number; end: number; kind: string;
  speaker: string | null; text: string; manner: string | null; timed: boolean;
  is_hook: boolean; is_cliff: boolean; intensity: number;
}

export interface Variant { episode: number; start: number; end: number; duration: number; first_beat: number; last_beat: number }

export interface Promo {
  id: string; rank: number; post_order: number; post_rationale: string;
  segments: Segment[]; kind: "continuous" | "montage_episode" | "montage_cross";
  score: number; heuristic_score: number; llm_score: number | null;
  breakdown: Record<string, number>;
  hook: { text: string; type: string; type_key: string | null; at: number; episode: number; timestamp: number; score: number; llm?: string };
  cliffhanger: { text: string; type: string; type_key: string | null; episode: number; timestamp: number; score: number; llm?: string };
  why: string; tropes: string[]; flags: string[];
  variants: Record<string, Variant>; transcript: TranscriptLine[]; characters: string[];
  source: string; duration: number; episodes: number[];
  llm_notes: { standalone_reasons?: string[]; refined?: string | null; red_flags?: string[]; edit?: string; overall?: number };
}

export interface EpisodeInfo { number: number; title: string; source: string; duration: number; beats: number; scenes: number; parse_confidence: number; warnings: string[] }

export interface ComparisonRow {
  manual: { id: string; segments: { episode: number; start: number; end: number }[]; hook: string; cliffhanger: string; notes: string; duration: number };
  status: "matched" | "partial" | "missed";
  ai: { id: string; rank: number; score: number; segments: { episode: number; start: number; end: number }[] } | null;
  iou: number; coverage: number; start_delta: number | null; end_delta: number | null; hook_agrees: boolean | null; diagnosis: string;
}

export interface Comparison {
  summary: {
    manual_total: number; matched: number; partial: number; missed: number; recall: number; recall_incl_partial: number;
    precision_vs_manual: number; recall_at_k: Record<string, number>; mean_iou_matched: number | null;
    mean_abs_start_error_s: number | null; mean_abs_end_error_s: number | null; hook_agreement: number | null;
    episode_coverage: number | null; ai_new_finds: number; headline: string;
  };
  rows: ComparisonRow[];
  new_finds: { id: string; rank: number; score: number; episodes: number[]; segments: { episode: number; start: number; end: number }[]; hook: string; why: string }[];
}

export interface RunResult {
  run_id: string; created_at: string; version: string;
  show: { title: string; episodes: EpisodeInfo[]; characters: Record<string, { lines: number; first_episode: number; main: boolean }>; total_minutes: number };
  settings: { platform: string; min_seconds: number; max_seconds: number; target_seconds: number; top_k: number; weights: Record<string, number>; weights_source: string; llm: LLMInfo };
  promos: Promo[];
  posting_plan: { post_order: number; id: string; rank: number; rationale: string }[];
  heatmap: { episode: number; bin_seconds: number; values: number[]; duration: number }[];
  quality: {
    flag_counts: Record<string, { count: number; share: number; meaning: string }>;
    clean_promos: number; clean_share: number;
    review_first: { id: string; rank: number; flags: string[] }[];
    parse_issues: { episode: number; confidence: number; warnings: string[] }[];
    known_failure_modes: { mode: string; detail: string }[];
  };
  metrics: Record<string, any>;
  comparison: Comparison | null;
  warnings: string[];
}

export interface LLMInfo { enabled: boolean; provider: string | null; model: string | null; key?: string; free_tier?: boolean; reason?: string }

export interface Health { ok: boolean; version: string; serverless: boolean; local_paths: boolean; max_upload_mb: number; llm: LLMInfo }

export interface Options {
  platform: "any" | "tiktok" | "reels" | "shorts";
  top_k: number; min_score: number; max_per_episode: number; enable_montages: boolean;
  use_llm: boolean; llm_key: string; show_title: string;
}
