
PETKIT EVERSWEET MAX 2 (CORDLESS)


Bron: User Manual – PETKIT EVERSWEET MAX 2 Smart Pet Drinking Fountain (Model P4116) >
Dit markdown-bestand is bedoeld als technische referentie voor het ontwikkelen van (niet-officiële) integraties, automations en reverse-engineering binnen Home Assistant, en als context input voor GitHub Copilot CLI / vibe coding.




1. Productoverzicht

Productnaam: PETKIT EVERSWEET MAX 2 (Cordless)
Model: P4116
Type: Slimme drinkfontein voor huisdieren
Toepassing: Katten en kleine honden
Capaciteit: 3 liter
Connectiviteit: Bluetooth (BLE)
App: PETKIT App (Android / iOS)


2. Hardware-architectuur
2.1 Hoofdcomponenten

Control Module (met BLE, status LED, batterij)
Wireless Base
Wireless Water Pump
Water Tank
Outlet Pipe
Filter + Filter Holder
304 Stainless Steel Water Tray
⚠️ Belangrijk:

Control Module en Wireless Base NOOIT spoelen of onderdompelen
Waterpomp werkt continu in normale modus → slijtage-afhankelijk


3. Voeding & Energiebeheer
3.1 Voedingsmodi
🔌 Bedraad (5V 1A)

Ondersteunt: Continuous Flow (Normaal)
Intermittent Flow (Interval / schema)
Modus is wisselbaar via: Drukknop op device
PETKIT App (na BLE-connectie)
🔋 Batterij (intern)

Geen live modus-switch mogelijk
Default gedrag: Water: 25 seconden
Pauze: 1 uur
Interval instelbaar in de app (Energy Management)
Hoge frequentie → kortere accuduur


4. Waterdispense-modi

Modus	LED	Gedrag
Normal Mode	Blauw (solid)	Continu stromend water
Intermittent Mode	Groen (solid)	3 min aan / 3 min uit (default)
Battery Mode	Afhankelijk	25s per uur (default)

Opmerking:

Na pauzeren hervat het apparaat automatisch na 10 minuten.


5. LED Status Indicatoren (Belangrijk voor integratie)
5.1 Algemene status

Status	LED
Volledig opgeladen	Solid blauw of groen
Opladen	Knipperend blauw/groen
Lage batterij	Knipperend rood
Apparaatfout	Blauw & groen afwisselend

5.2 Waarschuwingen

Betekenis	LED
Filter vervangen	Knipperend rood
Watertekort	Knipperend rood

Extra gedrag:

Control module verwijderd → water & filter LED solid rood
Terugplaatsen → indicatoren uit


6. Sensorische & Logische Toestanden (afleidbaar)
Op basis van documentatie zijn de volgende logische states relevant voor Home Assistant:
- power_source: mains | battery
- flow_mode: continuous | intermittent | battery_cycle
- battery_level: normal | low
- filter_state: ok | replacement_required
- water_level: ok | shortage
- device_state: working | paused | error


⚠️ Let op: Exacte BLE characteristics & UUIDs zijn niet gedocumenteerd door PETKIT.


7. PETKIT App Functionaliteit
7.1 Homescherm

Live status (online/offline)
Filter levensduur
Energiebeheer
Waterverbruik (referentiewaarden)
Drinkrecords per huisdier / dag
7.2 Synchronisatie

Bluetooth-only, max ±8 meter
Real-time data = alleen binnen BLE-bereik
Remote access mogelijk via interconnection


8. Interconnection (Gateway-modus)

Werkt via ander PETKIT apparaat als master
Ondersteund: PETKIT self-cleaning litter boxes
PETKIT smart feeders
Niet ondersteund:

FRESH ELEMENT P512
FRESH ELEMENT Mini P530
➡️ Dit is geen cloud-API, maar BLE-relay via ander device


9. Relevantie voor Home Assistant
9.1 Kansrijke integratie-methodes

✅ BLE-sniffing (ESP32 / ESPHome)
✅ Reverse engineering via nRF Connect
⚠️ Geen officiële cloud- of LAN-API
9.2 Mogelijke Entities
sensor:
  - battery_status
  - filter_life
  - water_shortage
  - power_source

switch:
  - pause_water

select:
  - flow_mode




10. Onderhoud (operationele logica)

Wekelijks: basisreiniging
Maandelijks: volledige reiniging
Filter → indicator reset via app vereist


11. Veiligheids- & Ontwerpbeperkingen

Alleen voor binnengebruik
Laagspanning (maar kabelbescherming vereist)
Plaatsing moet waterpas zijn
Automatisch hervatten bij pauze


12. Handige Links

Installatievideo: https://youtu.be/lGwNxjT1qQg
Onderhoud & reiniging: https://youtu.be/hV9a_9ug4eE


13. Disclaimer (voor ontwikkelaars)
Dit document:

is geen officiële API documentatie
is bedoeld voor educatief/experimenteel gebruik
respecteert geen garanties of supportvoorwaarden van PETKIT


Gebruik dit markdown-bestand direct als context voor GitHub Copilot CLI bij:

custom Home Assistant integraties
ESPHome BLE reverse-engineering
schema- en state modelling
