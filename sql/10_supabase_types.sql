-- Supabase type definitions
-- Run this before 11_supabase_tables.sql

do $$ begin
    create type commitment_state as enum ('SKEPTICAL', 'COMMITTED');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type input_confidence as enum ('VALIDATED', 'PROVISIONAL');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type scene_status as enum ('RIG_OPEN', 'DRAFTING', 'COMPLETE');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type component_type as enum (
        'SCENE_HEADING', 'ACTION', 'CHARACTER', 'DIALOGUE',
        'PARENTHETICAL', 'TRANSITION', 'NOTE'
    );
exception when duplicate_object then null;
end $$;

do $$ begin
    create type character_role as enum ('PROTAGONIST', 'ANTAGONIST', 'PRINCIPAL', 'SECONDARY');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type roster_source as enum ('BLUEPRINT', 'SCENE_RIG');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type world_rule_type as enum ('A_POSSIBILITY', 'B_CONSEQUENCE');
exception when duplicate_object then null;
end $$;

do $$ begin
    create type queue_item as enum ('FINDING', 'SLOT_JUDGMENT_FAILED', 'CANON_FINDING');
exception when duplicate_object then null;
end $$;
