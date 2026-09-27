// Response shapes mirroring the Parallax FastAPI models (parallax_research.api.models).
// Field names match the API exactly so responses deserialize without transformation.

export interface ModelPrediction {
  ts_ns: number;
  p_model: number;
  p_market: number;
  edge: number;
  ev: number;
}

export interface Market {
  market_id: string;
  platform: string;
  question_text: string;
  close_time: string;
  resolved_outcome: number | null;
  probability: number | null;
  volume_24h: number | null;
  last_updated_ns: number | null;
  prediction: ModelPrediction | null;
}

export type SignalType = "logical_constraint" | "cross_source_divergence";

export interface ArbitrageSignal {
  id: number;
  type: SignalType;
  market_refs: string[];
  edge: number;
  detected_at: string;
  details: Record<string, unknown>;
}

export interface PaginatedSignals {
  items: ArbitrageSignal[];
  total: number;
  limit: number;
  offset: number;
}

export interface Report {
  name: string;
  content: string;
}

export interface ReplayPoint {
  ts_ns: number;
  probability: number;
}

export interface Replay {
  market_id: string;
  points: ReplayPoint[];
}
