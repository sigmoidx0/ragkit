"""Give untitled chat sessions a title from their first question.

New sessions are titled when their first message arrives; this fills in the
ones created before that existed. Safe to re-run — titled sessions are skipped.

    cd server && uv run python scripts/backfill_session_titles.py
    # in the container stack:
    docker compose -f deploy/docker-compose.yml exec server python scripts/backfill_session_titles.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

from app.agent.checkpoint import checkpointer_lifespan  # noqa: E402
from app.agent.history import title_from_message  # noqa: E402
from app.db.models import ChatSession  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


async def main() -> None:
    titled = skipped = 0
    async with checkpointer_lifespan() as saver:
        with SessionLocal() as db:
            for session in db.execute(select(ChatSession).where(ChatSession.title.is_(None))).scalars():
                cp = await saver.aget_tuple({"configurable": {"thread_id": str(session.id)}})
                messages = cp.checkpoint.get("channel_values", {}).get("messages", []) if cp else []
                first = next((str(m.content) for m in messages if isinstance(m, HumanMessage)), None)
                if first:
                    # Set updated_at to itself explicitly: otherwise its onupdate
                    # fires and every old session jumps to the top of the list,
                    # which is sorted by last activity.
                    db.execute(
                        update(ChatSession)
                        .where(ChatSession.id == session.id)
                        .values(title=title_from_message(first), updated_at=ChatSession.updated_at)
                    )
                    titled += 1
                else:
                    skipped += 1  # never chatted in — nothing to name it after
            db.commit()
    print(f"titled {titled} session(s), skipped {skipped} empty one(s)")


if __name__ == "__main__":
    asyncio.run(main())
