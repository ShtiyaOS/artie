-- Artie Spiegel — Supabase schema
-- Source: docs/11_supabase.md
-- Run in order. Types, then tables, then indexes, then RLS, then realtime.

-- ============================================================
-- 1. TYPES
-- ============================================================

create type commitment_state as enum ('SKEPTICAL', 'COMMITTED');

create type input_confidence as enum ('VALIDATED', 'PROVISIONAL');

create type scene_status as enum ('RIG_OPEN', 'DRAFTING', 'COMPLETE');

create type component_type as enum (
    'SCENE_HEADING', 'ACTION', 'CHARACTER', 'DIALOGUE',
    'PARENTHETICAL', 'TRANSITION', 'NOTE'
);

create type character_role as enum ('PROTAGONIST','ANTAGONIST','PRINCIPAL','SECONDARY');

create type roster_source as enum ('BLUEPRINT','SCENE_RIG');

create type world_rule_type as enum ('A_POSSIBILITY', 'B_CONSEQUENCE');

create type queue_item as enum ('FINDING','SLOT_JUDGMENT_FAILED','CANON_FINDING');


-- ============================================================
-- 2. TABLES  (foreign-key dependency order)
-- ============================================================

create table projects (
    project_id            uuid primary key default gen_random_uuid(),
    writer_id             uuid,
    working_title         text not null default 'Untitled',
    commitment_state      commitment_state not null default 'SKEPTICAL',
    current_bible_version integer not null default 1,
    target_scene_count    integer,
    scenes_completed      integer not null default 0,
    created_at            timestamptz not null default now(),
    updated_at            timestamptz not null default now()
);

create table bible_slots (
    project_id       uuid not null references projects on delete cascade,
    slot_id          text not null,
    value            jsonb not null,
    is_filled        boolean not null default false,
    input_conf       input_confidence not null default 'VALIDATED',
    reask_count      smallint not null default 0,
    filled_at        timestamptz,
    updated_at       timestamptz not null default now(),
    primary key (project_id, slot_id)
);

create table scenes (
    scene_id                   uuid primary key default gen_random_uuid(),
    project_id                 uuid not null references projects on delete cascade,
    position_id                smallint,
    sequence_order             integer not null,
    status                     scene_status not null default 'RIG_OPEN',
    diagnosed_at_bible_version integer,
    created_at                 timestamptz not null default now(),
    updated_at                 timestamptz not null default now()
);

create table takes (
    take_id      uuid primary key default gen_random_uuid(),
    scene_id     uuid not null references scenes on delete cascade,
    take_number  integer not null,
    is_final_cut boolean not null default false,
    submitted_at timestamptz,
    created_at   timestamptz not null default now(),
    unique (scene_id, take_number)
);

create table scene_rig_slots (
    scene_id    uuid not null references scenes on delete cascade,
    slot_id     text not null,
    value       jsonb not null,
    is_filled   boolean not null default false,
    input_conf  input_confidence not null default 'VALIDATED',
    reask_count smallint not null default 0,
    updated_at  timestamptz not null default now(),
    primary key (scene_id, slot_id)
);

create table script_components (
    component_id   uuid primary key default gen_random_uuid(),
    take_id        uuid not null references takes on delete cascade,
    sequence_order integer not null,
    comp_type      component_type not null,
    content        text not null default '',
    content_hash   text,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

create table characters (
    character_id           uuid primary key default gen_random_uuid(),
    project_id             uuid not null references projects on delete cascade,
    name                   text not null,
    role                   character_role not null,
    description            text,
    source                 roster_source not null,
    canonical_frame_uri    text,
    character_portrait_uri text,
    created_at             timestamptz not null default now(),
    unique (project_id, name)
);

create table locations (
    location_id uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects on delete cascade,
    name        text not null,
    source      roster_source not null,
    created_at  timestamptz not null default now(),
    unique (project_id, name)
);

create table world_rules (
    rule_id    uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects on delete cascade,
    rule_type  world_rule_type not null,
    condition  text not null,
    outcome    text not null,
    is_active  boolean not null default true,
    created_at timestamptz not null default now()
);

create table assets (
    asset_id        uuid primary key default gen_random_uuid(),
    scene_id        uuid not null references scenes on delete cascade,
    gcs_uri         text not null,
    model           text not null,
    prompt          text not null,
    assumption_note text,
    finish_reason   text,
    created_at      timestamptz not null default now()
);

create table agent_queue (
    queue_id     uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    scene_id     uuid references scenes on delete cascade,
    item_type    queue_item not null,
    payload      jsonb not null,
    created_at   timestamptz not null default now(),
    delivered_at timestamptz
);

create table sessions (
    session_id   uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    opened_at    timestamptz not null default now(),
    closed_at    timestamptz,
    opening_slug text
);

create table continuity_checks (
    check_id       uuid primary key default gen_random_uuid(),
    project_id     uuid not null references projects on delete cascade,
    ran_at         timestamptz not null default now(),
    scenes_covered integer not null,
    take_ids       uuid[] not null,
    findings       jsonb not null,
    tiers_run      smallint[] not null
);


-- ============================================================
-- 3. INDEXES
-- ============================================================

create index on scenes (project_id, sequence_order);
create index on scenes (project_id, position_id);

create index on takes (scene_id, take_number);
create unique index takes_one_final_cut
    on takes (scene_id) where is_final_cut;

create index on script_components (take_id, sequence_order);

create unique index world_rules_active_cap
    on world_rules (project_id, rule_id) where is_active;

create index on agent_queue (project_id, delivered_at) where delivered_at is null;

create index on continuity_checks (project_id, ran_at desc);


-- ============================================================
-- 4. ROW-LEVEL SECURITY
-- RLS on every table. No policies. Backend uses the secret key.
-- ============================================================

alter table projects           enable row level security;
alter table bible_slots        enable row level security;
alter table scenes             enable row level security;
alter table takes              enable row level security;
alter table scene_rig_slots    enable row level security;
alter table script_components  enable row level security;
alter table characters         enable row level security;
alter table locations          enable row level security;
alter table world_rules        enable row level security;
alter table assets             enable row level security;
alter table agent_queue        enable row level security;
alter table sessions           enable row level security;
alter table continuity_checks  enable row level security;


-- ============================================================
-- 5. REALTIME
-- Four tables only. Deliberately not script_components.
-- ============================================================

alter publication supabase_realtime add table scenes;
alter publication supabase_realtime add table agent_queue;
alter publication supabase_realtime add table bible_slots;
alter publication supabase_realtime add table assets;
