from __future__ import annotations

from sqlalchemy import create_engine, text

from app.config import get


def main() -> None:
    url = get("POSTGRES_URL")
    if not url:
        raise SystemExit("POSTGRES_URL is not set")

    engine = create_engine(url)
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "select table_name "
                "from information_schema.tables "
                "where table_schema = 'public' "
                "order by table_name"
            )
        ).fetchall()
        print("tables:", [t[0] for t in tables])

        for t in ["root_jobs", "segment_tasks", "segment_mapping", "alembic_version"]:
            cols = conn.execute(
                text(
                    "select column_name, data_type "
                    "from information_schema.columns "
                    "where table_schema = 'public' and table_name = :t "
                    "order by ordinal_position"
                ),
                {"t": t},
            ).fetchall()
            print(f"\n{t}:")
            if not cols:
                print("  MISSING")
            else:
                for name, dtype in cols:
                    print(f"  - {name}: {dtype}")

        print("\nconstraints:")
        constraints = conn.execute(
            text(
                "select table_name, constraint_name, constraint_type "
                "from information_schema.table_constraints "
                "where table_schema='public' "
                "and table_name in ('root_jobs','segment_tasks','segment_mapping') "
                "order by table_name, constraint_type, constraint_name"
            )
        ).fetchall()
        for row in constraints:
            print("  ", row)


if __name__ == "__main__":
    main()


