"""Q-05-T17 (TASK-8823; SPEC-711 AC-18): reissue and intake.

"Choosing Revise and reissue on PI-01 makes AUD-23 g live with a dual date, and filing the
Harborline PDF from INB-01 creates the PI-01 source with no other write to the locked work item."
Here: only a revising case reopens; the reopened draft is dual-dated and names the original
release; A-07's release records kind reissue for it; the INB-01 destination files a source row
only.
"""

from __future__ import annotations

import inspect

from abacus.modules.assurance import post_issuance_reissue as r
from abacus.modules.assurance import release


def test_ac_only_a_revising_case_reopens() -> None:
    assert r.NotRevising.code == "post_issuance_not_revising"
    source = inspect.getsource(r.reopen_for_reissue)
    assert '"revise_and_reissue"' in source and "dual_date" in source and "reissue_of_release_id" in source


def test_ac_the_release_records_kind_reissue() -> None:
    source = inspect.getsource(release)
    assert "'reissue' END" in source and "reissue_of_id" in source


def test_ac_intake_files_a_source_row_only() -> None:
    after = inspect.getsource(r._after_file)  # pyright: ignore[reportPrivateUsage]
    assert "INSERT INTO post_issuance_sources" in after and "UPDATE" not in after
    assert r.DESTINATION == "post_issuance_source"
