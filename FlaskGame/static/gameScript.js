function gameApp(username, roomCode, teamName) {
    return {
        nick: username,
        room: roomCode,
        team: teamName,
        socket: null,
        messages: [],
        newMessage: '',
        gameState: {}, 
        currentLocation: { id: null, name: null },
        availableActions: [],
        isMapVisible: false,
        isScannerVisible: false,
        qrScanner: null,
        stunUntil: 0,
        debugLogs: [],
        councilActive: false,
        councilTarget: '',
        councilAccuser: '',
        isGhost : false,
        gameOverData: null,
        mapJammedUntil: 0,
        now: Date.now(),
        init() {
            this.socket = io();
            this.socket.emit('join_game', { nick: this.nick, room: this.room, team: this.team });
            setInterval(() => {
                this.now = Date.now();
            }, 250);
            this.socket.on('message', (data) => { this.updateChat(data); });
            
            this.socket.on('game_over', (data) => {
                this.gameOverData = data;
                this.stopScanner();
            });
            this.socket.on('jam_signals', (data) => { 
                this.mapJammedUntil = Date.now() + (data.duration * 1000);
                this.isMapVisible = false;
        });
            this.socket.on('available_actions', (data) => {
                this.currentLocation = { id: data.location_id, name: data.location_name };
                this.availableActions = data.actions;
                this.isScannerVisible = false; 
                this.stunUntil = data.stun_until;
                this.isGhost = data.voted_out;
                this.mapJammedUntil = data.map_jammed_until || 0;
                
            });

            this.socket.on('force_stun', (data) => {
                this.stunUntil = data.stun_until;
            });
            this.socket.on('state_update', (data) => {
                this.gameState = data;
                this.$nextTick(() => {
                    this.renderMapLines();
                });
            });

            this.socket.on('game_error', (data) => { alert(data.message); });
            this.socket.on('open_council', (data) => {
                this.councilTarget = data.target;
                this.councilAccuser = data.by;
                this.councilActive = true;
            });

        
            this.socket.on('council_ended', () => {
                this.councilActive = false;
            });
        },

        updateChat(data) {
            this.messages.push(data);
            this.$nextTick(() => {
                const msgBox = document.getElementById('messages');
                if(msgBox) msgBox.scrollTop = msgBox.scrollHeight;
            });
        },

        performAction(action) {
            this.socket.emit('game_action', {
                nick: this.nick,
                room: this.room,
                action: action,
                location_id: this.currentLocation.id 
            });

            this.availableActions = [];
            this.currentLocation = { id: null, name: null };
        },

        sendMessage() {
            if (this.newMessage.trim()) {
                this.socket.emit('message', { nick: this.nick, text: this.newMessage, room: this.room });
                this.newMessage = '';
            }
        },

        startScanner() {
            this.isScannerVisible = true;
            this.$nextTick(() => {
                this.qrScanner = new Html5Qrcode("qr-reader");
                const qrCodeSuccessCallback = (decodedText) => {
                    this.stopScanner();
                    this.socket.emit('qr_scan', { nick: this.nick, room: this.room, code: decodedText });
                };
                this.qrScanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, qrCodeSuccessCallback)
                    .catch(err => {
                        console.log("Scanner Error", err);
                        this.isScannerVisible = false;
                        alert("Camera permission denied or error.");
                    });
            });
        },

        stopScanner() {
            if (this.qrScanner) {
                this.qrScanner.stop().then(() => {
                    this.qrScanner.clear();
                }).catch(err => console.log(err)).finally(() => {
                    this.isScannerVisible = false;
                });
            } else {
                this.isScannerVisible = false;
            }
        },

        submitVote(choice) {
            this.socket.emit('submit_council_vote', {
                room: this.room,
                nick: this.nick,
                choice: choice
            });
            this.councilActive = false; 
        },

        renderMapLines() {
            const svg = this.$refs.mapSvg;
            if (!svg) return;

            while (svg.firstChild) {
                svg.removeChild(svg.firstChild);
            }

            const drawn = new Set();

            for (const [id, shrine] of Object.entries(this.gameState)) {
                for (const neighborId of shrine.adj) {

                    if (!this.gameState[neighborId]) continue;

                   
                    const key = [id, neighborId].sort().join("-");
                    if (drawn.has(key)) continue;
                    drawn.add(key);

                    const neighbor = this.gameState[neighborId];

                    const line = document.createElementNS(
                        "http://www.w3.org/2000/svg",
                        "line"
                    );

                    line.setAttribute("x1", shrine.x);
                    line.setAttribute("y1", shrine.y*0.75);

                    line.setAttribute("x2", neighbor.x);
                    line.setAttribute("y2", neighbor.y*0.75 );
                    line.setAttribute("class", "map-line");

                    svg.appendChild(line);
                }
            }
        }
    }
}