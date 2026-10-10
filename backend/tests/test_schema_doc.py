"""`common/schema.md` must match `common/models.py`.

The ER diagram is the one picture of the schema people read; a stale one
misleads worse than none, which is what happened to the hand-drawn diagram it
replaces (ADR 0001, ADR 0030).
"""

from common import schema_doc


def test_every_table_belongs_to_a_domain():
    assert schema_doc.unassigned_tables() == [], (
        "Add the new table to a domain in common/schema_doc.py DOMAINS"
    )


def test_schema_doc_is_current():
    assert schema_doc.SCHEMA_DOC_PATH.read_text(encoding="utf-8") == (
        schema_doc.render()
    ), "common/schema.md is stale; run `python -m common.schema_doc` in backend/"
