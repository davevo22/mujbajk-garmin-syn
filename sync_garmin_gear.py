"""
Přečte z Garmin Connect nájezd km konkrétního kola (z vybavení / gear)
a uloží ho do souboru km.json v tomto repozitáři.

Přihlašovací údaje se čtou z proměnných prostředí GARMIN_EMAIL a GARMIN_PASSWORD
(v GitHub Actions se nastavují jako "Secrets", nikdy nejsou vidět v kódu).
"""

import json
import os
import sys

from garminconnect import Garmin

GEAR_NAME_FILTER = os.environ.get("GEAR_NAME_FILTER", "")  # např. "Rose" - volitelné


def main() -> None:
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")

    if not email or not password:
        print("Chybí GARMIN_EMAIL nebo GARMIN_PASSWORD v prostředí.", file=sys.stderr)
        sys.exit(1)

    api = Garmin(email, password)
    api.login()

    gear_list = api.get_gear(api.get_full_name())

    # Vypíšeme si SUROVÁ data pro ladění - uvidíme přesně, jak Garmin
    # pojmenovává pole (název kola, ujeté km...). Tohle se objeví v logu
    # GitHub Actions, takže si podle toho můžeme upravit filtr/pole níž.
    print("Nalezené vybavení:")
    print(json.dumps(gear_list, indent=2, ensure_ascii=False))

    if not gear_list:
        print("Garmin nevrátil žádné vybavení.", file=sys.stderr)
        sys.exit(1)

    # Pokud je nastavený filtr podle jména, použijeme první shodu.
    # Jinak vezmeme první položku v seznamu (uprav si dle potřeby po prvním běhu).
    chosen = None
    if GEAR_NAME_FILTER:
        for gear in gear_list:
            name = gear.get("displayName") or gear.get("customMakeModel") or ""
            if GEAR_NAME_FILTER.lower() in name.lower():
                chosen = gear
                break
    if chosen is None:
        chosen = gear_list[0]

    print("Vybrané vybavení:")
    print(json.dumps(chosen, indent=2, ensure_ascii=False))

    # Pole s ujetou vzdáleností se může jmenovat různě podle verze API -
    # zkusíme několik obvyklých názvů.
    distance_meters = (
        chosen.get("totalDistance")
        or chosen.get("distance")
        or chosen.get("totalDistanceInMeters")
    )

    if distance_meters is None:
        print(
            "Nepodařilo se najít pole se vzdáleností - podívej se do výpisu "
            "výše a uprav skript podle skutečného názvu pole.",
            file=sys.stderr,
        )
        sys.exit(1)

    km = round(distance_meters / 1000, 1)

    output = {
        "gear_name": chosen.get("displayName") or chosen.get("customMakeModel") or "",
        "km": km,
        "source": "garmin_connect",
    }

    with open("km.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Uloženo: {output}")


if __name__ == "__main__":
    main()
