"""A-09-T39 stage 1 (TASK-8543; DEC-5529): the `harlow_pike` slice's figures are group_fixtures'.

Every elimination balances; split by entity, each one's per-caption net is group_fixtures' to the
cent (so the consolidation engine's goldens still hold); each line sits on an entity whose interim
trial balance carries that caption; the timeline runs in the design's order, on epoch E1, and the
slice is registered for `--slice harlow_pike`.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from abacus.modules.assurance import group_fixtures as gf
from abacus_tools.synthetic.scenarios.brightwater_hale import harlow_pike_slice as hp
from abacus_tools.synthetic.scenarios.brightwater_hale.epochs import EPOCH_ADDS
from abacus_tools.synthetic.scenarios.brightwater_hale.slices import registered, slice_events
from abacus_tools.synthetic.scenarios.brightwater_hale.timeline import ordered


def test_each_elimination_balances_and_nets_to_group_fixtures() -> None:
    fixtures = {code: (level, desc, lines) for code, level, desc, lines in gf.ELIMINATIONS}
    assert [e[0] for e in hp.ELIMINATIONS] == list(fixtures)
    for code, level, desc, lines in hp.ELIMINATIONS:
        f_level, f_desc, f_lines = fixtures[code]
        assert (level, desc) == (f_level, f_desc), code
        assert sum(d for _c, _e, d, _cr in lines) == sum(cr for _c, _e, _d, cr in lines), code
        mine: dict[str, Decimal] = defaultdict(Decimal)
        for caption, _entity, d, cr in lines:
            mine[caption] += d - cr
        theirs: dict[str, Decimal] = defaultdict(Decimal)
        for caption, d, cr in f_lines:
            theirs[caption] += d - cr
        assert dict(mine) == dict(theirs), code


def test_each_line_sits_on_an_entity_that_carries_the_caption() -> None:
    for code, _level, _desc, lines in hp.ELIMINATIONS:
        for caption, entity, _d, _cr in lines:
            assert gf.entity_column(entity)[caption] != 0, (code, caption, entity)


def test_the_structure_and_names_are_group_fixtures() -> None:
    assert hp.ENTITY_KEYS == gf.ENTITIES
    assert hp.ENTITY_NAMES == gf.NAMES
    assert {(k, lvl, p) for k, lvl, p in hp.STRUCTURE} == set(gf.STRUCTURE)


def test_the_timeline_is_registered_ordered_and_on_epoch_e1() -> None:
    assert hp.SLICE in registered()
    events = ordered(slice_events(hp.SLICE))
    kinds = [e.kind for e in events]
    assert kinds[:6] == [
        "harlow.client_created",
        "harlow.engagement_created",
        "harlow.independence_confirmed",
        "harlow.independence_confirmed",
        "harlow.independence_confirmed",
        "harlow.connection_added",
    ]
    assert kinds[6:8] == ["harlow.consolidation_created", "harlow.structure_saved"]
    assert kinds.count("harlow.interim_tb_attached") == 5
    assert kinds.count("harlow.elimination_proposed") == 6
    assert kinds[-1] == "harlow.eliminations_posted"
    assert all(e.client == hp.CLIENT for e in events)
    assert hp.CLIENT in EPOCH_ADDS["E1"]
    first = events[0].at
    assert (first.hour, first.minute) == (10, 5)  # E1 adds Harlow & Pike from 10:05 AM
    assert {e.actor for e in events if e.kind == "harlow.elimination_proposed"} == {"CD"}
    assert events[-1].actor == "OH"
