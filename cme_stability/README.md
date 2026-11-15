# CME EURUSD – 5 Handelstage JSON-Stabilitätstest

Isolierter lesender Verbindungstest des undokumentierten CME-Website-Endpunkts. **Kein TradingView-Export, keine PDF-Auswertung, keine Änderung anderer Dashboarddateien.**

- EURUSD (Produkt 8116), Optionsverfall Dezember 2026 (Z26), reporttype P.
- Montag bis Freitag um 20:17 Uhr Europe/Berlin, jeweils der letzte vorangegangene Werktag.
- Call-/Put-Gruppen, Strike-Zeilen, Duplikate, OI-/Volumensummen und XLS-Referenz vom 13.11.2026 werden geprüft.
- Nur history.json und summary.json mit Prüfergebnissen. Keine vollständigen CME-Ketten im Repo.
- Ab fünf unterschiedlichen erfolgreichen Handelstagen werden weitere CME-Aufrufe automatisch übersprungen.
- Fehlgeschlagene Abrufe werden protokolliert und als fehlgeschlagene Actions-Läufe markiert.

## Manueller Test
Actions → „CME EURUSD – JSON-Stabilitätstest“ → Run workflow. Optional trade_date=20261113.

## Ausschalten
Actions → Workflow → ... → Disable workflow.

## Grenzen
Undokumentierter CME-Endpunkt; GitHub-Server können anders behandelt werden als ein Windows-PC (z. B. 403 oder leere Daten). GitHub-Schedules können verzögert werden. Dies ist nur ein Verbindungstest, keine garantierte Datenversorgung.
