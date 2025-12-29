import shortuuid
import random
import time
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, send
from game_manager import GameManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'keykeykey'
socketio = SocketIO(app)


rooms_players = {} 
REQUIRED_PLAYERS = 2


CAPTURE_TIME = 10
SABOTAGE_COOLDOWN = 120
BLESS_COOLDOWN = 180
STUN_DURATION = 45


MAP_DATA = {
    "grand_temple": {
        "name": "Grand Temple", 
        "adj": ["mshr", "eshr"], 
        "type": "hq", 
        "default_owner": "Sentinels",
        "x": 50, "y": 10  # top center
    },
    "dark_sanctum": {
        "name": "Hidden Sanctum", 
        "adj": ["mshr", "wshr"], 
        "type": "hq", 
        "default_owner": "Heretics",
        "x": 50, "y": 90  # bottom center
    },
    "mshr": {
        "name": "Middle Shrine", 
        "adj": ["grand_temple", "dark_sanctum", "nshr", "sshr"], 
        "type": "shrine",
        "x": 50, "y": 50  # middle center
    },
    "nshr": {
        "name": "North Shrine", 
        "adj": ["mshr"], 
        "type": "shrine",
        "x": 20, "y": 30 # etc
    },
    "sshr": {
        "name": "South Shrine", 
        "adj": ["mshr","eshr"], 
        "type": "shrine",
        "x": 80, "y": 70
    },
    "eshr": {
        "name": "East Shrine", 
        "adj": ["grand_temple"], 
        "type": "shrine",
        "x": 80, "y": 30
    },
    "wshr": {
        "name": "West Shrine", 
        "adj": ["dark_sanctum"], 
        "type": "shrine",
        "x": 20, "y": 70
    },
}

game_manager = GameManager(
    MAP_DATA, 
    capture_time=CAPTURE_TIME,
    sabotage_cd=SABOTAGE_COOLDOWN,
    bless_cd=BLESS_COOLDOWN,
    stun_duration=STUN_DURATION
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



@socketio.on('join_lobby')
def handle_join_lobby(data):
    username = data['nick']
    room = data['room']
    
    if room not in rooms_players:
        rooms_players[room] = []
         
    rooms_players[room].append({
        'sid': request.sid, 
        'nick': username, 
        'team': None # only for frontend UI, matches data in game maneasger DO NOT TOUCH
    })
    
    join_room(room)
    
    player_count = len(rooms_players[room])
    
    socketio.emit('player_update', {
        'count': player_count, 
        'required': REQUIRED_PLAYERS
    }, to=room)
    
    send({'nick': 'System', 'text': f'{username} has joined the lobby.'}, to=room)

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
    room = data['room']
    nick = data['nick']
    join_room(room)
    #join_room(request.sid) not needed apparently? 
    player = next(
        (p for p in rooms_players[room] if p['nick'] == nick),
        None
    )
    if player:
        player['sid'] = request.sid

    socketio.emit(
        'state_update',
        game_manager.get_state(room),
        to=request.sid
    )


@socketio.on('disconnect')
def handle_disconnect():
    for room_code, players in rooms_players.items():
        player = next((p for p in players if p['sid'] == request.sid), None)
        if player:
           
            if player.get('team') is None:
                players.remove(player)
                socketio.emit('player_update', {
                    'count': len(players), 
                    'required': REQUIRED_PLAYERS
                }, to=room_code)
                send({'nick': 'System', 'text': f'{player["nick"]} left the lobby.'}, to=room_code)
            else:
                print(f"Player {player['nick']} connection toggled (page reload).") #for debug
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
        socketio.emit('available_actions', {
            'location_id': code,
            'location_name': MAP_DATA[code]['name'],
            'actions': actions,
            'stun_until': p_data.get('stun_until',0) *1000
        }, to=request.sid)


@socketio.on('game_action')
def on_action(data):
    room, loc_id, action, nick = data['room'], data['location_id'], data['action'], data['nick']
    
    if action.startswith("CURSE_"):
        target_nick = action.replace("CURSE_", "")
        logs = game_manager._do_curse(room, target_nick, nick)
        target_player = next((p for p in rooms_players[room] if p['nick'] == target_nick), None)
        if target_player:
            target_p_data = game_manager._get_player_data(room, target_nick)
            socketio.emit('force_stun', {
                'stun_until': target_p_data.get('stun_until', 0) * 1000
            }, to=target_player['sid'])
            send({'nick':'DEBUG','text':'stun messagr recieved'},to=target_player['sid']) #debug
            print("DEBUG - Stun notification sent")
    else:
        player = next((p for p in rooms_players[room] if p['nick'] == nick), None)
        logs = game_manager.process_action(room, loc_id, action, player)
    
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


@socketio.on('room_validation')
def validate_room(data):
    if data['room'] in rooms_players:
        socketio.emit('validation', {'status': True}, to=request.sid)
    else:
        socketio.emit('validation', {'status': False, 'message': 'No room found'}, to=request.sid)

@socketio.on('message')
def handle_message(data):
    send(data, to=data['room'])

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)