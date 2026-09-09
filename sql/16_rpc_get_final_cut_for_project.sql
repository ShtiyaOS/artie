-- noinspection SqlNoDataSourceInspectionForFile

CREATE OR REPLACE FUNCTION get_final_cut_for_project(prj_id uuid)
RETURNS TABLE(content text, component_type text, scene_id uuid, take_id uuid, component_id uuid, sequence_order integer)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        sc.content,
        sc.component_type,
        s.scene_id,
        t.take_id,
        sc.component_id,
        sc.sequence_order
    FROM
        script_components sc
    JOIN
        takes t ON sc.take_id = t.take_id
    JOIN
        scenes s ON t.scene_id = s.scene_id
    WHERE
        s.project_id = prj_id AND t.is_final_cut = TRUE
    ORDER BY
        s.sequence_order, sc.sequence_order;
END;
$$;
