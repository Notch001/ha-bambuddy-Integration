# Bambuddy für Home Assistant

Inoffizielle Home-Assistant-Integration für [Bambuddy](https://github.com/maziggy/bambuddy), die selbst gehostete Verwaltung für Bambu-Lab-Drucker.

Sie zeigt dir in Home Assistant:

- **Den Zustand jedes Druckers:** Status, aktueller Druck, Fortschritt, Restzeit, voraussichtliches Ende, Schicht, Temperaturen, Online/Offline, Fehler, „Druckplatte räumen“.
- **Die Warteschlange:** wartende und laufende Druckaufträge, insgesamt und pro Drucker, mit der Liste der Aufträge als Attribut.

Die Integration liest nur. Sie startet, stoppt oder ändert nichts in Bambuddy.

## Voraussetzungen

- Home Assistant 2025.3 oder neuer
- Ein laufender Bambuddy-Server, den Home Assistant im Netzwerk erreicht
- [HACS](https://hacs.xyz/) (empfohlen)

## Installation

### 1. API-Schlüssel in Bambuddy anlegen

Nur nötig, wenn in Bambuddy die Anmeldung eingeschaltet ist.

1. Bambuddy im Browser öffnen → **Einstellungen** → **API-Schlüssel**.
2. **Schlüssel erstellen**, Name z. B. `Home Assistant`.
3. Nur **Status lesen** anhaken, alle anderen Rechte können aus bleiben.
4. Den angezeigten Schlüssel (beginnt mit `bb_`) **sofort kopieren**. Er wird nur einmal angezeigt.

### 2. Integration über HACS installieren

1. In Home Assistant **HACS** öffnen.
2. Oben rechts auf die drei Punkte **⋮** → **Benutzerdefinierte Repositories**.
3. Als Repository `https://github.com/Notch001/ha-bambuddy-integration` eintragen, als Typ **Integration** wählen → **Hinzufügen**.
4. In HACS nach **Bambuddy** suchen, öffnen und **Herunterladen** klicken.
5. Home Assistant neu starten (**Einstellungen** → **System** → oben rechts Ein/Aus-Symbol → **Home Assistant neu starten**).

<details>
<summary>Ohne HACS (manuell)</summary>

Den Ordner `custom_components/bambuddy` aus diesem Repository nach `/config/custom_components/bambuddy` in deine Home-Assistant-Installation kopieren (z. B. mit dem Add-on „File editor“ oder „Samba share“), dann Home Assistant neu starten.
</details>

### 3. Integration einrichten

1. **Einstellungen** → **Geräte & Dienste** → unten rechts **Integration hinzufügen** → **Bambuddy** suchen.
2. **Bambuddy-Adresse** eintragen, also dieselbe Adresse, mit der du Bambuddy im Browser öffnest, z. B. `http://192.168.1.50:8000`.
3. Den **API-Schlüssel** aus Schritt 1 einfügen, oder das Feld leer lassen, wenn Bambuddy keine Anmeldung nutzt.
4. **Absenden**. Danach erscheinen ein Gerät „Bambuddy“ für die Warteschlange und ein Gerät pro Drucker.

Neu in Bambuddy angelegte Drucker tauchen automatisch auf. Das Abfrageintervall (Standard: 30 Sekunden) lässt sich unter **Konfigurieren** bei der Integration ändern.

## Entitäten

### Pro Drucker

| Entität | Beschreibung |
|---|---|
| Status | Bereit, Vorbereitung, Druckt, Pausiert, Fertig, Fehlgeschlagen, Offline |
| Aktueller Druck | Name des laufenden Drucks |
| Fortschritt | in % |
| Restzeit | in Minuten |
| Voraussichtliches Ende | Uhrzeit |
| Aktuelle Schicht / Schichten gesamt | |
| Düsen-, Bett-, Bauraumtemperatur | Ist- und Zielwerte (Bauraum und zweite Düse nur, wenn der Drucker sie meldet) |
| Warteschlange | Anzahl der Aufträge, die fest diesem Drucker zugewiesen sind; Attribute `next_job` und `jobs` |
| Fehlermeldungen | Anzahl der HMS-Meldungen; Details im Attribut `errors` |
| Online, Druckt, Fehler, Druckplatte räumen | An/Aus-Sensoren |
| Tür, WLAN-Signal | standardmäßig deaktiviert, bei Bedarf einschalten |

### Bambuddy (Warteschlange)

| Entität | Beschreibung |
|---|---|
| Wartende Druckaufträge | Anzahl; Attribute `next_job` und `jobs` (max. 50 Einträge) |
| Laufende Druckaufträge | Anzahl; Attribut `jobs` |

Jeder Eintrag in `jobs` enthält: `id`, `name`, `status`, `printer` (bei nicht zugewiesenen Aufträgen z. B. „Any A1 Mini“), `position`, `scheduled_time`, `started_at`, `print_time_minutes`, `filament_type`, `filament_grams`, `manual_start`, `waiting_reason`.

## Beispiel: Warteschlange auf dem Dashboard

Eine Markdown-Karte. Ersetze `sensor.bambuddy_wartende_druckauftrage` durch die Entitäts-ID deines Sensors „Wartende Druckaufträge“. Du findest sie unter **Einstellungen** → **Geräte & Dienste** → **Bambuddy** → Gerät **Bambuddy**.

```yaml
type: markdown
title: Druck-Warteschlange
content: >
  {% set jobs = state_attr('sensor.bambuddy_wartende_druckauftrage', 'jobs') or [] %}
  {% for job in jobs %}
  {{ loop.index }}. **{{ job.name }}** – {{ job.printer or 'beliebiger Drucker' }}
  {%- if job.print_time_minutes %} ({{ job.print_time_minutes }} min){% endif %}
  {% else %}
  Keine Aufträge in der Warteschlange.
  {% endfor %}
```

## Entwicklung

```bash
pip install -r requirements_test.txt
python -m pytest
```
