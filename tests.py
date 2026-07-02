import requests
import urllib3

# Wyłączenie ostrzeżeń SSL (tylko do testów)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================================================
# Konfiguracja
# ======================================================

URL = "https://twoj-endpoint.pl/api/esg"

TOKEN = "TU_WKLEJ_TOKEN"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ======================================================
# Dane testowe
# ======================================================

test_cases = [
    {
        "lat": 54.42727,
        "lng": 16.40220,
        "expected": "wysokie"
    },
    {
        "lat": 54.78404,
        "lng": 18.41469,
        "expected": "niskie"
    },
    {
        "lat": 49.59994,
        "lng": 20.75095,
        "expected": "brak ryzyka"
    }
]

# ======================================================
# Liczniki
# ======================================================

passed = 0
failed = 0

print("=" * 80)
print("START TESTÓW")
print("=" * 80)

# ======================================================
# Testowanie endpointu
# ======================================================

for i, case in enumerate(test_cases, start=1):

    payload = {
        "lat": case["lat"],
        "lng": case["lng"]
    }

    try:

        response = requests.post(
            URL,
            headers=headers,
            json=payload,
            timeout=20,
            verify=False
        )

        if response.status_code != 200:
            failed += 1

            print(f"\nTEST {i} - HTTP ERROR")
            print(f"LAT        : {case['lat']}")
            print(f"LNG        : {case['lng']}")
            print(f"HTTP CODE  : {response.status_code}")
            print(f"RESPONSE   : {response.text}")

            continue

        data = response.json()

        # Zmień nazwę pola, jeśli endpoint zwraca inną
        actual = data.get("score")

        if actual == case["expected"]:

            passed += 1

            print(f"\nTEST {i} - PASSED")
            print(f"LAT        : {case['lat']}")
            print(f"LNG        : {case['lng']}")
            print(f"EXPECTED   : {case['expected']}")
            print(f"ACTUAL     : {actual}")

        else:

            failed += 1

            print(f"\nTEST {i} - FAILED")
            print(f"LAT        : {case['lat']}")
            print(f"LNG        : {case['lng']}")
            print(f"EXPECTED   : {case['expected']}")
            print(f"ACTUAL     : {actual}")
            print(f"RESPONSE   : {data}")

    except requests.exceptions.RequestException as e:

        failed += 1

        print(f"\nTEST {i} - CONNECTION ERROR")
        print(f"LAT        : {case['lat']}")
        print(f"LNG        : {case['lng']}")
        print(f"ERROR      : {e}")

    except ValueError:

        failed += 1

        print(f"\nTEST {i} - INVALID JSON")
        print(f"LAT        : {case['lat']}")
        print(f"LNG        : {case['lng']}")
        print(f"RESPONSE   : {response.text}")

# ======================================================
# Podsumowanie
# ======================================================

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"TOTAL TESTS : {passed + failed}")
print(f"PASSED      : {passed}")
print(f"FAILED      : {failed}")