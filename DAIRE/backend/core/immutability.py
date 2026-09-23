"""Database-level delete protection for externally-produced records.

Results that originate outside DAIRE (blockchain smart contract, AI engine)
must never be deleted. These SQLite triggers block DELETE on every connection —
raw SQL, ORM, shell and admin alike.

PostgreSQL note: for production, replicate with
CREATE TRIGGER ... BEFORE DELETE ... RAISE EXCEPTION.
"""
from django.db.backends.signals import connection_created
from django.dispatch import receiver

# Tables whose rows must never be deleted.
DELETE_PROTECTED_TABLES = (
    "core_smartcontractresult",
    "core_blockchaintransaction",
    "core_aireputationresult",
    "core_assessment",
)


def _create_triggers(db_connection) -> None:
    if db_connection.vendor != "sqlite":
        return
    with db_connection.cursor() as cursor:
        for table in DELETE_PROTECTED_TABLES:
            cursor.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=%s", [table]
            )
            if cursor.fetchone() is None:
                continue  # fresh database before migrations
            cursor.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                BEFORE DELETE ON {table}
                BEGIN
                    SELECT RAISE(ABORT, '{table} is immutable: records cannot be deleted.');
                END;
                """
            )


@receiver(connection_created)
def _install_triggers(sender, connection, **kwargs):
    """Install delete-protection triggers on every new database connection."""
    try:
        _create_triggers(connection)
    except Exception:
        pass  # never block startup


def install_after_migrate(sender, **kwargs):
    """Called after every `migrate` so fresh/test databases get triggers too."""
    from django.db import connection

    try:
        _create_triggers(connection)
    except Exception:
        pass
