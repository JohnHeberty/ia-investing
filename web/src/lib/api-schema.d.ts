export interface paths {
  "/api/v1/policy/events": {
    get: {
      parameters: { query?: { as_of?: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/model-portfolios": {
    get: {
      parameters: { query?: { state?: string; limit?: number; environment?: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/model-portfolios/{portfolio_id}": {
    get: {
      parameters: { path: { portfolio_id: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/agents/runs": {
    get: {
      parameters: { query?: { status?: string; agent_name?: string; limit?: number } };
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/research/cases": {
    get: { responses: { 200: { content: { "application/json": Record<string, unknown>[] } } } };
  };
  "/api/v1/sources/health": {
    get: { responses: { 200: { content: { "application/json": Record<string, unknown>[] } } } };
  };
  "/api/v1/instruments/resolve": {
    get: {
      parameters: { query: { query: string; as_of?: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/backtests": {
    get: {
      parameters: { query?: { limit?: number; offset?: number } };
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/committee/sessions": {
    get: {
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/committee/sessions/{session_id}": {
    get: {
      parameters: { path: { session_id: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/paper/trade-intents": {
    get: {
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/quality/incidents": {
    get: {
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
  };
  "/api/v1/audit/logs": {
    get: {
      parameters: { query?: { limit?: number; offset?: number } };
      responses: {
        200: { content: { "application/json": { items?: Record<string, unknown>[] } } };
      };
    };
  };
  "/api/v1/audit/verify": {
    get: {
      responses: {
        200: {
          content: {
            "application/json": {
              verified?: boolean;
              tampered_entries?: Record<string, unknown>[];
            };
          };
        };
      };
    };
  };
  "/api/v1/portfolio": {
    get: {
      responses: { 200: { content: { "application/json": Record<string, unknown>[] } } };
    };
    post: {
      parameters: { header: { "Idempotency-Key": string } };
      requestBody: {
        content: {
          "application/json": {
            name: string;
            description?: string;
            is_paper_trading?: boolean;
            base_currency?: string;
            initial_capital?: number;
          };
        };
      };
      responses: { 201: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/portfolio/{portfolio_id}": {
    get: {
      parameters: { path: { portfolio_id: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/portfolio/{portfolio_id}/positions": {
    post: {
      parameters: { path: { portfolio_id: string } };
      requestBody: {
        content: {
          "application/json": {
            ticker_symbol: string;
            quantity: number;
            avg_cost_per_share: number;
            current_price?: number;
            issuer_id?: string;
          };
        };
      };
      responses: { 201: { content: { "application/json": Record<string, unknown> } } };
    };
  };
  "/api/v1/portfolio/{portfolio_id}/recommendations": {
    get: {
      parameters: { path: { portfolio_id: string } };
      responses: { 200: { content: { "application/json": Record<string, unknown> } } };
    };
  };
}

export type webhooks = Record<string, never>;
// eslint-disable-next-line @typescript-eslint/no-empty-object-type
export interface components {}
export type $defs = Record<string, never>;
export type external = Record<string, never>;
