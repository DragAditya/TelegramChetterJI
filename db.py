import os
import json
import aiosqlite
from config import DB_PATH


# ─────────────────────────────────────────────────────────────
# Init Database
# ─────────────────────────────────────────────────────────────

async def init_db():

    # Create DB folder only if directory exists
    db_dir = os.path.dirname(DB_PATH)

    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(DB_PATH) as db:

        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id  INTEGER PRIMARY KEY,
                name         TEXT DEFAULT 'Unknown',
                profile_data TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id  INTEGER NOT NULL,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL,
                ts           TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS style_examples (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                context   TEXT NOT NULL,
                my_reply  TEXT NOT NULL,
                ts        TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Default state
        await db.execute("""
            INSERT OR IGNORE INTO state
            VALUES ('active', 'false')
        """)

        await db.execute("""
            INSERT OR IGNORE INTO state
            VALUES ('total_replies', '0')
        """)

        await db.commit()


# ─────────────────────────────────────────────────────────────
# State
# ─────────────────────────────────────────────────────────────

async def get_state(key: str) -> str:

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            "SELECT value FROM state WHERE key=?",
            (key,)
        ) as cur:

            row = await cur.fetchone()

            return row[0] if row else ""


async def set_state(key: str, value: str):

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            "INSERT OR REPLACE INTO state VALUES (?, ?)",
            (key, value)
        )

        await db.commit()


async def increment_replies():

    total = int(await get_state("total_replies") or 0)

    total += 1

    await set_state("total_replies", str(total))


# ─────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────

async def get_or_create_user(
    telegram_id: int,
    name: str = "Unknown"
) -> dict:

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT telegram_id, name, profile_data
            FROM users
            WHERE telegram_id=?
            """,
            (telegram_id,)
        ) as cur:

            row = await cur.fetchone()

        # Create user if missing
        if not row:

            await db.execute(
                """
                INSERT INTO users(telegram_id, name)
                VALUES (?, ?)
                """,
                (telegram_id, name)
            )

            await db.commit()

            return {
                "telegram_id": telegram_id,
                "name": name,
                "profile_data": {}
            }

        return {
            "telegram_id": row[0],
            "name": row[1],
            "profile_data": json.loads(row[2] or "{}")
        }


async def update_user_info(
    telegram_id: int,
    updates: dict
):

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT profile_data
            FROM users
            WHERE telegram_id=?
            """,
            (telegram_id,)
        ) as cur:

            row = await cur.fetchone()

        profile = json.loads(row[0] or "{}") if row else {}

        profile.update(updates)

        name_update = updates.get("name")

        if name_update:

            await db.execute(
                """
                UPDATE users
                SET name=?, profile_data=?
                WHERE telegram_id=?
                """,
                (
                    name_update,
                    json.dumps(profile),
                    telegram_id
                )
            )

        else:

            await db.execute(
                """
                UPDATE users
                SET profile_data=?
                WHERE telegram_id=?
                """,
                (
                    json.dumps(profile),
                    telegram_id
                )
            )

        await db.commit()


# ─────────────────────────────────────────────────────────────
# Messages
# ─────────────────────────────────────────────────────────────

async def add_message(
    telegram_id: int,
    role: str,
    content: str
):

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT INTO messages(
                telegram_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                telegram_id,
                role,
                content
            )
        )

        await db.commit()

    # Auto compression
    count = await _msg_count(telegram_id)

    if count > 20:
        await _compress(telegram_id)


async def get_history(
    telegram_id: int,
    limit: int = 15
) -> list[tuple[str, str]]:

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT role, content
            FROM messages
            WHERE telegram_id=?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (
                telegram_id,
                limit
            )
        ) as cur:

            rows = await cur.fetchall()

    return list(reversed(rows))


async def _msg_count(
    telegram_id: int
) -> int:

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT COUNT(*)
            FROM messages
            WHERE telegram_id=?
            """,
            (telegram_id,)
        ) as cur:

            row = await cur.fetchone()

            return row[0] if row else 0


async def _compress(
    telegram_id: int
):

    from ai import summarize_conversation

    history = await get_history(
        telegram_id,
        limit=20
    )

    summary = await summarize_conversation(history)

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            DELETE FROM messages
            WHERE telegram_id=?
            """,
            (telegram_id,)
        )

        await db.execute(
            """
            INSERT INTO messages(
                telegram_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                telegram_id,
                "system",
                f"[Summary of earlier chat]: {summary}"
            )
        )

        await db.commit()


# ─────────────────────────────────────────────────────────────
# Style Learning
# ─────────────────────────────────────────────────────────────

async def add_style_example(
    context: str,
    my_reply: str
):

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            INSERT INTO style_examples(
                context,
                my_reply
            )
            VALUES (?, ?)
            """,
            (
                context[:500],
                my_reply[:500]
            )
        )

        await db.commit()


async def get_style_examples(
    limit: int = 8
) -> list[tuple[str, str]]:

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT context, my_reply
            FROM style_examples
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (limit,)
        ) as cur:

            return await cur.fetchall()


# ─────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────

async def get_stats() -> dict:

    active = await get_state("active")

    total_replies = await get_state(
        "total_replies"
    )

    async with aiosqlite.connect(DB_PATH) as db:

        async with db.execute(
            """
            SELECT COUNT(DISTINCT telegram_id)
            FROM messages
            WHERE role='user'
            """
        ) as cur:

            unique_users = (
                await cur.fetchone()
            )[0]

        async with db.execute(
            """
            SELECT COUNT(*)
            FROM style_examples
            """
        ) as cur:

            style_count = (
                await cur.fetchone()
            )[0]

    return {
        "active": active == "true",
        "total_replies": int(total_replies or 0),
        "unique_users": unique_users,
        "style_learned": style_count,
    }
