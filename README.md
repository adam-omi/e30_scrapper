# 🚗 E30 Hunter - Market Monitoring Bot

Skrypt w Pythonie służący do monitorowania portali ogłoszeniowych w poszukiwaniu nowych ofert sprzedaży BMW E30. Program pobiera dane z wielu źródeł, normalizuje je, zapisuje w lokalnej bazie danych i wysyła powiadomienia na żywo przez Telegram.

## 🛠️ Funkcjonalności
* **Multi-Portal Scraping:** Obsługa serwisów OLX, Autoplac i Sprzedajemy.pl przy użyciu wzorca Strategy.
* **Data Cleaning:** Usuwanie śmieciowego kodu CSS/JS oraz normalizacja danych za pomocą Regex.
* **Baza Danych (SQLite):** Automatyczne filtrowanie duplikatów ofert.
* **Telegram Integration:** Natychmiastowe powiadomienia PUSH.

## 🚀 Jak zacząć?
1. Zainstaluj biblioteki: `pip install httpx selectolax`
2. W pliku `main.py` ustaw `USE_TELEGRAM = True` oraz swoje tokeny.
3. Uruchom: `python main.py`