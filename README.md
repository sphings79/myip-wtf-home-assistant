<div align="center">

<img src="assets/banner.svg" alt="MyIP.wtf for Home Assistant — public IPv4 and IPv6 address sensors, rate limit friendly, no API key required" width="100%">

# MyIP.wtf — Public IP Address Sensors for Home Assistant

**Monitor your public IPv4 and IPv6 address, ISP, country and Tor exit status in Home Assistant.**
A lightweight HACS custom integration built on the free [myip.wtf](https://myip.wtf/) service — no API key, no account, no cloud vendor in between.

[![HACS: Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/sphings79/myip-wtf-home-assistant?style=for-the-badge&color=41BDF5)](https://github.com/sphings79/myip-wtf-home-assistant/releases)
[![Home Assistant 2024.12+](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-41BDF5.svg?style=for-the-badge)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-3ddc97.svg?style=for-the-badge)](LICENSE)

**English** · [Deutsch](README.de.md)

</div>

---

## Table of contents

- [What this integration does](#what-this-integration-does)
- [Entities you get](#entities-you-get)
- [How it works](#how-it-works)
- [One request per minute — for the whole integration](#one-request-per-minute--for-the-whole-integration)
- [Installation](#installation)
- [Configuration](#configuration)
- [Choosing a polling interval](#choosing-a-polling-interval)
- [Automation examples](#automation-examples)
- [Dashboard example](#dashboard-example)
- [The `myip_wtf_ip_changed` event](#the-myip_wtf_ip_changed-event)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Credits](#credits)
- [Disclaimer](#disclaimer)
- [Contributing](#contributing)
- [License](#license)

---

## What this integration does

Home Assistant knows a lot about your home network, but not much about the address the rest of the
internet sees. This integration closes that gap: it asks [myip.wtf](https://myip.wtf/) what your
**public IP address** (also called external IP, WAN IP or internet IP) currently is and turns the
answer into regular Home Assistant entities.

That gives you, per IP version:

- the **public IPv4 address** and the **public IPv6 address** of your internet connection,
- the **reverse DNS hostname** your provider assigns to it,
- the **internet service provider (ISP)** behind the address,
- a coarse **geolocation**: city, country and country code,
- whether the address is a known **Tor exit node**,
- a timestamp of the **last address change**, plus an event you can trigger automations on.

Typical uses: a **dynamic DNS** update when your provider hands you a new address, a **VPN kill switch
check** ("does my WAN address still look like the VPN provider?"), a notification after a forced
reconnect, or simply a dashboard card that tells you what to type into a firewall rule.

**No API key. No registration. No polling loop to write yourself.**

## Entities you get

<img src="assets/entities.svg" alt="Entity overview: one Home Assistant device per IP version, each with eight sensors — IP address, hostname, internet provider, location, city, country, country code and IP changed at — plus two binary sensors for Tor exit node and reachability" width="100%">

Each enabled IP version becomes its own Home Assistant **device**, so `IPv4` and `IPv6` values never
get mixed up in a dashboard or automation.

| Entity | Type | Example state | Notes |
| --- | --- | --- | --- |
| `sensor.myip_wtf_ipv4_ip_address` | Sensor | `203.0.113.7` | Your public IPv4 address |
| `sensor.myip_wtf_ipv4_hostname` | Sensor | `host.example.net` | Reverse DNS name |
| `sensor.myip_wtf_ipv4_internet_provider` | Sensor | `Example Telecom` | ISP / network owner |
| `sensor.myip_wtf_ipv4_location` | Sensor | `Lemgo, NW, Germany` | Combined location string |
| `sensor.myip_wtf_ipv4_city` | Sensor | `Lemgo` | Coarse city estimate |
| `sensor.myip_wtf_ipv4_country` | Sensor | `Germany` | Country name |
| `sensor.myip_wtf_ipv4_country_code` | Sensor | `DE` | ISO 3166-1 alpha-2, diagnostic |
| `sensor.myip_wtf_ipv4_ip_changed_at` | Sensor | `2026-08-25T06:12:00+00:00` | Timestamp, survives restarts |
| `binary_sensor.myip_wtf_ipv4_tor_exit_node` | Binary sensor | `off` | `on` if the address is a known Tor exit |
| `binary_sensor.myip_wtf_ipv4_reachable` | Binary sensor | `on` | Did the last poll for this IP version work? |

The same ten entities exist with `ipv6` in place of `ipv4` when IPv6 is enabled. Entity IDs depend on
the device name you choose in Home Assistant; the ones above are the defaults.

## How it works

<img src="assets/architecture.svg" alt="Architecture diagram: the update coordinator wakes up on the configured interval and sends every request through one shared rate limiter to ipv4.myip.wtf and ipv6.myip.wtf; answers become sensors, binary sensors and an IP change event" width="100%">

A single update coordinator drives everything:

1. On every polling cycle it asks for each enabled IP version, **one request at a time**.
2. `ipv4.myip.wtf` only has an `A` record and `ipv6.myip.wtf` only has an `AAAA` record, so the
   operating system automatically uses the right protocol — no socket tricks needed.
3. The JSON answer is normalised (empty and placeholder values become `unknown`) and pushed into the
   entities.
4. If the address differs from the previous one, the integration fires
   [`myip_wtf_ip_changed`](#the-myip_wtf_ip_changed-event).

## One request per minute — for the whole integration

The myip.wtf [automation policy](https://myip.wtf/automation) asks automated clients to stay at
**one request per minute per IP address**, and limits use to non-commercial applications. This
integration takes that seriously and enforces it in one place:

<img src="assets/rate-limit.svg" alt="Timeline comparison: a per-coordinator budget would fire the IPv4 and IPv6 request in the same second, while the shared global budget of this integration keeps at least 60 seconds between any two requests" width="100%">

- There is **one shared request budget** for the whole integration, not one per IP version, not one
  per entity and not one per refresh trigger.
- Every request — scheduled poll, `homeassistant.update_entity`, config flow probe — queues behind
  that budget and waits until at least **60 seconds** have passed since the previous one.
- An HTTP `429` answer pushes the next allowed request even further out and raises a repair issue.
- The config flow refuses an interval that would exceed the budget: with both IP versions enabled the
  minimum is two minutes, because a full cycle costs two requests.

With the default interval of 15 minutes and both IP versions enabled, the integration sends
**8 requests per hour** — comfortably below the 60 the policy allows.

## Installation

<img src="assets/install.svg" alt="Installation in four steps: add the custom repository to HACS, install MyIP.wtf, restart Home Assistant, then add the integration and pick your IP versions" width="100%">

### HACS (recommended)

1. Open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add `https://github.com/sphings79/myip-wtf-home-assistant` with category **Integration**.
3. Search for **MyIP.wtf** and press **Download**.
4. **Restart Home Assistant.**
5. Go to **Settings → Devices & services → Add integration** and pick **MyIP.wtf**.

### Manual installation

1. Download the latest release.
2. Copy the folder `custom_components/myip_wtf` into your Home Assistant `config/custom_components/`
   directory, so you end up with `config/custom_components/myip_wtf/manifest.json`.
3. Restart Home Assistant and add the integration from the UI.

Requirements: Home Assistant **2024.12** or newer, and outbound HTTPS access to `myip.wtf`.
There are no Python dependencies beyond what Home Assistant already ships.

## Configuration

Everything is configured in the UI — there is no YAML configuration. You can change all of it later
under **Settings → Devices & services → MyIP.wtf → Configure**.

| Option | Default | Description |
| --- | --- | --- |
| Track public IPv4 address | on | Polls `ipv4.myip.wtf`. |
| Track public IPv6 address | on | Polls `ipv6.myip.wtf`. Turn it off if your connection has no IPv6. |
| Polling interval | 15 minutes | Time between two full polling cycles. Minimum: one minute per enabled IP version. |

Turning an IP version off removes its device and all of its entities on the next reload —
they are not left behind in an unavailable state. If a device ever does survive, the
**Delete** button on its device page removes it.

At setup time the integration probes exactly **one** IP version to check that the service answers.
A second probe would have to wait for the shared request slot and stall the dialog, so the other
version is verified on the first regular poll instead.

## Choosing a polling interval

| Interval | IP versions | Requests per hour | Good for |
| --- | --- | --- | --- |
| 2 min | IPv4 + IPv6 | 60 | The absolute maximum the policy allows — only if you really need it |
| 5 min | IPv4 + IPv6 | 24 | Connections with frequent forced reconnects |
| **15 min** | IPv4 + IPv6 | **8** | **Default — fine for almost everyone** |
| 30 min | IPv4 only | 2 | Static or rarely changing addresses |
| 60 min | IPv4 only | 1 | Business lines with a fixed IP |

Public IP addresses change rarely — usually on a router reboot or a nightly forced reconnect. Polling
faster mostly burns someone else's bandwidth. If you need instant reaction, trigger a refresh from an
automation with `homeassistant.update_entity` when your router reports a reconnect; that call still
respects the shared budget.

## Automation examples

<img src="assets/automation.svg" alt="Automation flow: when the public IP address changes the integration fires the myip_wtf_ip_changed event, which can trigger a push notification, a dynamic DNS update or a VPN check" width="100%">

**Notify me when the public IP address changes**

```yaml
automation:
  - alias: Public IP changed
    triggers:
      - trigger: event
        event_type: myip_wtf_ip_changed
    actions:
      - action: notify.mobile_app_phone
        data:
          title: "New public {{ trigger.event.data.ip_version | upper }} address"
          message: >-
            {{ trigger.event.data.old_ip }} → {{ trigger.event.data.new_ip }}
            ({{ trigger.event.data.isp }})
```

**Update a dynamic DNS record, IPv4 only**

```yaml
automation:
  - alias: Update DynDNS on IPv4 change
    triggers:
      - trigger: event
        event_type: myip_wtf_ip_changed
        event_data:
          ip_version: ipv4
    actions:
      - action: rest_command.update_dyndns
        data:
          ip: "{{ trigger.event.data.new_ip }}"
```

**Warn me when the VPN drops and my real ISP address shows up**

```yaml
automation:
  - alias: VPN leak warning
    triggers:
      - trigger: state
        entity_id: sensor.myip_wtf_ipv4_internet_provider
    conditions:
      - condition: template
        value_template: "{{ trigger.to_state.state == 'Example Telecom' }}"
    actions:
      - action: persistent_notification.create
        data:
          title: VPN appears to be down
          message: >-
            Home Assistant is talking to the internet as
            {{ states('sensor.myip_wtf_ipv4_ip_address') }}.
```

**Alert on an unexpected Tor exit node**

```yaml
automation:
  - alias: Traffic leaving through Tor
    triggers:
      - trigger: state
        entity_id: binary_sensor.myip_wtf_ipv4_tor_exit_node
        to: "on"
    actions:
      - action: notify.persistent_notification
        data:
          message: The public IPv4 address is a known Tor exit node.
```

## Dashboard example

<img src="assets/dashboard.svg" alt="Example Home Assistant dashboard with a MyIP.wtf entities card, a connection health card and a logbook of public IP address changes" width="100%">

```yaml
type: entities
title: Internet connection
entities:
  - entity: sensor.myip_wtf_ipv4_ip_address
    name: IPv4
  - entity: sensor.myip_wtf_ipv6_ip_address
    name: IPv6
  - entity: sensor.myip_wtf_ipv4_internet_provider
    name: Provider
  - entity: sensor.myip_wtf_ipv4_hostname
    name: Hostname
  - entity: sensor.myip_wtf_ipv4_country
    name: Country
  - entity: sensor.myip_wtf_ipv4_city
    name: City
  - entity: sensor.myip_wtf_ipv4_ip_changed_at
    name: Changed
  - entity: binary_sensor.myip_wtf_ipv4_tor_exit_node
    name: Tor exit node
```

## The `myip_wtf_ip_changed` event

Fired once per IP version whenever the address differs from the previous poll. It is not fired on the
very first successful poll after a restart, so a Home Assistant restart alone never triggers your
automations.

| Field | Example | Description |
| --- | --- | --- |
| `ip_version` | `ipv4` | Which version changed — `ipv4` or `ipv6` |
| `old_ip` | `198.51.100.4` | The previously seen address |
| `new_ip` | `203.0.113.7` | The new address |
| `hostname` | `host.example.net` | Reverse DNS of the new address |
| `isp` | `Example Telecom` | Provider of the new address |
| `city` / `country` / `country_code` | `Lemgo` / `Germany` / `DE` | Geolocation of the new address |
| `tor_exit` | `false` | Is the new address a known Tor exit node? |
| `entry_id` | `01J…` | Config entry that fired the event |

## Troubleshooting

**IPv6 entities stay unavailable.** Most connections still have no working IPv6. After three failed
cycles the integration raises a repair issue; turn IPv6 off in the options to stop the failing
requests.

**"myip.wtf is rate limiting this host".** The service answered with HTTP 429. Increase the polling
interval and check whether something else on the same connection — another Home Assistant instance, a
script, a router add-on — is querying myip.wtf as well. The limit counts per public IP address, not
per application.

**The address is wrong or the city is off.** The address is whatever the service sees, which is the
address your traffic actually leaves through: with a VPN or proxy active that is the VPN's address,
not your line's. Geolocation comes from an IP database and is a rough estimate, not GPS.

**Enable debug logging:**

```yaml
logger:
  default: warning
  logs:
    custom_components.myip_wtf: debug
```

A **Download diagnostics** button is available on the integration page. The IP address, hostname and
city are redacted before the file is written, so it is safe to attach to an issue.

## FAQ

**Does this integration need an API key or an account?**
No. myip.wtf is a free service without registration. The integration sends a plain HTTPS `GET` and
identifies itself with a descriptive `User-Agent`.

**Can I use it commercially?**
No. The [myip.wtf automation policy](https://myip.wtf/automation) explicitly prohibits commercial
use. Home automation at home is fine; a business monitoring system is not.

**How is this different from Home Assistant's built-in IP integrations?**
The core `dnsip` integration resolves a DNS name to an address, and `ipify`-style services only give
you the bare address. myip.wtf adds hostname, ISP, geolocation and Tor exit detection in the same
answer — and this integration adds the change event, per-version devices and the shared rate limit.

**Does it work behind CGNAT or a VPN?**
Yes, and that is the point: it reports the address the internet actually sees, which behind CGNAT is
your provider's shared address and behind a VPN is the VPN exit address.

**Why does a refresh sometimes take a minute?**
Because the second IP version has to wait for the shared one-request-per-minute slot. That is
intentional.

**Does it slow down Home Assistant startup?**
No. The first refresh after a restart fetches a single IP version, and a one-off catch-up refresh
about a minute later fills in the rest.

**Can I run two instances?**
No — the integration is limited to a single config entry on purpose, so the request budget cannot be
circumvented by accident.

**Is my IP address sent anywhere else?**
No. The only outbound connection is to myip.wtf, which necessarily sees your address because that is
what it reports back. See their [privacy policy](https://myip.wtf/privacy).

## Credits

**This integration is not the service.** All the data comes from a free service run by someone else,
and all credit for it belongs to them:

- **[myip.wtf](https://myip.wtf/) / [wtfismyip.com](https://wtfismyip.com/)** — the public IP service
  this integration reads from. No ads, no trackers, no CloudFlare, IPv6 support and Tor exit
  detection, provided free of charge to the community.
- Their source code is public at
  **[codeberg.org/wtfismyip/wtfismyip](https://codeberg.org/wtfismyip/wtfismyip)**.
- Their [automation policy](https://myip.wtf/automation) and
  [privacy policy](https://myip.wtf/privacy) are what shaped the design of this integration.

If you find the service useful, **[donate to them](https://myip.wtf/donate)** — they run it without
advertising revenue.

Thanks also to the Home Assistant and HACS communities for the integration patterns this project
follows.

## Disclaimer

This is an **unofficial, community built** integration. It is not affiliated with, endorsed by or
operated by the people behind myip.wtf / wtfismyip.com, nor by the Home Assistant project. The
upstream service is provided with no guarantees as to availability or reliability, and this
integration inherits that. Use it at your own risk, and stay within the upstream automation policy.

The upstream API uses deliberately profane field names. The integration maps them to neutral entity
names, so nothing of that surfaces in your Home Assistant instance.

## Contributing

Issues and pull requests are welcome. Please keep two things in mind:

- Any change must stay within **one request per minute in total**.
- Run the checks before opening a PR:

```bash
pip install homeassistant pytest pytest-asyncio ruff && ruff check . && pytest
```

Problems with the myip.wtf service itself (downtime, wrong geolocation) belong
[upstream](https://codeberg.org/wtfismyip/wtfismyip), not here.

---

## ☕ Support

These tools are built and maintained in my free time, and they stay free, open and cloud-free.
If one of them saved you an afternoon, you can [buy me a coffee](https://buymeacoffee.com/sphings).

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-sphings-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/sphings)

## License

[MIT](LICENSE) © Dennis (@sphings79)

---

<div align="center">

<sub>

**Keywords:** Home Assistant public IP sensor · external IP address Home Assistant · WAN IP sensor ·
HACS custom integration · IPv4 and IPv6 monitoring · ISP sensor · dynamic DNS trigger · Tor exit node
detection · myip.wtf · wtfismyip

</sub>

</div>
