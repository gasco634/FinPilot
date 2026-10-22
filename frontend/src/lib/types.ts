export type Filters = { year: number; period: string; activityId: string; clientId: string }
export type Kpis = {
  revenue_xof: number; expenses_xof: number; net_profit_xof: number; net_margin_pct: number; cash_balance_xof: number;
  receivables_xof: number; overdue_xof: number; savings_rate_pct: number; billed_revenue_xof: number; collection_rate_pct: number;
  dso_days: number; quote_conversion_pct: number; quote_acceptance_days: number | null; average_basket_xof: number; client_concentration_pct: number; client_hhi: number;
  growth_mom_pct: number | null; growth_yoy_pct: number | null; burn_rate_monthly_xof: number; runway_months: number | null;
  break_even_xof: number; gross_profit_xof: number; gross_margin_pct: number; monthly: { month: string; income_xof: number; expenses_xof: number }[];
  activities: { activity_id: string; activity_name: string; revenue_xof: number; expenses_xof: number; profit_xof: number }[];
  top_clients: { client_id: string; client_name: string; revenue_xof: number }[];
  changes: { revenue_pct: number | null; expenses_pct: number | null; profit_pct: number | null };
}
export type Client = { id: string; name: string; first_name?: string|null; last_name?: string|null; email?: string; phone?: string; revenue_xof: number; billed_xof: number; receivables_xof: number; segment: 'A'|'B'|'C'; payment_terms_days: number; reliability_score?: number; average_payment_days?: number|null; recurring_rate_pct?: number }
export type Activity = { id: string; name: string; color: string }
export type Category = { id: string; name: string; kind: string; cost_type?: string }
export type Transaction = { id: string; kind: 'income'|'expense'; income_type?: 'prestation'|'formation'|'vente'|'autre'|null; amount_xof: number; transaction_date: string; due_date?: string; status: string; payment_method?: string; activity_id?: string; client_id?: string; category_id?: string; description: string; reference?: string }
export type Alert = { id: string; severity: string; status: string; title: string; explanation: string; recommendation: string; generated_at?: string }
export type DashboardData = { period: { start: string; end: string }; kpis: Kpis; alerts: Alert[]; recent_transactions: Transaction[]; budgets: { category_name: string; budget_xof: number; actual_xof: number }[]; settings: Record<string, any>; activities: [string,string][]; clients: [string,string][] }
