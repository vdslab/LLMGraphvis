"""Relabel historical upload logs from <thought> to <steps>

The upload pipeline used to persist its progress log ("Importing GraphML
data…", "Calculating ForceAtlas2 layout…") wrapped in <thought>, which the chat
renders under a "Thinking" heading. No model runs during an upload, so every
one of those messages tells the user the app reasoned about something it did
not. New uploads write <steps>; this rewrites the ones already stored.

Deliberately narrow: only a message whose <thought> block is immediately
followed by the upload's own success line is touched, and only the tag is
changed. The overview text in those messages stays inline rather than being
reconstructed into a collapsible — its title is not recoverable from the stored
Markdown, and a wrong title would be worse than an unfolded section.

Revision ID: a7b8c9d0e1f2
Revises: f6a1b2c3d4e5
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The line only handle_upload_background writes. Together with the message
# starting with the tag being replaced, it identifies an upload log and nothing
# else — the marker has to name the tag being replaced, or the reverse
# direction matches nothing.
SUCCESS_LINE = "Graph uploaded and initialized successfully."


def _retag(from_tag: str, to_tag: str) -> None:
    op.execute(
        sa.text(
            """
            UPDATE chat_messages
               SET content = replace(
                     replace(content, :open_from, :open_to),
                     :close_from, :close_to)
             WHERE role = 'model'
               AND content LIKE :has_open
               AND content LIKE :marker
            """
        ).bindparams(
            open_from=f"<{from_tag}>",
            open_to=f"<{to_tag}>",
            close_from=f"</{from_tag}>",
            close_to=f"</{to_tag}>",
            has_open=f"<{from_tag}>%",
            marker=f"%</{from_tag}>%{SUCCESS_LINE}%",
        )
    )


def upgrade() -> None:
    _retag("thought", "steps")


def downgrade() -> None:
    _retag("steps", "thought")
