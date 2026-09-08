-- Add tables to Supabase realtime publication
-- Run after 12_supabase_rls.sql

begin;

-- Supabase default realtime publication
do $$
begin
    -- Add each table to the supabase_realtime publication if not already member
    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'scenes'
    ) then
        alter publication supabase_realtime add table scenes;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'agent_queue'
    ) then
        alter publication supabase_realtime add table agent_queue;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'bible_slots'
    ) then
        alter publication supabase_realtime add table bible_slots;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'assets'
    ) then
        alter publication supabase_realtime add table assets;
    end if;
end $$;

commit;
