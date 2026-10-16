-- =====================================================================
-- Market Intelligence Engine: схема Supabase
-- Запуск: Supabase -> SQL Editor -> New query -> вставить -> Run.
-- Скрипт идемпотентный: его можно запускать повторно.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. ТАБЛИЦЫ
-- ---------------------------------------------------------------------

create table if not exists public.signals (
  id                 bigserial primary key,
  symbol             text        not null,
  asset_class        text,
  timeframe          text        not null,
  candle_ts          timestamptz not null,
  bias               text        not null check (bias in ('bullish', 'bearish', 'neutral')),
  score              double precision,
  probability        double precision,
  probability_source text,
  expectancy_r       double precision,
  recommended        boolean     not null default false,
  payload            jsonb       not null,
  outcome            text        check (outcome in ('tp1', 'sl', 'expired', 'no_data')),
  r_multiple         double precision,
  resolved_at        timestamptz,
  created_at         timestamptz not null default now(),
  constraint signals_symbol_tf_candle_key unique (symbol, timeframe, candle_ts)
);

create table if not exists public.candle_cache (
  key        text primary key,
  symbol     text        not null,
  timeframe  text        not null,
  updated_at timestamptz not null default now(),
  data       jsonb       not null
);

create table if not exists public.api_budget (
  day        date        not null,
  provider   text        not null,
  used       integer     not null default 0,
  updated_at timestamptz not null default now(),
  primary key (day, provider)
);

create table if not exists public.manual_events (
  id       bigserial primary key,
  ts       timestamptz not null,
  ccy      text        not null,
  event    text        not null,
  impact   text        not null default 'high' check (impact in ('low', 'medium', 'high')),
  estimate double precision,
  actual   double precision,
  note     text
);

create table if not exists public.heartbeat (
  id integer primary key,
  ts timestamptz not null default now()
);
insert into public.heartbeat (id, ts) values (1, now())
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- 2. ИНДЕКСЫ
-- ---------------------------------------------------------------------
create index if not exists signals_created_idx
  on public.signals (created_at desc);
create index if not exists signals_symbol_tf_idx
  on public.signals (symbol, timeframe, candle_ts desc);
create index if not exists signals_unresolved_idx
  on public.signals (candle_ts) where outcome is null;
create index if not exists signals_reco_idx
  on public.signals (recommended, created_at desc);
create index if not exists candle_cache_updated_idx
  on public.candle_cache (updated_at);
create index if not exists manual_events_ts_idx
  on public.manual_events (ts);

-- ---------------------------------------------------------------------
-- 3. ПРАВА И RLS
-- ---------------------------------------------------------------------
alter table public.signals       enable row level security;
alter table public.candle_cache  enable row level security;
alter table public.api_budget    enable row level security;
alter table public.manual_events enable row level security;
alter table public.heartbeat     enable row level security;

revoke all on public.signals, public.candle_cache, public.api_budget,
              public.manual_events, public.heartbeat
  from anon, authenticated;

grant select on public.signals to anon, authenticated;

drop policy if exists "anon can read signals" on public.signals;
create policy "anon can read signals"
  on public.signals
  for select
  to anon, authenticated
  using (true);

grant all on all tables    in schema public to service_role;
grant all on all sequences in schema public to service_role;

-- ---------------------------------------------------------------------
-- 4. REALTIME на таблице signals
-- ---------------------------------------------------------------------
do $$
begin
  if not exists (
    select 1 from pg_publication_tables
    where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'signals'
  ) then
    alter publication supabase_realtime add table public.signals;
  end if;
end $$;

-- ---------------------------------------------------------------------
-- 5. STORAGE: приватный бакет для моделей XGBoost
-- ---------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('models', 'models', false)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- 6. АВТООЧИСТКА
-- ---------------------------------------------------------------------
create or replace function public.cleanup_old_data(retention_days integer default 45)
returns jsonb
language plpgsql
set search_path = public
as $$
declare
  n_sig bigint;
  n_cc  bigint;
  n_bud bigint;
begin
  delete from signals
   where created_at < now() - make_interval(days => retention_days);
  get diagnostics n_sig = row_count;

  delete from candle_cache
   where updated_at < now() - interval '7 days';
  get diagnostics n_cc = row_count;

  delete from api_budget
   where day < current_date - 30;
  get diagnostics n_bud = row_count;

  return jsonb_build_object(
    'signals_deleted', n_sig,
    'candle_cache_deleted', n_cc,
    'api_budget_deleted', n_bud
  );
end;
$$;

revoke all on function public.cleanup_old_data(integer) from public, anon, authenticated;
grant execute on function public.cleanup_old_data(integer) to service_role;

do $$
begin
  create extension if not exists pg_cron;
  begin
    perform cron.unschedule('mie-cleanup');
  exception when others then
    null;
  end;
  perform cron.schedule('mie-cleanup', '17 3 * * *', 'select public.cleanup_old_data(45)');
  raise notice 'pg_cron: задание mie-cleanup создано';
exception when others then
  raise notice 'pg_cron недоступен (%). Очистку выполняет бэкенд.', sqlerrm;
end $$;
