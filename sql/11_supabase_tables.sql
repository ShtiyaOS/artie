-- Supabase tables and indexes
-- Run after 10_supabase_types.sql

-- 2.1 Projects
create table if not exists projects (
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

-- 2.2 Bible slots
create table if not exists bible_slots (
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

-- 2.3 Scenes
create table if not exists scenes (
    scene_id                   uuid primary key default gen_random_uuid(),
    project_id                 uuid not null references projects on delete cascade,
    position_id                smallint,
    sequence_order             integer not null,
    status                     scene_status not null default 'RIG_OPEN',
    diagnosed_at_bible_version integer,
    created_at                 timestamptz not null default now(),
    updated_at                 timestamptz not null default now()
);

create index if not exists scenes_project_order on scenes (project_id, sequence_order);
create index if not exists scenes_project_position on scenes (project_id, position_id);

-- 2.4 Takes
create table if not exists takes (
    take_id      uuid primary key default gen_random_uuid(),
    scene_id     uuid not null references scenes on delete cascade,
    take_number  integer not null,
    is_final_cut boolean not null default false,
    submitted_at timestamptz,
    created_at   timestamptz not null default now(),
    unique (scene_id, take_number)
);

create index if not exists takes_scene on takes (scene_id, take_number);
create unique index if not exists takes_one_final_cut
    on takes (scene_id) where is_final_cut;

-- 2.5 Scene Rig slots
create table if not exists scene_rig_slots (
    scene_id    uuid not null references scenes on delete cascade,
    slot_id     text not null,
    value       jsonb not null,
    is_filled   boolean not null default false,
    input_conf  input_confidence not null default 'VALIDATED',
    reask_count smallint not null default 0,
    updated_at  timestamptz not null default now(),
    primary key (scene_id, slot_id)
);

-- 2.6 Script components
create table if not exists script_components (
    component_id   uuid primary key default gen_random_uuid(),
    take_id        uuid not null references takes on delete cascade,
    sequence_order integer not null,
    comp_type      component_type not null,
    content        text not null default '',
    content_hash   text,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

create index if not exists script_components_take on script_components (take_id, sequence_order);

-- 2.7 Characters
create table if not exists characters (
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

-- 2.8 Locations
create table if not exists locations (
    location_id uuid primary key default gen_random_uuid(),
    project_id  uuid not null references projects on delete cascade,
    name        text not null,
    source      roster_source not null,
    created_at  timestamptz not null default now(),
    unique (project_id, name)
);

-- 2.9 World rules
create table if not exists world_rules (
    rule_id    uuid primary key default gen_random_uuid(),
    project_id uuid not null references projects on delete cascade,
    rule_type  world_rule_type not null,
    condition  text not null,
    outcome    text not null,
    is_active  boolean not null default true,
    created_at timestamptz not null default now()
);

create unique index if not exists world_rules_active_cap
    on world_rules (project_id, rule_id) where is_active;

-- 2.10 Assets
create table if not exists assets (
    asset_id        uuid primary key default gen_random_uuid(),
    scene_id        uuid not null references scenes on delete cascade,
    gcs_uri         text not null,
    model           text not null,
    prompt          text not null,
    assumption_note text,
    finish_reason   text,
    created_at      timestamptz not null default now()
);

-- 2.11 Delivery queue
create table if not exists agent_queue (
    queue_id     uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    scene_id     uuid references scenes on delete cascade,
    item_type    queue_item not null,
    payload      jsonb not null,
    created_at   timestamptz not null default now(),
    delivered_at timestamptz
);

create index if not exists agent_queue_undelivered
    on agent_queue (project_id, delivered_at) where delivered_at is null;

-- 2.12 Sessions
create table if not exists sessions (
    session_id   uuid primary key default gen_random_uuid(),
    project_id   uuid not null references projects on delete cascade,
    opened_at    timestamptz not null default now(),
    closed_at    timestamptz,
    opening_slug text
);

-- 2.13 Continuity checks
create table if not exists continuity_checks (
    check_id       uuid primary key default gen_random_uuid(),
    project_id     uuid not null references projects on delete cascade,
    ran_at         timestamptz not null default now(),
    scenes_covered integer not null,
    take_ids       uuid[] not null,
    findings       jsonb not null,
    tiers_run      smallint[] not null
);

create index if not exists continuity_checks_project
    on continuity_checks (project_id, ran_at desc);
