function homeApp() {
            return {
                nick: '',
                room: '',
                error: '',
                socket: null,
                
                init() {
                    this.socket = io();

                    this.socket.on('room_created', (data) => {
                        // 
                        this.room = data.room;
                        this.joinRoom();
                    });
                    this.socket.on('duplicate_nick', (data) => {
                        alert(data.message)
                    })
                    this.socket.on('validation',(data) => {
                        if(data.status){
                            window.location.href = `/lobby?nick=${this.nick}&room=${this.room}`;
                        }
                        else{
                            alert(data.message)
                        }
                    })
                },

                createRoom() {
                    if (!this.nick.trim()) {
                        this.error = 'Please enter a nickname first.';
                        return;
                    }
                    this.socket.emit('create_room', { nick: this.nick });
                },

                joinRoom() {
                    if (!this.nick.trim() || !this.room.trim()) {
                        this.error = 'Nickname and room code are required to join.';
                        return;
                    }
                    this.socket.emit('room_validation', {room: this.room, nick: this.nick})
                    
                }
            }
        }
        document.addEventListener('alpine:init', () => {
            Alpine.data('homeApp', homeApp);
        });