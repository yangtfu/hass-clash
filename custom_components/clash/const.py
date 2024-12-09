"""Constants."""

DOMAIN = "clash"

SCAN_INTERVAL = 5
DELAY_TEST = [
    "Shadowsocks",
    "Trojan",
    "VMess",
    "Hysteria",
    "Hysteria2",
    "VLESS",
    "SSH",
    "TUIC",
    "Tor",
    "SSH",
]
NOW = ["Selector", "URLTest"]
CONF_DELAY = "delay"
CONF_URLTEST = "urltest"
CONF_TRAFFIC = "traffic"
CONF_SELECTOR = "selector"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 10
