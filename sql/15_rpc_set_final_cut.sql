-- A remote-procedure call (RPC) to set a take as the final cut.
-- This is the only safe way to enforce the partial unique index on
-- takes(scene_id) where is_final_cut.
--
-- 1. It finds the scene_id for the given take.
-- 2. It sets is_final_cut = false for all other takes in that scene.
-- 3. It sets is_final_cut = true for the target take.
--
-- Called from the /takes/{take_id}/finalize API endpoint.
create or replace function set_final_cut(target_take_id uuid)
returns void
language plpgsql
as $$
declare
    target_scene_id uuid;
begin
    -- Get the scene_id for the take we're finalizing
    select scene_id into target_scene_id
    from takes
    where take_id = target_take_id;

    if target_scene_id is null then
        raise exception 'Take not found: %', target_take_id;
    end if;

    -- Atomically update all takes for this scene
    -- First, unset any other final cut for this scene
    update takes
    set is_final_cut = false
    where scene_id = target_scene_id
      and take_id != target_take_id
      and is_final_cut = true;

    -- Then, set the new final cut
    update takes
    set is_final_cut = true
    where take_id = target_take_id;
end;
$$;
