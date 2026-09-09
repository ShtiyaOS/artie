-- noinspection SqlNoDataSourceInspectionForFile

CREATE OR REPLACE FUNCTION get_all_components_for_project(prj_id uuid)
RETURNS TABLE(component_id uuid, content_hash text)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.component_id,
        sc.content_hash
    FROM
        script_components sc
    JOIN
        takes t ON sc.take_id = t.take_id
    JOIN
        scenes s ON t.scene_id = s.scene_id
    WHERE
        s.project_id = prj_id;
END;
$$;
