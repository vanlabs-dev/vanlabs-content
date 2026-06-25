-- Cross-run dedup for the Bittensor Engagement Engine.
-- One-time DDL. Lives in the shared IntoOps Supabase project; the vanlabs_ prefix
-- keeps it namespaced. PostgREST cannot run DDL, so apply this via the Supabase SQL
-- editor or the Supabase MCP (execute_sql / apply_migration). Safe and additive.

create table if not exists vanlabs_seen_targets (
  tweet_id   text primary key,      -- canonical X status id (Desearch tweet.id)
  tweet_url  text not null,
  author     text,                  -- @handle engaged
  topic      text,                  -- short label of the item (story-level variety)
  format     text,                  -- 'quote' | 'reply'
  run_at     timestamptz not null default now()
);

-- The routine reads with run_at >= now() - interval '7 days', so index run_at.
create index if not exists vanlabs_seen_targets_run_at_idx
  on vanlabs_seen_targets (run_at desc);
