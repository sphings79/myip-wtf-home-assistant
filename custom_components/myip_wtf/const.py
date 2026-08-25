"""Constants for the MyIP.wtf integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "myip_wtf"
MANUFACTURER: Final = "myip.wtf"

#: GitHub repository of this integration (used for the User-Agent and links).
REPO: Final = "sphings79/myip-wtf-home-assistant"

# --- API -------------------------------------------------------------------

#: Endpoint that is reachable over IPv4 only (A record, no AAAA).
URL_IPV4: Final = "https://ipv4.myip.wtf/json"
#: Endpoint that is reachable over IPv6 only (AAAA record, no A).
URL_IPV6: Final = "https://ipv6.myip.wtf/json"

IPV4: Final = "ipv4"
IPV6: Final = "ipv6"

ENDPOINTS: Final[dict[str, str]] = {IPV4: URL_IPV4, IPV6: URL_IPV6}

#: Human readable labels used for device names.
VERSION_LABELS: Final[dict[str, str]] = {IPV4: "IPv4", IPV6: "IPv6"}

# --- Rate limiting ---------------------------------------------------------

#: The upstream automation policy (https://myip.wtf/automation) allows at most
#: one request per minute.  We apply that budget globally - across every IP
#: version and every config entry - instead of per coordinator, so the
#: integration can never exceed one outbound request per minute in total.
MIN_REQUEST_SPACING: Final = 60.0

#: Smallest polling interval (in minutes) that a single IP version may use.
MIN_INTERVAL_PER_VERSION: Final = 1

#: Default polling interval in minutes.  Public IP addresses rarely change,
#: and a relaxed default keeps us far below the upstream budget.
DEFAULT_SCAN_INTERVAL: Final = 15
MAX_SCAN_INTERVAL: Final = 1440

REQUEST_TIMEOUT: Final = timedelta(seconds=30)

# --- Configuration ---------------------------------------------------------

CONF_IPV4: Final = "ipv4"
CONF_IPV6: Final = "ipv6"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_TITLE: Final = "MyIP.wtf"

# --- Events / issues -------------------------------------------------------

EVENT_IP_CHANGED: Final = "myip_wtf_ip_changed"

ISSUE_RATE_LIMITED: Final = "rate_limited"
ISSUE_VERSION_UNAVAILABLE: Final = "version_unavailable_{version}"

#: Number of consecutive failures for a single IP version before a repair
#: issue is raised suggesting the user turns that version off.
FAILURE_THRESHOLD: Final = 3

# --- hass.data keys --------------------------------------------------------

DATA_LIMITER: Final = "rate_limiter"
DATA_CACHE: Final = "response_cache"
