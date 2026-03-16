# Fuel Finder for Home Assistant

A Home Assistant custom integration for the UK Government [Fuel Finder](https://www.fuel-finder.service.gov.uk) API. Track real-time fuel prices and station status at the forecourts you care about.

## What it does

Configure one or more petrol stations by searching for them during setup. The integration then polls for price updates and exposes:

### Per station (device)

| Entity | Type | Description |
|---|---|---|
| E5 price | Sensor | Super unleaded price in pence/litre |
| E10 price | Sensor | Unleaded price in pence/litre |
| B7 price | Sensor | Standard diesel price in pence/litre |
| B7 Premium price | Sensor | Premium diesel price in pence/litre |
| B10 price | Sensor | B10 diesel price in pence/litre |
| HVO price | Sensor | HVO diesel price in pence/litre |
| Open | Binary sensor | Whether the station is currently open |

Only fuel types sold at that station are created. Prices include `price_last_updated` and `price_change_effective_timestamp` as attributes.

### Cheapest fuel sensors

Aggregate sensors that compare prices across all your tracked stations:

| Entity | Type | Description |
|---|---|---|
| Cheapest E5 | Sensor | Lowest E5 price across all tracked stations |
| Cheapest E10 | Sensor | Lowest E10 price across all tracked stations |
| Cheapest B7 | Sensor | Lowest B7 price across all tracked stations |
| Cheapest B7 Premium | Sensor | Lowest B7 Premium price across all tracked stations |
| Cheapest B10 | Sensor | Lowest B10 price across all tracked stations |
| Cheapest HVO | Sensor | Lowest HVO price across all tracked stations |

Each cheapest sensor includes attributes:

- `station_name` — which station has the cheapest price
- `station_address` — address of that station
- `runner_up_price` — second cheapest price
- `runner_up_station` — second cheapest station name
- `cheapest_3` — list of the top 3 cheapest (name, price, address) for dashboard use

Only created for fuel types that at least one tracked station sells.

### Device attributes

Each station device carries:

- Brand name
- Address and postcode
- GPS coordinates (used for distance-from-home calculations)
- Amenities (car wash, toilets, AdBlue, water)
- Motorway / supermarket flags
- Opening hours

## Setup

You need API credentials from the Fuel Finder service (OAuth2 client ID and secret). Add the integration through **Settings > Devices & Services > Add Integration** and search for "Fuel Finder".

The config flow will:

1. Ask for your OAuth2 client ID and client secret
2. Let you search for stations by postcode or name
3. Select which stations to track (searchable dropdown)
4. Choose which fuel types to monitor (e.g. just unleaded and diesel)

You can add more stations later by reconfiguring the integration.

## Requirements

- Home Assistant 2024.1+
- Fuel Finder API credentials (client ID and client secret)

## Installation

### HACS (recommended)

Add this repository as a custom repository in HACS, then install "Fuel Finder".

### Manual

Copy `custom_components/fuel_finder/` to your Home Assistant `config/custom_components/` directory and restart.

## Dashboard ideas

### Map with prices on pins

Station sensors include `latitude` and `longitude` attributes, so they work with the Map card. Use `label_mode: state` to show the price directly on each pin instead of initials:

```yaml
type: map
entities:
  - entity: sensor.my_local_tesco_unleaded_e10_price
    label_mode: state
  - entity: sensor.shell_high_street_unleaded_e10_price
    label_mode: state
  - entity: sensor.bp_main_road_unleaded_e10_price
    label_mode: state
```

### Cheapest fuel glance card

A quick overview of the best prices across all your tracked stations:

```yaml
type: entities
title: Cheapest fuel
entities:
  - entity: sensor.fuel_finder_cheapest_e10
    name: Unleaded
  - entity: sensor.fuel_finder_cheapest_b7_standard
    name: Diesel
```

The attribution line beneath each row shows which station has the cheapest price.

### Price history graph

Track how prices change over time at a specific station or across the cheapest sensors:

```yaml
type: history-graph
title: Diesel price history
hours_to_show: 168
entities:
  - entity: sensor.fuel_finder_cheapest_b7_standard
    name: Cheapest diesel
  - entity: sensor.my_local_tesco_diesel_b7_price
    name: Local Tesco
  - entity: sensor.shell_high_street_diesel_b7_price
    name: Shell High Street
```

### Conditional card for price alerts

Highlight a station only when its price drops below a threshold:

```yaml
type: conditional
conditions:
  - entity: sensor.my_local_tesco_unleaded_e10_price
    state_not: unavailable
  - entity: sensor.my_local_tesco_unleaded_e10_price
    below: "135"
card:
  type: tile
  entity: sensor.my_local_tesco_unleaded_e10_price
  name: Cheap unleaded nearby
  color: green
```

### Markdown card with top 3

Use the `cheapest_3` attribute to build a custom leaderboard:

```yaml
type: markdown
title: Cheapest Unleaded
content: >
  {% set top3 = state_attr('sensor.fuel_finder_cheapest_e10', 'cheapest_3') %}
  {% if top3 %}
  {% for s in top3 %}
  {{ loop.index }}. **{{ s.name }}** — {{ s.price }}p
     _{{ s.address }}_
  {% endfor %}
  {% else %}
  No data available
  {% endif %}
```

## Example automations

**Notify when diesel drops below a threshold:**

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.my_local_tesco_diesel_b7_price
        below: 135
    action:
      - action: notify.mobile_app
        data:
          title: "Diesel price drop"
          message: "{{ state_attr(trigger.entity_id, 'friendly_name') }} is now {{ trigger.to_state.state }}p"
```

**Notify when the cheapest diesel anywhere drops below a threshold:**

```yaml
automation:
  - trigger:
      - platform: numeric_state
        entity_id: sensor.fuel_finder_cheapest_b7
        below: 130
    action:
      - action: notify.mobile_app
        data:
          title: "Cheap diesel alert"
          message: >
            {{ state_attr('sensor.fuel_finder_cheapest_b7', 'station_name') }}
            has B7 at {{ states('sensor.fuel_finder_cheapest_b7') }}p
```
