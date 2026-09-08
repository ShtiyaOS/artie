-- Seed: cell_slot_consumption
-- Derived from docs/10_clickhouse.md §3.4 (governing)
-- cross-referenced with docs/02_greenlight.md §2 Consumed-by column.
--
-- cell_id_num = position_number * 10 + lens_number
--   X01 = 1 .. X12 = 12 ; Y1 = 1 .. Y6 = 6
--
-- S09 (Genre) and S11 (World Rules) consume no cells and have no rows here.
-- Row count: 88

INSERT INTO cell_slot_consumption (cell_id_num, slot_id) VALUES

-- S02 Protagonist — all Y3 cells (positions X01..X12, lens 3)
(13, 'S02'),   -- X01.Y3
(23, 'S02'),   -- X02.Y3
(33, 'S02'),   -- X03.Y3
(43, 'S02'),   -- X04.Y3
(53, 'S02'),   -- X05.Y3
(63, 'S02'),   -- X06.Y3
(73, 'S02'),   -- X07.Y3
(83, 'S02'),   -- X08.Y3
(93, 'S02'),   -- X09.Y3
(103, 'S02'),  -- X10.Y3
(113, 'S02'),  -- X11.Y3
(123, 'S02'),  -- X12.Y3

-- S03 Protagonist Want — all Y2 cells (12) + X04.Y1, X06.Y1
(12, 'S03'),   -- X01.Y2
(22, 'S03'),   -- X02.Y2
(32, 'S03'),   -- X03.Y2
(42, 'S03'),   -- X04.Y2
(52, 'S03'),   -- X05.Y2
(62, 'S03'),   -- X06.Y2
(72, 'S03'),   -- X07.Y2
(82, 'S03'),   -- X08.Y2
(92, 'S03'),   -- X09.Y2
(102, 'S03'),  -- X10.Y2
(112, 'S03'),  -- X11.Y2
(122, 'S03'),  -- X12.Y2
(41, 'S03'),   -- X04.Y1
(61, 'S03'),   -- X06.Y1

-- S04 Protagonist Flaw — X01.Y3, X08.Y3, X11.Y3, X12.Y3
(13, 'S04'),   -- X01.Y3
(83, 'S04'),   -- X08.Y3
(113, 'S04'),  -- X11.Y3
(123, 'S04'),  -- X12.Y3

-- S05 Antagonism — all Y2 cells (positions X01..X12, lens 2)
(12, 'S05'),   -- X01.Y2
(22, 'S05'),   -- X02.Y2
(32, 'S05'),   -- X03.Y2
(42, 'S05'),   -- X04.Y2
(52, 'S05'),   -- X05.Y2
(62, 'S05'),   -- X06.Y2
(72, 'S05'),   -- X07.Y2
(82, 'S05'),   -- X08.Y2
(92, 'S05'),   -- X09.Y2
(102, 'S05'),  -- X10.Y2
(112, 'S05'),  -- X11.Y2
(122, 'S05'),  -- X12.Y2

-- S06 Thematic Proposition — all Y4 cells (positions X01..X12, lens 4)
(14, 'S06'),   -- X01.Y4
(24, 'S06'),   -- X02.Y4
(34, 'S06'),   -- X03.Y4
(44, 'S06'),   -- X04.Y4
(54, 'S06'),   -- X05.Y4
(64, 'S06'),   -- X06.Y4
(74, 'S06'),   -- X07.Y4
(84, 'S06'),   -- X08.Y4
(94, 'S06'),   -- X09.Y4
(104, 'S06'),  -- X10.Y4
(114, 'S06'),  -- X11.Y4
(124, 'S06'),  -- X12.Y4

-- S07 Status Quo Baseline — X01 row (6 cells) + 7 TRANSFORMATION cells
-- X01 row: X01.Y1..X01.Y6
(11, 'S07'),   -- X01.Y1
(12, 'S07'),   -- X01.Y2
(13, 'S07'),   -- X01.Y3
(14, 'S07'),   -- X01.Y4
(15, 'S07'),   -- X01.Y5
(16, 'S07'),   -- X01.Y6
-- TRANSFORMATION cells: X12.Y1..X12.Y6, X11.Y3
(121, 'S07'),  -- X12.Y1
(122, 'S07'),  -- X12.Y2
(123, 'S07'),  -- X12.Y3
(124, 'S07'),  -- X12.Y4
(125, 'S07'),  -- X12.Y5
(126, 'S07'),  -- X12.Y6
(113, 'S07'),  -- X11.Y3

-- S08 Arena — X03.Y6, X07.Y6, X12.Y6
(36, 'S08'),   -- X03.Y6
(76, 'S08'),   -- X07.Y6
(126, 'S08'),  -- X12.Y6

-- S10 Ending Shape — X11 row (6) + X12 row (6)
(111, 'S10'),  -- X11.Y1
(112, 'S10'),  -- X11.Y2
(113, 'S10'),  -- X11.Y3
(114, 'S10'),  -- X11.Y4
(115, 'S10'),  -- X11.Y5
(116, 'S10'),  -- X11.Y6
(121, 'S10'),  -- X12.Y1
(122, 'S10'),  -- X12.Y2
(123, 'S10'),  -- X12.Y3
(124, 'S10'),  -- X12.Y4
(125, 'S10'),  -- X12.Y5
(126, 'S10'),  -- X12.Y6

-- TP1 Inciting Incident — X02 row (6 cells)
(21, 'TP1'),   -- X02.Y1
(22, 'TP1'),   -- X02.Y2
(23, 'TP1'),   -- X02.Y3
(24, 'TP1'),   -- X02.Y4
(25, 'TP1'),   -- X02.Y5
(26, 'TP1');   -- X02.Y6
