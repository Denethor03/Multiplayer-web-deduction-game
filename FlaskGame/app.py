import shortuuid
import random
from flask import Flask, render_template, request
from flask_socketio import SocketIO, join_room, leave_room, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'keykeykey'
socketio = SocketIO(app)


rooms = {} # this holds everything for "now"
REQUIRED_PLAYERS = 3  # change later to 6 or smth

# TO DO DELETE ROOM on disconect when room empty
LOCATIONS = {
    "nshr": {
        "name": "North Shrine",
        "actions": ["a1", "a2", "a3"]
    },
    "sshr": {
        "name": "South shrine",
        "actions": ["b1", "b2", "b3"]
    },
    "eshr": {
        "name": "East Shrine",
        "actions": ["c1", "c2", "c3"]
    },
    "wshr": {
        "name": "West Shrine",
        "actions": ["d1", "d2", "d3"]
    },
    "mshr": {
        "name": "Middle Shrine",
        "actions": ["e1","e2","e3"]
    }
    
}


# rotes
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




# H createRoom() -> emit("create room" with nick)
# S on "create room" add room -> emit("room created" with room code to sender)
# H on "room created" -> joinRoom() -> lobby(nick,room)
# H /lobby(nick,room,req_playys) -> init() -> emit("join lobby" with nick, room,)
# S on "join lobby" add players to room

@socketio.on('create_room')
def handle_create_room(data):
    room_code = shortuuid.uuid()[:6].upper()
    rooms[room_code] = {'players': []}
    socketio.emit('room_created', {'room': room_code}, to=request.sid)


@socketio.on('join_lobby')
def handle_join_lobby(data):
    username = data['nick']
    room = data['room']
    
    # should not happen now 
    #if room not in rooms:
    #
    #    socketio.emit('game_error', {'message': 'No such room exist'}, to=request.sid)
    #    return

    rooms[room]['players'].append({'sid': request.sid, 'nick': username})
    join_room(room) # build in function that adds player sid to room

    player_count = len(rooms[room]['players'])
    socketio.emit('player_update', {'count': player_count, 'required': REQUIRED_PLAYERS}, to=room)
    send({'nick': 'System', 'text': f'{username} has joined the lobby.'}, to=room)

    if player_count == REQUIRED_PLAYERS:
        # smth with teams
        players_in_room = rooms[room]['players']
        random.shuffle(players_in_room)
        team_a_size = REQUIRED_PLAYERS // 2

        for i, player in enumerate(players_in_room):
            player['team'] = 'Team A' if i < team_a_size else 'Team B'


        socketio.emit('start_game', {'players': players_in_room}, to=room)


@socketio.on('join_game')
def handle_join_game(data):
    join_room(data['room'])
    send({'nick': 'System', 'text': f'{data["nick"]} ({data["team"]}) has entered the game.'}, to=data['room'])


# qr scannign
@socketio.on('qr_scan')
def handle_qr_scan(data):
    username = data['nick']
    room = data['room']
    code_data = data['code']

    location = LOCATIONS.get(code_data)

    if location:
        # remove nickname perhaps
        send({'nick': 'System', 'text': f'Location "{location["name"]}" was visited by {username}.'}, to=room)


        socketio.emit('available_actions', {
            'location_id': code_data,
            'location_name': location['name'],
            'actions': location['actions']
        }, to=request.sid)  # this sends only to player who scannes
    else:

        socketio.emit('game_error', {'message': 'That QR code is not recognized.'}, to=request.sid)

@socketio.on('room_validation')
def validate_room(data):
    if data['room'] in rooms:
        socketio.emit('validation', {'status': True})
    else:
        socketio.emit('validation', {'status': False, 'message': 'No room found'})

@socketio.on('game_action')
def handle_game_action(data):
    username = data['nick']
    room = data['room']
    action = data['action']
    location_name = data['location_name']

    # to do actual logic
    response_text = f'{username} chose to "{action}" at {location_name}.'


    send({'nick': 'System', 'text': response_text}, to=room)


@socketio.on('message')
def handle_message(data):
    send(data, to=data['room'])



@socketio.on('disconnect')
def handle_disconnect():
    for room_code, room_data in rooms.items():
        player_to_remove = next((p for p in room_data.get('players', []) if p['sid'] == request.sid), None)
        if player_to_remove:
            room_data['players'].remove(player_to_remove)
            send({'nick': 'System', 'text': f'{player_to_remove["nick"]} has left.'}, to=room_code)
            socketio.emit('player_update', {'count': len(room_data['players']), 'required': REQUIRED_PLAYERS},
                          to=room_code)
            break

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)