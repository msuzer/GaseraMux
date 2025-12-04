API_PATHS = {
    "measurement": {
        "start": "/gasera/api/measurement/start",
        "abort": "/gasera/api/measurement/abort",
        "events": "/gasera/api/measurement/events"
    },
    "logs": {
        "list": "/gasera/api/logs",
        "download": "/gasera/api/logs/",
        "delete": "/gasera/api/logs/delete/",
        "storage": "/gasera/api/logs/storage"
    },
    "settings": {
        "read": "/system/prefs",
        "update": "/system/prefs",
        "buzzer": "/system/buzzer"
    },
    "version": {
        "local": "/system/version/local",
        "github": "/system/version/github",
        "checkout": "/system/version/checkout",
        "rollback": "/system/version/rollback"
    },
    "gasera": {
        "gas_colors": "/gasera/api/gas_colors"
    }
}
