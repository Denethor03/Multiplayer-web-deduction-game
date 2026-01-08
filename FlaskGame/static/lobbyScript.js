function lobbyApp(username, roomCode, required) {
        return {
            nick: username,
            room: roomCode,
            playerCount: 0,
            requiredPlayers: required,
            socket: null,
            team: null,

            isChatVisible: true,
            messages: [],
            newMessage: '',
            
            init() {
                this.socket = io();
                this.socket.emit('check_game_status', { nick: this.nick, room: this.room });
                this.socket.emit('join_lobby', { nick: this.nick, room: this.room });
                this.socket.on('player_update', (data) => { this.playerCount = data.count; });
                this.socket.on('message', (data) => { this.updateChat(data); });   
                this.socket.on('game_already_started', (data) => {
                    window.location.href = `/game?nick=${this.nick}&room=${this.room}&team=${data.team}`;
                });
                this.socket.on('start_game', (data) => {

                    const me = data.players.find(p => p.nick === this.nick);
                    const myTeam = me ? me.team : 'Unknown';
                    window.location.href = `/game?nick=${this.nick}&room=${this.room}&team=${myTeam}`;
                });
            },
            sendMessage() {
                if (this.newMessage.trim()) {
                    this.socket.emit('message', { nick: this.nick, text: this.newMessage, room: this.room });
                    this.newMessage = '';
                }
            },
            updateChat(data) {
                this.messages.push(data);

                this.$nextTick(() => {
                    const msgBox = document.getElementById('messages');
                    msgBox.scrollTop = msgBox.scrollHeight;
                });
            },
    }
}