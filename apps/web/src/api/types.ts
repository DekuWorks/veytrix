export type HealthResponse = {
  status: "ok";
};

export type ReadyResponse = {
  status: "ready" | "unavailable";
  database: "up" | "down";
};

export type DiagnosticsResponse = {
  service: "veytrix-api";
  env: "local";
  trading_mode: "paper";
  live_broker: "disabled";
  auth: "not_configured";
  sample_data: true;
  execution_permitted: false;
  daily_weekly_stops_enforced: false;
  rate_limit: "process_local";
  csrf: "not_implemented";
  versions: {
    api: "0.1.0";
    python: string;
  };
};

export type BarResponse = {
  bar_start: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
};

export type BarsResponse = {
  symbol: string;
  venue: string;
  asset_type: string;
  currency: string;
  source_id: string;
  interval: "1d" | "1m";
  seed: number | null;
  synthetic: boolean;
  calendar_note: string;
  disclaimer: string;
  last_close: string | null;
  previous_close: string | null;
  change: string | null;
  change_percent: string | null;
  retrieved_at: string | null;
  source_url: string | null;
  bars: BarResponse[];
};

export const COINBASE_PRODUCTS = ["BTC-USD", "ETH-USD", "SOL-USD"] as const;

export type CoinbaseProduct = (typeof COINBASE_PRODUCTS)[number];

export type TickerResponse = {
  symbol: CoinbaseProduct;
  venue: "COINBASE";
  source_id: "coinbase-exchange";
  synthetic: false;
  price: string;
  bid: string;
  ask: string;
  size: string;
  volume: string;
  trade_time: string;
  trade_id: number;
  retrieved_at: string;
  disclaimer: string;
};

export type SizeResponse = {
  symbol: CoinbaseProduct;
  shares: number;
  binding_constraint: "risk" | "allocation" | "both" | "none";
  stop_distance: string;
  planned_risk_amount: string;
  risk_budget: string;
  notional: string;
  account_equity: string;
  entry_price: string;
  stop_price: string;
  risk_fraction: string;
  max_allocation_fraction: string;
  daily_loss_stop_fraction: string;
  weekly_loss_stop_fraction: string;
  policy_name: string;
  warning: string | null;
  note: string;
  execution_permitted: false;
  order_submitted: false;
  daily_stop_enforced: false;
  weekly_stop_enforced: false;
};

export type PaperPositionResponse = {
  id: string;
  symbol: CoinbaseProduct;
  entry: string;
  stop: string;
  shares: number;
  notional: string;
  planned_risk: string;
  binding_constraint: "risk" | "allocation" | "both" | "none";
  exchange_time: string;
  recorded_at: string;
  execution_permitted: false;
  order_submitted: false;
};

export type PaperPositionListResponse = {
  positions: PaperPositionResponse[];
};

export type ResearchNoteResponse = {
  id: string;
  title: string;
  body: string;
  created_at: string;
};

export type ResearchNoteListResponse = {
  notes: ResearchNoteResponse[];
};

export type SourceEventResponse = {
  id: string;
  title: string;
  source: string;
  event_time: string;
  first_public_at: string;
  recorded_at: string;
  execution_permitted: false;
  order_submitted: false;
};

export type SourceEventListResponse = {
  events: SourceEventResponse[];
};

export type PaperSizeJournalEntry = {
  id: string;
  recorded_at: string;
  symbol: CoinbaseProduct;
  equity: string;
  entry: string;
  stop: string;
  shares: number;
  planned_risk: string;
  binding_constraint: "risk" | "allocation" | "both" | "none";
  execution_permitted: false;
  order_submitted: false;
};

export type PaperSizeJournalListResponse = {
  entries: PaperSizeJournalEntry[];
};

export type Mac01StatusResponse = {
  strategy: "mac-01";
  strategy_version: string | null;
  symbol: "AAPL";
  broker: "alpaca_trading_api";
  order_route: "none";
  order_submitter: "cli_runner_only";
  config_valid: boolean;
  config_mode: "paper" | "live" | null;
  money: "paper" | "real" | "unknown";
  config_live_enabled: boolean | null;
  config_expected_account_set: boolean | null;
  config_submit_orders: boolean | null;
  config_kill_switch: boolean | null;
  max_notional_per_trade: string | null;
  max_position_notional: string | null;
  max_orders_per_day: number | null;
  last_mode: "paper" | "live" | null;
  paused: boolean;
  kill_switch: boolean;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_message: string | null;
  last_session_date: string | null;
  disclaimer: string;
};

export type Mac01Signal = {
  session_date: string;
  strategy_version: string;
  symbol: string;
  side: "BUY" | "SELL" | "HOLD";
  reason: string;
  close: string;
  fast_prev: string;
  slow_prev: string;
  fast_cur: string;
  slow_cur: string;
  decision: string;
  decision_reason: string;
  inputs_hash: string;
  created_at: string;
  decided_at: string;
};

export type Mac01SignalListResponse = {
  signals: Mac01Signal[];
};

export type Mac01Order = {
  client_order_id: string;
  mode: "paper" | "live";
  session_date: string;
  side: "buy" | "sell";
  notional: string | null;
  qty: string | null;
  order_type: "market";
  time_in_force: "day";
  status: string;
  broker_order_id: string | null;
  filled_qty: string;
  filled_avg_price: string | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  last_error: string | null;
};

export type Mac01OrderListResponse = {
  orders: Mac01Order[];
};

export type Mac01PerformanceResponse = {
  mode: "paper" | "live";
  realised_pl: string | null;
  realised_available: boolean;
  unrealised_pl: string | null;
  unrealised_available: boolean;
  position_qty: string | null;
  avg_entry_price: string | null;
  market_price: string | null;
  position_as_of: string | null;
  filled_orders: number;
  note: string;
};

export type Mac01ChartPoint = {
  session_date: string;
  close: string;
  sma_fast: string | null;
  sma_slow: string | null;
};

export type Mac01ChartResponse = {
  available: boolean;
  symbol: "AAPL";
  source: string | null;
  as_of: string | null;
  fast_period: number | null;
  slow_period: number | null;
  points: Mac01ChartPoint[];
  markers: { session_date: string; side: "BUY" | "SELL" }[];
  note: string;
};

export type PaperSwapBalance = {
  symbol: string;
  amount: string;
};

export type PaperSwapNetwork = {
  chain: "solana" | "ethereum" | "base";
  network: "solana-devnet" | "sepolia" | "base-sepolia";
  chain_id: "devnet" | "11155111" | "84532";
  simulated: true;
  balances: PaperSwapBalance[];
};

export type PaperSwapPortfolioResponse = {
  simulated: true;
  execution_permitted: false;
  order_submitted: false;
  networks: PaperSwapNetwork[];
};

export type PaperSwapOrder = {
  id: string;
  chain: "solana" | "ethereum" | "base";
  network: "solana-devnet" | "sepolia" | "base-sepolia";
  chain_id: "devnet" | "11155111" | "84532";
  token_in: string;
  token_out: string;
  amount_in: string;
  quoted_out: string;
  amount_out: string;
  quoted_price: string;
  quote_source: string;
  price_kind: "pool" | "reference";
  slippage_bps: number;
  slippage_applied: string;
  fee_estimate: string;
  fee_symbol: string;
  balances_after: Record<string, string>;
  status: "simulated";
  simulated: true;
  created_at: string;
  execution_permitted: false;
  order_submitted: false;
};

export type PaperSwapOrderListResponse = {
  simulated: true;
  execution_permitted: false;
  order_submitted: false;
  orders: PaperSwapOrder[];
};

export const AGENT_CODES = [
  "SUPERVISOR-01",
  "DAY-01",
  "STOCK-01",
  "CRYPTO-01",
  "DEFI-01",
  "ETF-01",
  "RESEARCH-01",
  "RISK-01",
  "TREASURY-01",
] as const;

export type AgentCode = (typeof AGENT_CODES)[number];

export type AgentDesk = {
  code: AgentCode;
  display_name: string;
  desk: string;
  status: "disabled" | "paused";
  paper_only: true;
  can_submit_orders: false;
  can_sign: false;
  can_transfer_funds: false;
  holds_credentials: false;
  permission_effect: "deny";
};

export type AgentListResponse = {
  agents: AgentDesk[];
  source: "local_registry";
  trading_rights: "denied";
  execution_permitted: false;
  order_submitted: false;
};

export const DENIED_TOOLS = [
  "submit_order",
  "cancel_order",
  "sign_transaction",
  "broadcast_transaction",
  "bank_transfer",
  "set_live_mode",
  "release_kill_switch",
] as const;

export type DeskDetail = {
  code: AgentCode;
  display_name: string;
  desk: string;
  status: "disabled" | "paused";
  paper_only: true;
  can_submit_orders: false;
  can_sign: false;
  can_transfer_funds: false;
  holds_credentials: false;
  permission_effect: "deny";
  notes: string;
  tools: { tool_name: (typeof DENIED_TOOLS)[number]; effect: "deny" }[];
  running: false;
  can_enable: false;
  source: "local_registry";
  trading_rights: "denied";
  execution_permitted: false;
  order_submitted: false;
};

export type AuditLogEntry = {
  id: string;
  created_at: string;
  correlation_id: string;
  action: "risk.size.recorded";
  symbol: (typeof COINBASE_PRODUCTS)[number];
  shares: number;
  binding_constraint: "risk" | "allocation" | "both" | "none";
  execution_permitted: false;
  order_submitted: false;
};

export type AuditLogListResponse = {
  events: AuditLogEntry[];
  source: "local_audit_log";
  execution_permitted: false;
  order_submitted: false;
};

export type SystemStatusResponse = {
  status: "ok";
  service: "veytrix-api";
  env: "local";
  trading_mode: "paper";
  live_broker: "disabled";
  auth: "not_configured";
  database: "up";
  execution_permitted: false;
  order_submitted: false;
  order_route: "absent";
  agents_registered: number;
  agents_can_trade: false;
  sample_data: true;
};

export type MarketFeedHealth = {
  symbol: CoinbaseProduct;
  status: "up" | "stale" | "down";
  source_id: "coinbase-exchange";
  synthetic: false;
  retrieved_at: string | null;
  trade_time: string | null;
  age_seconds: number | null;
  price: string | null;
  note: string;
};

export type MarketHealthResponse = {
  status: "ok" | "degraded" | "unavailable";
  source: "coinbase-exchange";
  stale_after_seconds: 120;
  feeds: [MarketFeedHealth, MarketFeedHealth, MarketFeedHealth];
  sample_included: false;
  executable: false;
  execution_permitted: false;
  order_submitted: false;
  order_route: "absent";
  note: string;
};

export type TreasuryMonthlySummary = {
  period: string;
  period_closed: false;
  realised_profit: string;
  costs: string;
  loss_carryforward: string;
  eligible_profit: string;
  proposed_distribution: string;
  retained: string;
  loss_carryforward_out: string;
  distribution_fraction: "0.50";
  distribution_cap: "2000.00";
  review_day: 5;
  review_on: string;
  review_shifted_for_weekend: boolean;
  fills_counted: number;
  fees_included: false;
  carryforward_stored: false;
  broker_reconciled: false;
  settled: false;
  transfer_status: "not_attempted";
  approval_route: "absent";
  execution_permitted: false;
  order_submitted: false;
  transfer_submitted: false;
  source: "local_projection";
  note: string;
};

export type SupervisorTool = {
  name: string;
  effect: "read" | "deny";
  executes: false;
};

export type Mac01ScheduleResponse = {
  strategy: "mac-01";
  timezone: "America/New_York";
  run_clock: "09:35";
  delay_after_open_minutes: 5;
  calendar: "not_read";
  next_session: "unknown";
  running: false;
  process: "absent";
  submit_flag: false;
  can_start: false;
  config_valid: boolean;
  config_mode: "paper" | "live" | null;
  config_submit_orders: boolean | null;
  config_live_enabled: boolean | null;
  alpaca_called: false;
  execution_permitted: false;
  order_submitted: false;
  order_route: "absent";
  source: "local_config";
  note: string;
};

export type SubmissionConditionName =
  | "mode_live"
  | "live_enabled"
  | "submit_orders"
  | "confirm_phrase"
  | "submit_flag"
  | "account_match"
  | "account_active"
  | "kill_switch_off";

export type SubmissionEvidenceResponse = {
  config_valid: boolean;
  config_mode: "paper" | "live" | null;
  config_live_enabled: boolean | null;
  config_submit_orders: boolean | null;
  config_kill_switch: boolean | null;
  expected_account_set: boolean | null;
  conditions: { name: SubmissionConditionName; met: boolean }[];
  conditions_met: number;
  account_status: "not_read";
  ledger_kill_switch: "not_read";
  submit_flag: false;
  api_reaches_engine: false;
  broker_called: false;
  paper_submission_from_api: false;
  live_submission_possible: false;
  expected_account_echoed: false;
  confirm_phrase_echoed: false;
  execution_permitted: false;
  order_submitted: false;
  order_route: "absent";
  source: "local_config";
  note: string;
};

export type ReconciliationRow = {
  client_order_id: string;
  mode: "paper" | "live";
  side: "buy" | "sell";
  local_status: string;
  broker_order_id: string | null;
  broker_order_stored: boolean;
  broker_status: "not_read";
  matched: false;
  reason: "broker_not_read";
};

export type ReconciliationResponse = {
  local_orders: number;
  local_fills: number;
  local_open: number;
  broker_rows_read: 0;
  broker_read: "absent";
  alpaca_called: false;
  reconciled: false;
  rows: ReconciliationRow[];
  execution_permitted: false;
  order_submitted: false;
  order_route: "absent";
  source: "local_ledger";
  note: string;
};

export type SupervisorToolsResponse = {
  source: "local_catalogue";
  model: "not_configured";
  chat: "absent";
  tools: SupervisorTool[];
  executed: false;
  invokes_model: false;
  execution_permitted: false;
  order_submitted: false;
  note: string;
};
