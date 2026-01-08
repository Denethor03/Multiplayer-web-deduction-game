# Game Configuration File

# === GAME RULES ===
REQUIRED_PLAYERS = 3
CAPTURE_TIME = 10  # seconds to capture a shrine
SABOTAGE_COOLDOWN = 120  # cooldown for sabotage action
BLESS_COOLDOWN = 180  # cooldown for bless action
STUN_DURATION = 45  # duration of stun effect
JAM_CD = 300  # cooldown for jamming signals

# === SERVER SETTINGS ===
ROOM_DELETION_TIME = 300  # time before empty room is deleted
PLAYER_RECONECT_WINDOW = 3  # lobby reconnection timeout (seconds)
PLAYER_GAME_RECONNECT_WINDOW = 200  # in-game reconnection timeout (seconds)

# === MAP DATA ===
MAP_DATA = {
    "grand_temple": {
        "name": "Grand Temple", 
        "adj": ["mshr", "eshr"], 
        "type": "hq", 
        "default_owner": "Sentinels",
        "x": 50, 
        "y": 20  
    },
    "dark_sanctum": {
        "name": "Hidden Sanctum", 
        "adj": ["mshr", "wshr"], 
        "type": "hq", 
        "default_owner": "Heretics",
        "x": 50, 
        "y": 90 
    },
    "mshr": {
        "name": "Middle Shrine", 
        "adj": ["grand_temple", "dark_sanctum", "nshr", "sshr"], 
        "type": "shrine",
        "x": 50, 
        "y": 50  
    },
    "nshr": {
        "name": "North Shrine", 
        "adj": ["mshr"], 
        "type": "shrine",
        "x": 20, 
        "y": 30 
    },
    "sshr": {
        "name": "South Shrine", 
        "adj": ["mshr", "eshr"], 
        "type": "shrine",
        "x": 90, 
        "y": 65
    },
    "eshr": {
        "name": "East Shrine", 
        "adj": ["grand_temple", "sshr"], 
        "type": "shrine",
        "x": 80, 
        "y": 30
    },
    "wshr": {
        "name": "West Shrine", 
        "adj": ["dark_sanctum"], 
        "type": "shrine",
        "x": 10, 
        "y": 60
    },
    "rtow": {
        "name": "Radio Tower", 
        "adj": [], 
        "type": "jammer", 
        "x": 20, 
        "y": 50 
    }
}