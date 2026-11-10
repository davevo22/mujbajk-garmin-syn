"""
Spočítá aktuální nájezd kol a uloží ho do km.json v tomto repozitáři.

Používá oficiální Garmin Connect Personal API (přihlášení API klíčem,
žádné heslo ani ověřovací kód). Toto API nevrací km vybavení přímo,
proto se nájezd každého kola počítá takto:

    km = base_km  +  součet jízd daného typu po datu base_date

Ověřeno 10. 11. 2026 na kole Rose: 7937,2 km + 1771,7 km silničních jízd
= 9708,9 km, Garmin u kola ukazoval 9709 km.

API klíč se čte z proměnné prostředí GARMIN_PERSONAL_API_KEY
(v GitHub Actions uložený jako "Secret", nikdy není vidět v kódu).
"""

import json
import os
import sys
from datetime import date, timedelta

from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
    resolve_api_key,
)

# Kola: výchozí stav km v Garminu na konci dne base_date a typy aktivit,
# které se kolu započítají. První kolo je "hlavní" (kvůli starší verzi appky).
BIKES = [
    {
        "name": "Rose Xlite 06",
        "base_km": 7937.2,
        "base_date": "2026-09-20",
        "types": ["road_biking"],
    },
    {
        "name": "Mondraker Podium",
        "base_km": 2350.8,
        "base_date": "2026-11-10",
        "types": ["mountain_biking"],
    },
]

PAGE_SIZE = 100


def main() -> None:
    if not os.environ.get("GARMIN_PERSONAL_API_KEY"):
        print("Chybí GARMIN_PERSONAL_API_KEY v prostředí.", file=sys.stderr)
        sys.exit(1)

    earliest = min(date.fromisoformat(b["base_date"]) for b in BIKES) + timedelta(days=1)

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(resolve_api_key())

    activities = []
    with GarminPersonalApiClient(token.access_token) as client:
        start = 0
        while True:
            page = client.search_activities(
                start=start,
                limit=PAGE_SIZE,
                start_date=earliest.isoformat(),
                end_date=date.today().isoformat(),
            )
            if isinstance(page, dict):
                page = next((v for v in page.values() if isinstance(v, list)), [])
            if not page:
                break
            activities.extend(page)
            if len(page) < PAGE_SIZE or start > 20000:
                break
            start += PAGE_SIZE

    # Zjednodušené aktivity: (den, typ, metry). Do logu jdou jen součty -
    # žádné názvy ani místa jízd (repozitář je veřejný).
    rides = []
    for activity in activities:
        day = str(activity.get("startTimeLocal") or activity.get("startTimeGMT") or "")[:10]
        type_key = str((activity.get("activityType") or {}).get("typeKey") or "neznamy")
        rides.append((day, type_key, float(activity.get("distance") or 0)))

    all_types = {t for b in BIKES for t in b["types"]}
    unused = {}
    for day, type_key, meters in rides:
        if type_key not in all_types:
            entry = unused.setdefault(type_key, [0, 0.0])
            entry[0] += 1
            entry[1] += meters

    results = []
    for bike in BIKES:
        counted = [m for day, t, m in rides if t in bike["types"] and day > bike["base_date"]]
        km = round(bike["base_km"] + sum(counted) / 1000, 1)
        results.append({"gear_name": bike["name"], "km": km})
        print(
            f"{bike['name']}: {bike['base_km']} km k {bike['base_date']} + "
            f"{len(counted)} jízd ({sum(counted) / 1000:.1f} km, typy {', '.join(bike['types'])}) = {km} km"
        )

    if unused:
        print(f"Nezapočtené typy aktivit od {earliest.isoformat()}:")
        for type_key, (count, meters) in sorted(unused.items()):
            print(f"  {type_key}: {count} aktivit, {meters / 1000:.1f} km")

    output = {
        "gear_name": results[0]["gear_name"],
        "km": results[0]["km"],
        "source": "garmin_personal_api",
        "bikes": results,
    }

    with open("km.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Uloženo: {output}")


if __name__ == "__main__":
    main()
