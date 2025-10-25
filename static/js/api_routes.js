API_PATHS = {
    "measurement": {
        "start": "/gasera/api/measurement/start",
        "abort": "/gasera/api/measurement/abort",
        "state": "/gasera/api/measurement/status",
        "events": "/gasera/api/measurement/events"
    },
    "connection": {
        "status": "/gasera/api/connection_status"
    },
    "data": {
        "dummy": "/gasera/api/data/dummy",
        "live": "/gasera/api/data/live"
    },
    "settings": {
        "read": "/system/prefs",
        "update": "/system/prefs"
    },
    "dispatch": {
        "instruction": "/gasera/api/dispatch/instruction"
    },
    "commandMap": {
        "script": "/gasera/command_map.js"
    },
    "gpio": {
        "control": "/gpio/api/gpio",
        "motorStatus": "/gpio/motor/status",
        "motorJog": "/gpio/motor/jog"
    },
    "system": {
        "info": "/system/api/info",
        "prefsGet": "/system/prefs",
        "prefsPost": "/system/prefs"
    }
}
