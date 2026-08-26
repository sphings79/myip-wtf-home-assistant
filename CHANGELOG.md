# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-08-26

### Fixed

- Turning an IP version off in the options left its device and entities behind
  as unavailable leftovers. The device of a disabled IP version is now removed
  on reload, which takes its entities with it. A stale device can also be
  deleted from the device page.

## [1.0.0] - 2026-08-25

### Added

- Initial release.
- Public IPv4 and IPv6 sensors sourced from `ipv4.myip.wtf` and `ipv6.myip.wtf`.
- Eight sensors per IP version: IP address, hostname, internet provider,
  location, city, country, country code and "IP changed at".
- Two binary sensors per IP version: Tor exit node and reachability.
- A single globally shared request budget of one request per minute, covering
  every IP version and every refresh trigger, as required by the
  [myip.wtf automation policy](https://myip.wtf/automation).
- `myip_wtf_ip_changed` event for automations.
- UI config flow and options flow with validation of the polling interval
  against the number of enabled IP versions.
- Repair issues for upstream rate limiting and for an IP version that keeps
  failing.
- Diagnostics download with the identifying values redacted.
- English and German translations.

[1.0.1]: https://github.com/sphings79/myip-wtf-home-assistant/releases/tag/v1.0.1
[1.0.0]: https://github.com/sphings79/myip-wtf-home-assistant/releases/tag/v1.0.0
