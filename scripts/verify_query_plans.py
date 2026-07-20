"""Validate query plans for critical issuer queries using EXPLAIN ANALYZE."""

from __future__ import annotations

import asyncio
import re

import sqlalchemy as sa
from sqlalchemy import text

from database.core import session_scope
from database.models.catalog import Issuer, Sector

SECTOR_FILTER_PLAN = (
    sa.select(Issuer)
    .join(Issuer.industry)
    .join(Sector)
    .where(Issuer.is_active.is_(True), Sector.name_pt.ilike("%energia%"))
    .order_by(Issuer.name_pt)
    .offset(0)
    .limit(50)
)

CNPJ_LOOKUP_PLAN = sa.select(Issuer).where(Issuer.cnpj == "00000000000191")

_DUMMY_ID = "00000000-0000-0000-0000-000000000000"
ID_LOOKUP_PLAN = sa.select(Issuer).where(Issuer.id == sa.cast(_DUMMY_ID, sa.dialects.postgresql.UUID))

ACTIVE_ONLY_PLAN = (
    sa.select(Issuer).where(Issuer.is_active.is_(True)).order_by(Issuer.name_pt).limit(50)
)


async def _explain_analyze(session: sa.ext.asyncio.AsyncSession, statement: sa.Select) -> str:
    compiled = statement.compile(
        dialect=sa.dialects.postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    )
    sql_str = f"EXPLAIN (ANALYZE, COSTS, VERBOSE) {compiled}"
    result = await session.execute(text(sql_str))
    return "\n".join(row[0] for row in result.fetchall())


async def main() -> None:
    checks_passed = 0
    checks_total = 0

    async with session_scope() as session:
        issuer_count = (await session.execute(text("SELECT count(*) FROM issuers"))).scalar() or 0
        print(f"issuers-table-count={issuer_count}")

        plan1 = await _explain_analyze(session, SECTOR_FILTER_PLAN)
        print(f"--- sector-filter plan ---\n{plan1}\n")

        for pattern, desc in [
            (r"Nested Loop|Hash Join|Merge Join", "join strategy"),
            (r"JOIN industries|industries", "industries join"),
            (r"JOIN sectors|sectors", "sectors join"),
            (r"is_active", "is_active filter"),
        ]:
            checks_total += 1
            if re.search(pattern, plan1, re.IGNORECASE):
                checks_passed += 1
                print(f"  OK   {desc}")
            else:
                print(f"  FAIL {desc}: pattern '{pattern}' not found")

        plan2 = await _explain_analyze(session, CNPJ_LOOKUP_PLAN)
        print(f"\n--- cnpj-lookup plan ---\n{plan2}\n")

        checks_total += 1
        cnpj_pattern = r"Index Scan.*ix_issuers_cnpj|Index Only Scan.*ix_issuers_cnpj|ix_issuers_cnpj"
        if re.search(cnpj_pattern, plan2, re.IGNORECASE):
            checks_passed += 1
            print("  OK   cnpj index scan")
        else:
            print("  FAIL cnpj index scan: ix_issuers_cnpj not used")

        plan3 = await _explain_analyze(session, ID_LOOKUP_PLAN)
        print(f"\n--- id-lookup plan ---\n{plan3}\n")

        checks_total += 1
        if re.search(r"Index Scan.*issuers_pkey|Primary Key|issuers_pkey", plan3, re.IGNORECASE):
            checks_passed += 1
            print("  OK   primary key scan")
        else:
            print("  FAIL primary key scan: issuers_pkey not used")

        plan4 = await _explain_analyze(session, ACTIVE_ONLY_PLAN)
        print(f"\n--- active-only plan ---\n{plan4}\n")

        checks_total += 1
        if "Join" not in plan4 and "JOIN" not in plan4.upper().replace("FULL TABLE SCAN", ""):
            checks_passed += 1
            print("  OK   no join for active-only filter")
        else:
            print("  WARN active-only plan contains join (may be planner choice)")

        checks_total += 1
        if issuer_count > 0:
            checks_passed += 1
            print(f"\n  OK   issuer count is non-zero ({issuer_count})")
        else:
            print("\n  FAIL issuer count is zero; EXPLAIN ANALYZE may be inaccurate")

    print(f"\nquery-plan-checks passed={checks_passed}/{checks_total}")
    if checks_passed == checks_total:
        print("query-plan-checks=PASS")
    else:
        print("query-plan-checks=FAIL")
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
