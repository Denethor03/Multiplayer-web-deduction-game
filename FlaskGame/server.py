import shortuuid
import random
import time
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, send
from game_manager import GameManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'keykeykey'
socketio = SocketIO(app)

rooms_players = {}

# --- conf params ---
# to be moved somewhere with map data
REQUIRED_PLAYERS = 3
CAPTURE_TIME = 10
SABOTAGE_COOLDOWN = 120
BLESS_COOLDOWN = 180
STUN_DURATION = 45
ROOM_DELETION_TIME = 300
PLAYER_RECONECT_WINDOW = 3
PLAYER_GAME_RECONNECT_WINDOW = 200
JAM_CD = 300
# --- =========== ---

MAP_DATA = {
    "grand_temple": {
        "name": "Grand Temple", 
        "adj": ["mshr", "eshr"], 
        "type": "hq", 
        "default_owner": "Sentinels",
        "x": 50, "y": 20  
    },
    "dark_sanctum": {
        "name": "Hidden Sanctum", 
        "adj": ["mshr", "wshr"], 
        "type": "hq", 
        "default_owner": "Heretics",
        "x": 50, "y": 90 
    },
    "mshr": {
        "name": "Middle Shrine", 
        "adj": ["grand_temple", "dark_sanctum", "nshr", "sshr"], 
        "type": "shrine",
        "x": 50, "y": 50  
    },
    "nshr": {
        "name": "North Shrine", 
        "adj": ["mshr"], 
        "type": "shrine",
        "x": 20, "y": 30 
    },
    "sshr": {
        "name": "South Shrine", 
        "adj": ["mshr","eshr"], 
        "type": "shrine",
        "x": 90, "y": 65
    },
    "eshr": {
        "name": "East Shrine", 
        "adj": ["grand_temple",'sshr'], 
        "type": "shrine",
        "x": 80, "y": 30
    },
    "wshr": {
        "name": "West Shrine", 
        "adj": ["dark_sanctum"], 
        "type": "shrine",
        "x": 10, "y": 60
    },
    "rtow": {
        "name": "Radio Tower", 
        "adj": [], 
        "type": "jammer", 
        "x": 20, "y": 50 
    }
}

game_manager = GameManager(
    MAP_DATA, 
    capture_time=CAPTURE_TIME,
    sabotage_cd=SABOTAGE_COOLDOWN,
    bless_cd=BLESS_COOLDOWN,
    stun_duration=STUN_DURATION,
    jam_cd=JAM_CD
)

# --- ROUTES ---
@app.route('/')
def home(): return render_template('home.html')

@app.route('/lobby')
def lobby():
    username = request.args.get('nick')
    room = request.args.get('room')
    return render_template('lobby.html', username=username, room=room, required_players=REQUIRED_PLAYERS)

@app.route('/game')
def game():
    username = request.args.get('nick')
    room = request.args.get('room')
    team = request.args.get('team')  
    return render_template('game.html', username=username, room=room, team=team)


# this is confusing 

@socketio.on('create_room')
def on_create(data):
    room_code = shortuuid.uuid()[:6].upper()
    game_manager.initialize_room(room_code)
    rooms_players[room_code] = []
    socketio.emit('room_created', {'room': room_code}, to=request.sid)
    print(f'DEBUG: Room {room_code} created')

@socketio.on('join_lobby')
def handle_join_lobby(data):
    username = data['nick']
    room = data['room']
    
    if room not in rooms_players:
        rooms_players[room] = []
    existing_player = next((p for p in rooms_players[room] if p['nick'] == username), None) # in case of page refresh/not sure if needed atm
    
    if existing_player:
        existing_player['sid'] = request.sid
        existing_player['online'] = True
        join_room(room)
        print(f"DEBUG - page refresh from {username}")
    else:
        rooms_players[room].append({
            'sid': request.sid, 
            'nick': username, 
            'team': None, # only for frontend UI, matches data in game maneasger DO NOT TOUCH
            'online': True
        })
        join_room(room)
        send({'nick': 'System', 'text': f'{username} has joined the lobby.'}, to=room)
    player_count = len(rooms_players[room])
    
    socketio.emit('player_update', {
        'count': player_count, 
        'required': REQUIRED_PLAYERS
    }, to=room)

    # start game if contions met
    if player_count == REQUIRED_PLAYERS:
        players_in_room = rooms_players[room]
        random.shuffle(players_in_room)
        
        team_a_size = REQUIRED_PLAYERS // 2
        for i, player in enumerate(players_in_room):
            team = 'Sentinels' if i < team_a_size else 'Heretics'
            player['team'] = team # only for UI in front
        
            game_manager.register_player(room, player['nick'], team)
    
        socketio.emit('start_game', {'players': players_in_room}, to=room)

@socketio.on('join_game')
def on_join_game(data):
    room, nick = data['room'], data['nick']
    if room in rooms_players:
        player = next((p for p in rooms_players[room] if p['nick'] == nick), None)
        if player:
            player['sid'] = request.sid 
            player['online'] = True
            join_room(room)
            socketio.emit('state_update', game_manager.get_state(room), to=request.sid)
    else:
        socketio.emit('game_error',{'message': 'This game has ended due to inactivity.'}, to=request.sid)


@socketio.on('disconnect')
def handle_disconnect():
    for room_code, players in rooms_players.items():
        player = next((p for p in players if p['sid'] == request.sid), None)    
        if player:
            player['online'] = False
            nick = player['nick']  
            
            if player.get('team') is None:
                timeout = PLAYER_RECONECT_WINDOW
            else:
                timeout = PLAYER_GAME_RECONNECT_WINDOW
            
            threading.Timer(timeout, remove_inactive_player, [room_code, nick]).start()
            
            anyone_online = any(p.get('online', True) for p in players)
            
            if not anyone_online:
                print(f"Room {room_code} is empty. Starting {ROOM_DELETION_TIME} cleanup timer.")
                threading.Timer(ROOM_DELETION_TIME, cleanup_room, [room_code]).start()
            else:
                #moved to remove_inactive_player
                #send({'nick': 'System', 'text': f'{nick} disconnected.'}, to=room_code)
                print(f"DEBUG: {nick} disconected")
            break
@socketio.on('qr_scan')
def on_qr_scan(data):
    room, code, nick = data['room'], data['code'], data['nick']
    p_data = game_manager._get_player_data(room, nick)
    if p_data:
        p_data["at_loc"] = code
        p_data["last_scan"] = time.time()

   
    if code in MAP_DATA:
        actions = game_manager.get_available_actions(room, code, nick)
        
        stun_dict = p_data.get('stun_until', {})
        shrine_stun = stun_dict.get(code, 0) if isinstance(stun_dict, dict) else 0
        
        socketio.emit('available_actions', {
            'location_id': code,
            'location_name': MAP_DATA[code]['name'],
            'actions': actions,
            'stun_until': shrine_stun *1000,
            'voted_out' : p_data.get('voted_out',0)
        }, to=request.sid)


@socketio.on('game_action')
def on_action(data):
    room, loc_id, action, nick = data['room'], data['location_id'], data['action'], data['nick']
    
    if action.startswith("VOTE_FOR_"):
        target = action.replace("VOTE_FOR_", "") #pass nick for now (probably for ever)
        
        game_manager.start_council(room, target, nick)
        
        socketio.emit('open_council', {'target': target, 'by': nick}, to=room)
        
        socketio.send({'nick': 'System', 'text': f" COUNCIL CALLED: {nick} has accused {target}!"}, to=room)
        return 
    
    if action.startswith("CURSE_"):
        target_nick = action.replace("CURSE_", "")
        logs = game_manager._do_curse(room, target_nick, nick, loc_id)
        target_player = next((p for p in rooms_players[room] if p['nick'] == target_nick), None)
        if target_player:
            target_p_data = game_manager._get_player_data(room, target_nick)
            socketio.emit('force_stun', {
            'stun_until': target_p_data.get('stun_until', 0) * 1000
        }, to=target_player['sid'])
            send({'nick':'System','text':'Someone cursed you! You cannotc act for some time'},to=target_player['sid']) 
            print("DEBUG - Stun notification sent")
    else:
        player = next((p for p in rooms_players[room] if p['nick'] == nick), None)
        logs = game_manager.process_action(room, loc_id, action, player)
    
    if action == "JAM_SIGNALS":
        room_state = game_manager.get_state(room)
        if room_state and loc_id in room_state:
            room_state[loc_id]['last_jam_time'] = time.time()
        
        socketio.emit('jam_signals', {'duration': 60}, to=room)
        logs = ["Someone has scrambled all local map frequencies!"]
    
    for log in logs:
        send({'nick': 'System', 'text': log}, to=room)
    
    socketio.emit('state_update', game_manager.get_state(room), to=room)

    if action == "FINALIZE_RITUAL":
        winner = game_manager.check_winner(room)
        if winner:  
            socketio.emit('game_over', {
                'winner': winner,
                'message': f"The {winner} have asserted total dominance! The ritual is complete."
            }, to=room)
            print("DEBUG - game over status sent")

@socketio.on('submit_council_vote')
def handle_council_vote(data):
    room, nick, choice = data['room'], data['nick'], data['choice']
    
    result = game_manager.cast_vote(room, nick, choice)
    
    if result and result['complete']:
        if result['success']:
            target_data = game_manager._get_player_data(room, result['target'])
            target_data['voted_out'] = True
            
            socketio.send({'nick': 'System', 'text': f" {result['target']} was CAST OUT by the council!"}, to=room)
        else:
            socketio.send({'nick': 'System', 'text': f"The council has SPARED {result['target']}."}, to=room)
        
        
        socketio.emit('council_ended', to=room)
        socketio.emit('state_update', game_manager.get_state(room), to=room)


@socketio.on('room_validation')
def validate_room(data):
    room_id = data.get('room')
    nick = data.get('nick') 
    if room_id in rooms_players:
        # check if teams are assigned, if not game has not started very crappy solution but flag not needed
        game_started = any(p.get('team') is not None for p in rooms_players[room_id])
        if game_started:
            socketio.emit('validation', {
                'status': False, 
                'message': 'This game has already started. You cannot join.'
            }, to=request.sid)
            return
        
        nick_exists = any(p['nick'] == nick for p in rooms_players[room_id]) 
        if not nick_exists:
            socketio.emit('validation', {'status': True}, to=request.sid)
        else:
            socketio.emit('validation', {
                'status': False, 
                'message': 'Nickname already used in that room'
            }, to=request.sid)
    else:
        socketio.emit('validation', {'status': False, 'message': 'No room found'}, to=request.sid)
@socketio.on('message')
def handle_message(data):
    send(data, to=data['room'])

def cleanup_room(room_code):
    if room_code in rooms_players:
        anyone_back = any(p.get('online', False) for p in rooms_players[room_code])
        if not anyone_back:
            print(f"Wiping room {room_code} - no players returned.")
            del rooms_players[room_code]
            game_manager.clear_room_data(room_code)

def remove_inactive_player(room_code, nick):
    if room_code in rooms_players:
        players = rooms_players[room_code]
        player = next((p for p in players if p['nick'] == nick), None)
        
        if player and not player.get('online', False):
            players.remove(player)
            # for debug
            status = "lobby" if player.get('team') is None else "game"
            print(f"CLEANUP: Removed {nick} from {status} in room {room_code} due to inactivity.")   
            # ====  
            socketio.emit('player_update', {
                'count': len(players), 
                'required': REQUIRED_PLAYERS
            }, to=room_code, namespace='/')
            socketio.send({'nick': 'System', 'text': f'{nick} left the lobby (timeout).'}, to=room_code, namespace='/')
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)