-- MARKET.EXE -- user activity history.
-- Run once in Supabase: Dashboard -> SQL Editor -> paste -> Run.
--
-- Users live in the backend (app/users.py); `user_uid` is their stable UUID.
-- Only the backend talks to this table, using the service_role key. RLS is
-- enabled with NO policies, so the public anon key cannot read or write it.

create table if not exists public.user_history (
    id          bigint generated always as identity primary key,
    user_uid    uuid        not null,
    kind        text        not null check (kind in ('company', 'simulation')),
    symbol      text        not null check (symbol ~ '^[A-Z]{4}$'),
    params      jsonb       not null default '{}'::jsonb,
    result      jsonb       not null default '{}'::jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists user_history_user_created_idx
    on public.user_history (user_uid, created_at desc);

alter table public.user_history enable row level security;

-- Defense in depth: strip direct table access from the client-facing roles.
revoke all on table public.user_history from anon, authenticated;

-- ---------------------------------------------------------------------------
-- Pinned stocks (watchlist). One row per (user, symbol).
-- Safe to re-run: everything is "if not exists".
-- ---------------------------------------------------------------------------
create table if not exists public.user_pins (
    user_uid    uuid        not null,
    symbol      text        not null check (symbol ~ '^[A-Z]{4}$'),
    created_at  timestamptz not null default now(),
    primary key (user_uid, symbol)
);

alter table public.user_pins enable row level security;
revoke all on table public.user_pins from anon, authenticated;
