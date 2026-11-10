"""
Přečte z Garmin Connect nájezd km konkrétního kola (z vybavení / gear)
a uloží ho do souboru km.json v tomto repozitáři.

Přihlašuje se API klíčem přes Garmin Connect Personal API (žádné heslo ani
ověřovací kód). Klíč se čte z proměnné prostředí GARMIN_PERSONAL_API_KEY
(v GitHub Actions uložený jako "Secret", nikdy není vidět v kódu).

Pozn.: vybavení není v dokumentaci Personal API uvedené. Skript zkouší
stejné adresy, jaké používá web Garmin Connect, a do logu vypíše, jak
každý pokus dopadl. Když Garmin přístup k vybavení nepovolí, skončí chybou
a km.json nechá beze změny.
"""

import json
import os
import sys

from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
    resolve_api_key,
)
from garmin_personal_api.errors import GarminPersonalApiError, HttpError

GEAR_NAME_FILTER = os.environ.get("GEAR_NAME_FILTER", "")  # např. "Rose" - volitelné
PROFILE_PK = os.environ.get("GARMIN_PROFILE_PK", "")       # volitelné číslo profilu


def try_get(client, path, params=None):
    """Zavolá adresu a vypíše výsledek. Vrací data, nebo None při chybě."""
    try:
        data = client.get(path, params=params)
        print(f"  OK   {path}")
        return data
    except HttpError as error:
        print(f"  HTTP {error.status_code}  {path}  {error.response_text.strip()[:200]}")
    except GarminPersonalApiError as error:
        print(f"  CHYBA  {path}  {str(error)[:200]}")
    return None


def find_profile_pk(client):
    """Číselné ID profilu - Garmin ho vrací na několika místech."""
    if PROFILE_PK:
        return PROFILE_PK
    attempts = [
        ("/userprofile-service/userprofile/settings", ("id", "userProfilePk", "userProfileNumber")),
        ("/device-service/deviceservice/mylastused", ("userProfileNumber",)),
        ("/userprofile-service/socialProfile", ("profileId", "id")),
    ]
    for path, keys in attempts:
        data = try_get(client, path)
        if isinstance(data, dict):
            for key in keys:
                if data.get(key):
                    return str(data[key])
    return ""


def gear_name_of(gear):
    return gear.get("displayName") or gear.get("customMakeModel") or ""


def main() -> None:
    if not os.environ.get("GARMIN_PERSONAL_API_KEY"):
        print("Chybí GARMIN_PERSONAL_API_KEY v prostředí.", file=sys.stderr)
        sys.exit(1)

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(resolve_api_key())
    print("Přihlášení API klíčem proběhlo.")

    with GarminPersonalApiClient(token.access_token) as client:
        print("Hledám číslo profilu:")
        profile_pk = find_profile_pk(client)
        if not profile_pk:
            print("Nepodařilo se zjistit číslo profilu.", file=sys.stderr)
            sys.exit(1)

        print("Načítám seznam vybavení:")
        gear_list = try_get(client, "/gear-service/gear/filterGear", {"userProfilePk": profile_pk})
        if not isinstance(gear_list, list) or not gear_list:
            print("Personal API nevrátilo žádné vybavení.", file=sys.stderr)
            sys.exit(1)

        print("Nalezené vybavení: " + ", ".join(gear_name_of(g) or "(bez názvu)" for g in gear_list))

        # Pokud je nastavený filtr podle jména, použijeme první shodu, jinak první položku.
        chosen = None
        if GEAR_NAME_FILTER:
            for gear in gear_list:
                if GEAR_NAME_FILTER.lower() in gear_name_of(gear).lower():
                    chosen = gear
                    break
        if chosen is None:
            chosen = gear_list[0]
        print(f"Vybrané vybavení: {gear_name_of(chosen)}")

        print("Načítám statistiky vybavení:")
        gear_stats = try_get(client, f"/gear-service/gear/stats/{chosen.get('uuid')}")
        if not isinstance(gear_stats, dict):
            print("Personal API nevrátilo statistiky vybavení.", file=sys.stderr)
            sys.exit(1)

    distance_meters = (
        gear_stats.get("totalDistance")
        or gear_stats.get("distance")
        or gear_stats.get("totalDistanceInMeters")
    )
    if distance_meters is None:
        print(
            "Ve statistikách chybí vzdálenost. Dostupná pole: " + ", ".join(sorted(gear_stats.keys())),
            file=sys.stderr,
        )
        sys.exit(1)

    output = {
        "gear_name": gear_name_of(chosen),
        "km": round(distance_meters / 1000, 1),
        "source": "garmin_connect",
    }

    with open("km.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Uloženo: {output}")


if __name__ == "__main__":
    main()
