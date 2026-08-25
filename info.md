# MyIP.wtf

Public **IPv4** and **IPv6** address sensors for Home Assistant, powered by the free
[myip.wtf](https://myip.wtf/) service. No API key, no account, no cloud vendor in between.

<img src="https://raw.githubusercontent.com/sphings79/myip-wtf-home-assistant/main/assets/banner.svg" alt="MyIP.wtf for Home Assistant — public IPv4 and IPv6 address sensors" width="100%">

## What you get

Per enabled IP version, one device with:

- **8 sensors** — IP address, hostname, internet provider, location, city, country, country code and
  "IP changed at"
- **2 binary sensors** — Tor exit node and reachability
- the **`myip_wtf_ip_changed`** event for automations (DynDNS updates, notifications, VPN checks)

## Rate limiting

The [myip.wtf automation policy](https://myip.wtf/automation) allows **one request per minute** and
non-commercial use only. This integration keeps **one shared request budget** for everything it does,
so IPv4 and IPv6 together never exceed that limit. The default interval of 15 minutes results in
8 requests per hour.

## Setup

After installing, restart Home Assistant and add the integration under
**Settings → Devices & services → Add integration → MyIP.wtf**. Pick the IP versions you want and the
polling interval — no YAML needed.

## Credits

The service itself is **not** part of this project. All data comes from
[myip.wtf / wtfismyip.com](https://myip.wtf/), run free of charge, without ads or trackers, by a third
party ([source code](https://codeberg.org/wtfismyip/wtfismyip),
[donate](https://myip.wtf/donate)). This is an unofficial, community built integration and is not
affiliated with or endorsed by them.

📖 Full documentation: [English](https://github.com/sphings79/myip-wtf-home-assistant#readme) ·
[Deutsch](https://github.com/sphings79/myip-wtf-home-assistant/blob/main/README.de.md)
