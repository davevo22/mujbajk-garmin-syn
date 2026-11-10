"""
ZKUŠEBNÍ VERZE - nic neukládá, km.json nechává beze změny.

Vypíše, kolik km mají od 20. 9. 2026 jednotlivé typy aktivit
(silniční kolo, horské kolo...). Podle toho poznáme, jestli se dají
jízdy na silničním a horském kole od sebe rozlišit.

Do logu jdou jen součty - žádné názvy ani místa jízd.
"""

import os
import sys
from datetime import date

from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
    resolve_api_key,
)

SINCE = "2026-09-20"   # den poslední úspěšné synchronizace (7937,2 km)
PAGE_SIZE = 100


def main() -> None:
    if not os.environ.get("GARMIN_PERSONAL_API_KEY"):
        print("Chybí GARMIN_PERSONAL_API_KEY v prostředí.", file=sys.stderr)
        sys.exit(1)

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(resolve_api_key())

    activities = []
    with GarminPersonalApiClient(token.access_token) as client:
        start = 0
        while True:
            page = client.search_activities(
                start=start, limit=PAGE_SIZE,
                start_date=SINCE, end_date=date.today().isoformat(),
            )
            if isinstance(page, dict):
                page = next((v for v in page.values() if isinstance(v, list)), [])
            if not page:
                break
            activities.extend(page)
            if len(page) < PAGE_SIZE or start > 20000:
                break
            start += PAGE_SIZE

    print(f"Aktivit od {SINCE}: {len(activities)}")
    if activities:
        print("Pole v odpovědi: " + ", ".join(sorted(activities[0].keys())))

    totals = {}      # typ -> [počet, metry] od 21. 9.
    first_day = {}   # typ -> [počet, metry] jen 20. 9.
    for activity in activities:
        day = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")[:10]
        type_key = str((activity.get("activityType") or {}).get("typeKey") or "neznamy")
        meters = float(activity.get("distance") or 0)
        bucket = first_day if day == SINCE else totals
        entry = bucket.setdefault(type_key, [0, 0.0])
        entry[0] += 1
        entry[1] += meters

    print(f"Součty od 21. 9. 2026 (bez dne {SINCE}):")
    for type_key, (count, meters) in sorted(totals.items()):
        print(f"  {type_key}: {count} aktivit, {meters / 1000:.1f} km")
    print(f"Jen den {SINCE}:")
    for type_key, (count, meters) in sorted(first_day.items()):
        print(f"  {type_key}: {count} aktivit, {meters / 1000:.1f} km")
    print("Pro srovnání: Garmin u kola Rose ukazuje 9709 km, při poslední synchronizaci 7937,2 km -> rozdíl 1771,8 km.")


if __name__ == "__main__":
    main()
