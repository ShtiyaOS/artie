-- Enable RLS on all tables — deny by default
-- Backend uses secret key which bypasses RLS; publishable key reaches nothing

alter table projects           enable row level security;
alter table bible_slots        enable row level security;
alter table scenes             enable row level security;
alter table scene_rig_slots    enable row level security;
alter table script_components  enable row level security;
alter table characters         enable row level security;
alter table locations          enable row level security;
alter table world_rules        enable row level security;
alter table assets             enable row level security;
alter table agent_queue        enable row level security;
alter table sessions           enable row level security;
alter table takes              enable row level security;
alter table continuity_checks  enable row level security;
