from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect
import random

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your-very-secret-and-unique-key'
socketio = SocketIO(app)



players = {}  # {sid: 'nickname'}
messages = []  # [{'nick': 'System', 'text': 'Welcome!'}]



QR_CODE_ACTIONS = {
    "LOC_ENG_ROOM_01": {
        "location_name": "Engine Room",
        "action_description": "You can sabotage the engine! (Red Team only)",
        "allowed_team": "red_team"
    },
    "LOC_MED_BAY_02": {
        "location_name": "Med Bay",
        "action_description": "You can heal a teammate! (Blue Team only)",
        "allowed_team": "blue_team"
    },
    "LOC_BRIDGE_03": {
        "location_name": "The Bridge",
        "action_description": "You can view security logs.",
        "allowed_team": "all"
    }
}
game_state = {
    'status': 'waiting',
    'required_players': 2,
    'teams': {
        'red_team': [],
        'blue_team': []
    },
    'winner_team': None
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """The join page."""
    if request.method == 'POST':
        nick = request.form.get('nick')
        if nick and nick.strip():
            session['nick'] = nick.strip()
            return redirect(url_for('chat'))

    return render_template('index.html')


@app.route('/chat')
def chat():
    """The main chat room page."""
    if 'nick' not in session:
        return redirect(url_for('index.html'))


    if len(players) >= game_state['required_players'] or game_state['status'] != 'waiting':
        return render_template('error_page.html', message='Game is full or already in progress.')

    return render_template('chat.html', nick=session['nick'])



@socketio.on('connect')
def handle_connect():
    nick = session.get('nick')
    if not nick:
        return


    if len(players) >= game_state['required_players']:
        emit('server_error', {'message': 'Sorry, the game is full or already in progress.'})
        disconnect()
        return


    players[request.sid] = nick
    print(f"Client connected: {nick} ({request.sid})")


    emit('chat_history', {'messages': messages})
    emit('user_update', {'message': f'{nick} has joined ({len(players)}/{game_state["required_players"]})'},
         broadcast=True)
    emit('player_list_update', {'players': list(players.values())}, broadcast=True)


    emit('game_state_update', game_state)


    check_for_game_start()


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in players:
        nick = players.pop(request.sid)
        print(f"Client disconnected: {nick} ({request.sid})")

        emit('user_update', {'message': f'{nick} has left the game.'}, broadcast=True)
        emit('player_list_update', {'players': list(players.values())}, broadcast=True)


        if game_state['status'] == 'in_progress':
            emit('user_update', {'message': 'A player disconnected. The game has been reset.'}, broadcast=True)
            reset_game()
@socketio.on('new_message')
def handle_new_message(data):

    nick = session.get('nick')
    if not nick:
        return

    message = {
        'nick': nick,
        'text': data['text']
    }
    messages.append(message)

    if len(messages) > 10:
        messages.pop(0)


    emit('chat_update', message, broadcast=True)




def check_for_game_start():

    if game_state['status'] == 'waiting' and len(players) == game_state['required_players']:
        start_game()




def start_game():

    print("--- Enough players have joined! Starting the game. ---")
    game_state['status'] = 'in_progress'

    player_nicks = list(players.values())
    random.shuffle(player_nicks)

    midpoint = len(player_nicks) // 2
    game_state['teams']['red_team'] = player_nicks[:midpoint]
    game_state['teams']['blue_team'] = player_nicks[midpoint:]

    print(f"Teams assigned: {game_state['teams']}")


    socketio.emit('user_update', {'message': 'The game is starting! Teams have been assigned.'}, namespace='/')
    socketio.emit('game_state_update', game_state, namespace='/')



def reset_game():

    global game_state, messages
    game_state = {
        'status': 'waiting',
        'required_players': 2,
        'teams': {'red_team': [], 'blue_team': []},
        'winner_team': None
    }
    messages = []
    print("--- Game has been reset. ---")

    socketio.emit('game_state_update', game_state, broadcast=True)
    socketio.emit('user_update', {'message': 'A new game is available! Waiting for players...'}, broadcast=True)




@socketio.on('qr_scan_action')
def handle_qr_scan(data):
    nick = session.get('nick')
    qr_text = data.get('qr_data')


    if not nick or not qr_text or game_state['status'] != 'in_progress':
        return

    print(f"Player '{nick}' scanned QR code: '{qr_text}'")


    if qr_text in QR_CODE_ACTIONS:
        action = QR_CODE_ACTIONS[qr_text]


        player_team = None
        if nick in game_state['teams']['red_team']:
            player_team = 'red_team'
        elif nick in game_state['teams']['blue_team']:
            player_team = 'blue_team'

        if action['allowed_team'] == 'all' or action['allowed_team'] == player_team:



            emit('user_update', {
                'message': f"{nick} scanned '{action['location_name']}' and performed an action!"
            }, broadcast=True)


            emit('action_feedback', {
                'success': True,
                'message': f"Success! You used the action: {action['action_description']}"
            })


        else:

            emit('action_feedback', {
                'success': False,
                'message': f"Your team cannot use the action at '{action['location_name']}'."
            })
    else:

        emit('action_feedback', {
            'success': False,
            'message': "This QR code is not valid for this game."
        })



if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)