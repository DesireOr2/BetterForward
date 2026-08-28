import sqlite3


def upgrade(db_path):
    with sqlite3.connect(db_path) as conn:
        db_cursor = conn.cursor()
        db_cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_received "
            "ON messages(received_id, in_group, topic_id)"
        )
        db_cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_forwarded "
            "ON messages(forwarded_id, topic_id, in_group)"
        )
        db_cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_topic "
            "ON messages(topic_id)"
        )
        conn.commit()
