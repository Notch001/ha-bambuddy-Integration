# Bambuddy für Home Assistant

<img src="custom_components/bambuddy/brand/icon.png" alt="" width="72" align="right">

🇬🇧 [English](README.md)

Inoffizielle Home-Assistant-Integration für [Bambuddy](https://github.com/maziggy/bambuddy), die selbst gehostete Verwaltung für Bambu-Lab-Drucker.

- **Druckerstatus:** Status, aktueller Druck mit Vorschau, Fortschritt, Restzeit, voraussichtliches Ende, Schicht, Temperaturen, Online/Offline, Fehler, „Druckplatte räumen“.
- **Warteschlange:** wartende und laufende Aufträge, insgesamt und pro Drucker, als To-do-Liste und als Sensoren.
- **AMS und Filament:** pro Slot Filament mit Farbe (z. B. „PLA Basic · Jade White“) und Restmenge, dazu Luftfeuchtigkeit und Temperatur jedes AMS.
- **Kamera:** Kamerabild und Livestream, über Bambuddy weitergeleitet.
- **Steuerung:** Pausieren, Fortsetzen, Abbrechen, Druckplatte als geräumt bestätigen, Bauraumbeleuchtung, Druckgeschwindigkeit.
- **Dashboard-Karte:** eine Karte für alle Drucker und die Warteschlange, wird mitgeliefert und automatisch geladen.

<img src="docs/card.png" alt="Bambuddy-Karte (Beispieldaten)" width="640">

## Voraussetzungen

- Home Assistant 2025.3 oder neuer (ab 2026.3 mit Integrations-Icon)
- Ein laufender Bambuddy-Server, den Home Assistant im Netzwerk erreicht
- [HACS](https://hacs.xyz/) (empfohlen)

## Installation

### 1. API-Schlüssel in Bambuddy anlegen

Nur nötig, wenn in Bambuddy die Anmeldung eingeschaltet ist.

1. Bambuddy öffnen → **Einstellungen** → **API-Schlüssel** → **Schlüssel erstellen**, Name z. B. `Home Assistant`.
2. **Status lesen** anhaken. Um Drucker aus Home Assistant zu steuern (Pause, Abbrechen, Licht, Geschwindigkeit), zusätzlich **Drucker steuern**. Alles andere kann aus bleiben.
3. Den Schlüssel (beginnt mit `bb_`) **sofort kopieren**. Er wird nur einmal angezeigt.

### 2. Über HACS installieren

1. **HACS** öffnen → oben rechts **⋮** → **Benutzerdefinierte Repositories**.
2. Repository `https://github.com/Notch001/ha-bambuddy-integration`, Typ **Integration** → **Hinzufügen**.
3. In HACS nach **Bambuddy** suchen, öffnen und **Herunterladen** klicken.
4. Home Assistant neu starten.

<details>
<summary>Ohne HACS</summary>

Den Ordner `custom_components/bambuddy` aus diesem Repository nach `/config/custom_components/bambuddy` kopieren und Home Assistant neu starten.
</details>

### 3. Integration einrichten

1. **Einstellungen** → **Geräte & Dienste** → **Integration hinzufügen** → **Bambuddy**.
2. **Bambuddy-Adresse** eintragen, also dieselbe Adresse wie im Browser, z. B. `http://192.168.1.50:8000`.
3. Den **API-Schlüssel** einfügen, oder leer lassen, wenn Bambuddy keine Anmeldung nutzt.

Danach gibt es ein Gerät „Bambuddy“ für die Warteschlange und ein Gerät pro Drucker. Später hinzugefügte Drucker, AMS-Einheiten und Spulen erscheinen automatisch. Das Abfrageintervall (Standard 30 s) lässt sich unter **Konfigurieren** ändern.

## Dashboard-Karte

Die Integration bringt eine eigene Karte mit und trägt sie automatisch als Dashboard-Ressource ein. Es muss nichts extra installiert werden.

**Hinzufügen:** Dashboard bearbeiten → **Karte hinzufügen** → nach **Bambuddy** suchen. Die Karte findet alle Drucker selbst. Im Karteneditor kannst du Drucker auswählen und Bereiche ein- und ausblenden.

```yaml
type: custom:bambuddy-card
title: 3D-Drucker            # optional
printers: []                 # optional: Geräte-IDs, leer = alle Drucker
show_temperatures: true
show_ams: true
show_controls: true          # braucht das Recht „Drucker steuern“
show_camera: false
show_printer_queue: true     # Aufträge für einen Drucker direkt unter dem Drucker
show_queue: true             # alle übrigen Aufträge (beliebiger Drucker / Drucker nicht auf der Karte)
collapse_queue: false        # Auftragslisten anfangs eingeklappt
queue_limit: 5               # max. Aufträge je Liste
```

Jeder Drucker bekommt eine eigene Kachel, deren farbiger oberer Rand den Status zeigt. Auf breiten Bildschirmen stehen die Kacheln nebeneinander, am Handy untereinander. Ein Tipp auf einen Wert öffnet die Details; „Abbrechen“ fragt vorher nach.

Die Auftragslisten lassen sich mit einem Tipp auf ihre Überschrift ein- und ausklappen; eingeklappt zeigt die Druckerliste weiterhin den nächsten Auftrag. Der Browser merkt sich, was eingeklappt ist.

**Eine Karte pro Drucker:** Wer lieber getrennte Karten möchte (z. B. eine pro Spalte im Abschnitte-Dashboard), fügt die Karte mehrmals hinzu, wählt in jeder einen Drucker aus (`printers: [<Geräte-ID>]`) und schaltet `show_queue` bei allen außer einer aus.

## Entitäten

### Pro Drucker

| Entität | Beschreibung |
|---|---|
| Status | Bereit, Vorbereitung, Druckt, Pausiert, Fertig, Fehlgeschlagen, Offline |
| Aktueller Druck, Druckphase | Dateiname; z. B. „Heatbed preheating“ |
| Fortschritt, Restzeit, Voraussichtliches Ende | %, Minuten, Uhrzeit |
| Aktuelle Schicht, Schichten gesamt | |
| Düsen-, Bett-, Bauraumtemperatur | Ist- und Zielwerte (Bauraum und zweite Düse nur, wenn gemeldet) |
| Warteschlange | Aufträge, die fest diesem Drucker zugewiesen sind; Attribute `next_job`, `jobs` |
| Fehlermeldungen | Anzahl der HMS-Meldungen; Details in `errors` |
| Online, Druckt, Fehler, Druckplatte räumen | An/Aus-Sensoren |
| Düse | Durchmesser; Typ in `nozzles` |
| Druckvorschau | Bild des laufenden Drucks |
| Kamera | Kamerabild und Livestream |
| Tür, WLAN-Signal, Lüfter, SD-Karte, Zeitraffer | standardmäßig deaktiviert |

### AMS und Filament

| Entität | Beschreibung |
|---|---|
| AMS 1 Slot 1 … | Filament und Farbe, z. B. „PLA Basic · Jade White“, sonst „Leer“/„Unbekannt“. Farbnamen aus dem Farbkatalog von Bambuddy, sonst ein Grundfarbname. Das Bild ist eine Spule in der Filamentfarbe. Attribute: `type`, `color`, `color_name`, `remaining` (%, nur RFID-Spulen), `nozzle_temp_min`, `nozzle_temp_max`, `active`, `ams`, `slot` |
| Externe Spule | dasselbe für den Spulenhalter außen |
| AMS 1 Luftfeuchtigkeit / Temperatur | |
| AMS 1 Trocknung Restzeit | nur wenn das AMS trocknen kann |

### Steuerung (braucht das Recht „Drucker steuern“)

| Entität | Beschreibung |
|---|---|
| Pausieren / Fortsetzen / Druck abbrechen | Knöpfe, nur aktiv, wenn es gerade passt |
| Druckplatte geräumt | meldet Bambuddy, dass die Platte frei ist, damit der nächste Auftrag starten kann |
| Bauraumbeleuchtung | an/aus |
| Druckgeschwindigkeit | Leise, Standard, Sport, Turbo (während eines Drucks) |

Ohne das Recht zeigt Home Assistant beim Drücken eine Fehlermeldung, sonst passiert nichts.

### Bambuddy (Warteschlange)

| Entität | Beschreibung |
|---|---|
| Wartende Druckaufträge | Anzahl; Attribute `next_job`, `jobs` (max. 50) |
| Laufende Druckaufträge | Anzahl; Attribut `jobs` |
| Druck-Warteschlange | die Warteschlange als **To-do-Liste** (nur lesen): laufende Aufträge (▶) oben, darunter die wartenden in der Reihenfolge, in der Bambuddy sie startet |

Jeder Eintrag in `jobs` enthält `id`, `name`, `status`, `printer`, `printer_id`, `position`, `scheduled_time`, `started_at`, `print_time_minutes`, `filament_type`, `filament_grams`, `manual_start`, `waiting_reason`.

Die To-do-Liste erscheint in der Seitenleiste unter **To-do-Listen** und lässt sich mit der eingebauten Karte **To-do-Liste** aufs Dashboard legen.

## Updates

Jede neue Version erscheint als Release auf GitHub. HACS prüft regelmäßig darauf und meldet sie unter **Einstellungen** → **Updates**. Sofort prüfen: HACS → **Bambuddy** → **⋮** → **Informationen aktualisieren**. Nach dem Update Home Assistant neu starten.

## Fehlerbehebung

**Die Karte zeigt „Konfigurationsfehler“ / „Custom element doesn't exist“ (oft nur am Handy).** Browser oder App haben das Skript der Karte noch nicht geladen. Seite neu laden. In der Companion-App: **Einstellungen** → **Companion App** → **Debugging** → **Frontend-Cache zurücksetzen**, dann die App neu öffnen. Ab 0.7.0 ist die Karte zusätzlich unter **Einstellungen** → **Dashboards** → **⋮** → **Ressourcen** eingetragen; diese Liste laden auch die Apps zuverlässig.

**Steuerknöpfe zeigen einen Fehler.** Dem API-Schlüssel fehlt das Recht **Drucker steuern**. Schlüssel in Bambuddy bearbeiten oder neu anlegen.

**Debug-Protokoll:** **Einstellungen** → **Geräte & Dienste** → **Bambuddy** → **Debug-Protokollierung aktivieren**.

## Entwicklung

```bash
pip install -r requirements_test.txt
python -m pytest
```

Ein Release entsteht automatisch, wenn sich die Version in `custom_components/bambuddy/manifest.json` auf `main` ändert.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Ein Community-Projekt, nicht verbunden mit dem Bambuddy-Projekt oder Bambu Lab.
