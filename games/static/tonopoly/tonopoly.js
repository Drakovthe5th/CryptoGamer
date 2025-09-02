class TONopolyGame {
    constructor() {
        this.telegramApp = window.Telegram.WebApp;
        this.telegramApp.expand();
        this.telegramApp.enableClosingConfirmation();
        
        this.gameState = null;
        this.playerColor = null;
        this.socket = null;
        this.gameId = this.getGameIdFromUrl() || this.generateGameId();
        this.assetsLoaded = 0;
        this.totalAssets = 0;
        this.soundEnabled = true;
        this.musicEnabled = false;
        
        this.init();
    }
    
    async init() {
        // Show loading screen
        this.showScreen('loading-screen');
        
        // Preload assets
        await this.preloadAssets();
        
        // Initialize UI
        this.renderLobby();
        this.setupEventListeners();
        
        // Update URL with game ID if not present
        if (!this.getGameIdFromUrl()) {
            this.updateUrlWithGameId();
        }
        
        // Connect to WebSocket
        await this.connectWebSocket();
        
        // Load user data
        await this.loadUserData();
        
        // Join the game
        await this.joinGame();
        
        // Hide loading screen
        this.hideLoadingScreen();
    }
    
    async preloadAssets() {
        const assets = [
            // Board assets
            'assets/board/board.png',
            'assets/board/board-overlay.png',
            'assets/board/home-areas.png',
            'assets/board/finish-path.png',
            
            // Piece assets
            'assets/pieces/piece-bitcoin.png',
            'assets/pieces/piece-ethereum.png',
            'assets/pieces/piece-ton.png',
            'assets/pieces/piece-stablecoin.png',
            'assets/pieces/piece-shadow.png',
            
            // Dice assets
            'assets/dice/dice-1.png',
            'assets/dice/dice-2.png',
            'assets/dice/dice-3.png',
            'assets/dice/dice-4.png',
            'assets/dice/dice-5.png',
            'assets/dice/dice-6.png',
            'assets/dice/dice-rolling.gif',
            
            // UI assets
            'assets/ui/button-roll.png',
            'assets/ui/button-stake.png',
            'assets/ui/button-bet.png',
            'assets/ui/panel-background.png',
            'assets/ui/icon-ton.png',
            'assets/ui/icon-stars.png',
            'assets/ui/icon-gamecoins.png',
            'assets/ui/avatar-default.png',
            'assets/ui/icon-trophy.png',
            
            // Space type icons
            'assets/spaces/space-normal.png',
            'assets/spaces/space-mining.png',
            'assets/spaces/space-bear-trap.png',
            'assets/spaces/space-bull-market.png',
            'assets/spaces/space-halving.png',
            'assets/spaces/space-rug-pull.png',
            'assets/spaces/space-ath.png',
            
            // Brand assets
            'assets/brands/bitcoin-logo.png',
            'assets/brands/ethereum-logo.png',
            'assets/brands/ton-logo.png',
            'assets/brands/usdt-logo.png',
            
            // Loading assets
            'assets/loading/loading-spinner.png',
            'assets/loading/progress-bar.png',
        ];
        
        this.totalAssets = assets.length;
        
        // Preload all assets
        const loadPromises = assets.map(asset => this.preloadAsset(asset));
        await Promise.all(loadPromises);
    }
    
    async preloadAsset(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                this.assetsLoaded++;
                this.updateLoadingProgress();
                resolve();
            };
            img.onerror = () => {
                console.warn(`Failed to load asset: ${src}`);
                this.assetsLoaded++;
                this.updateLoadingProgress();
                resolve();
            };
            img.src = src;
        });
    }
    
    updateLoadingProgress() {
        const progress = (this.assetsLoaded / this.totalAssets) * 100;
        document.querySelector('.progress-fill').style.width = `${progress}%`;
        document.querySelector('.loading-text').textContent = 
            `Loading TONopoly... ${Math.round(progress)}%`;
    }
    
    hideLoadingScreen() {
        document.getElementById('loading-screen').classList.remove('active');
    }
    
    generateGameId() {
        return 'game_' + Math.random().toString(36).substr(2, 9);
    }
    
    getGameIdFromUrl() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('game_id');
    }
    
    updateUrlWithGameId() {
        const newUrl = window.location.origin + window.location.pathname + 
                      '?game_id=' + this.gameId;
        window.history.replaceState({}, '', newUrl);
        document.getElementById('game-id').textContent = 'Game: ' + this.gameId;
    }
    
    async connectWebSocket() {
        const user = this.telegramApp.initDataUnsafe.user;
        const wsUrl = `wss://yourdomain.com/ws/tonopoly/${this.gameId}/${user.id}`;
        
        this.socket = new WebSocket(wsUrl);
        
        this.socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleGameUpdate(data);
        };
        
        this.socket.onopen = () => {
            console.log('Connected to TONopoly game server');
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showMessage('Connection error. Please refresh the page.', 'error');
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket connection closed');
        };
    }
    
    async joinGame() {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'join',
            user_id: user.id,
            username: user.username || user.first_name,
            color: this.playerColor
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    async setBet(amount) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'set_bet',
            user_id: user.id,
            game_id: this.gameId,
            amount: parseInt(amount)
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    async rollDice() {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'roll_dice',
            user_id: user.id,
            game_id: this.gameId
        };
        
        document.getElementById('roll-btn').disabled = true;
        
        // Play dice roll sound
        this.playSound('dice-roll-sound');
        
        // Show rolling animation
        const diceImage = document.getElementById('dice-image');
        diceImage.src = 'assets/dice/dice-rolling.gif';
        
        this.socket.send(JSON.stringify(request));
    }
    
    async movePiece(pieceIndex) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'move_piece',
            user_id: user.id,
            game_id: this.gameId,
            piece_index: pieceIndex
        };
        
        this.socket.send(JSON.stringify(request));
        this.hidePieceSelection();
    }
    
    async stakeCoins(amount) {
        const user = this.telegramApp.initDataUnsafe.user;
        const request = {
            type: 'stake_coins',
            user_id: user.id,
            game_id: this.gameId,
            amount: parseInt(amount)
        };
        
        this.socket.send(JSON.stringify(request));
    }
    
    handleGameUpdate(data) {
        switch (data.type) {
            case 'game_state':
                this.gameState = data.game_state;
                this.updateGameUI();
                break;
                
            case 'player_joined':
                this.showMessage(`${data.username} joined the game`, 'info');
                this.updatePlayersList();
                break;
                
            case 'player_left':
                this.showMessage('A player left the game', 'info');
                this.updatePlayersList();
                break;
                
            case 'bet_set':
                this.showMessage(`Bet set to ${data.amount} Telegram Stars`, 'info');
                this.updateBetUI(data.amount);
                break;
                
            case 'bet_invoice':
                this.showBetInvoice(data.invoice_url, data.amount);
                break;
                
            case 'dice_rolled':
                // Update dice image with the rolled value
                const diceImage = document.getElementById('dice-image');
                diceImage.src = `assets/dice/dice-${data.dice_value}.png`;
                
                this.showMessage(`${this.getPlayerName(data.user_id)} rolled a ${data.dice_value}`, 'info');
                
                if (data.user_id === this.telegramApp.initDataUnsafe.user.id) {
                    this.showPieceSelection();
                }
                break;
                
            case 'piece_moved':
                this.playSound('piece-move-sound');
                this.showMessage(data.message, 'info');
                
                // Check if message contains capture or bonus to play appropriate sound
                if (data.message.includes('Captured')) {
                    this.playSound('capture-sound');
                } else if (data.message.includes('Mined') || data.message.includes('Earn')) {
                    this.playSound('bonus-sound');
                }
                
                this.updateBoard();
                break;
                
            case 'coins_staked':
                this.showMessage(`${this.getPlayerName(data.user_id)} staked ${data.amount} coins`, 'info');
                this.updateGameUI();
                break;
                
            case 'game_over':
                this.playSound('win-sound');
                this.showGameOver(data.winner, data.winnings);
                break;
                
            case 'error':
                this.showMessage(data.message, 'error');
                break;
        }
    }
    
    updateGameUI() {
        if (!this.gameState) return;
        
        // Update game status
        document.getElementById('game-status').textContent = 
            this.getGameStateName(this.gameState.state);
        
        // Update players list
        this.updatePlayersList();
        
        // Update board
        this.updateBoard();
        
        // Update turn indicator
        this.updateTurnIndicator();
        
        // Show appropriate screen based on game state
        this.showScreenForState();
    }
    
    showScreenForState() {
        const screens = ['lobby', 'game', 'game-over'];
        screens.forEach(screen => {
            document.getElementById(screen).classList.remove('active');
        });
        
        switch (this.gameState.state) {
            case 0: // LOBBY
                this.showScreen('lobby');
                break;
            case 1: // WAITING_FOR_BET
                this.showScreen('lobby');
                break;
            case 2: // PLAYING
                this.showScreen('game');
                break;
            case 3: // FINISHED
                this.showScreen('game-over');
                break;
        }
    }
    
    showScreen(screenId) {
        // Hide all screens
        document.querySelectorAll('.screen').forEach(screen => {
            screen.classList.remove('active');
        });
        
        // Show the requested screen
        document.getElementById(screenId).classList.add('active');
    }
    
    updatePlayersList() {
        if (!this.gameState) return;
        
        const lobbyList = document.getElementById('players-list');
        const gameList = document.getElementById('game-players-list');
        
        lobbyList.innerHTML = '';
        gameList.innerHTML = '';
        
        this.gameState.players.forEach((player, index) => {
            const playerItem = document.createElement('div');
            playerItem.className = 'player-item';
            playerItem.innerHTML = `
                <div class="color-indicator" style="background: ${player.color};"></div>
                <span class="player-name">${player.username}</span>
                ${player.has_paid_bet ? '<span class="bet-status">✓</span>' : ''}
                ${index === this.gameState.current_turn_index ? '<span class="turn-indicator">🎲</span>' : ''}
            `;
            
            lobbyList.appendChild(playerItem.cloneNode(true));
            gameList.appendChild(playerItem);
        });
    }
    
    updateBoard() {
        if (!this.gameState) return;
        
        const board = document.getElementById('tonopoly-board');
        board.innerHTML = '';
        
        // Create board background
        const boardBg = document.createElement('div');
        boardBg.className = 'board-background';
        boardBg.style.backgroundImage = "url('assets/board/board.png')";
        board.appendChild(boardBg);
        
        // Render player pieces
        this.gameState.players.forEach(player => {
            player.pieces.forEach((position, index) => {
                if (position > 0) {
                    const pieceEl = document.createElement('div');
                    pieceEl.className = `piece ${this.getColorClass(player.color)}`;
                    pieceEl.id = `piece-${player.user_id}-${index}`;
                    
                    // Set piece position
                    const positionCoords = this.calculatePiecePosition(position, player.color);
                    pieceEl.style.left = positionCoords.x + 'px';
                    pieceEl.style.top = positionCoords.y + 'px';
                    
                    // Add shadow effect
                    const shadowEl = document.createElement('div');
                    shadowEl.className = 'piece-shadow';
                    shadowEl.style.backgroundImage = "url('assets/pieces/piece-shadow.png')";
                    shadowEl.style.left = (positionCoords.x + 2) + 'px';
                    shadowEl.style.top = (positionCoords.y + 2) + 'px';
                    board.appendChild(shadowEl);
                    
                    board.appendChild(pieceEl);
                }
            });
        });
    }
    
    calculatePiecePosition(position, color) {
        // This would need a more sophisticated algorithm based on board layout
        // For now, using a simple circular positioning
        const boardSize = 500; // Board size in pixels
        const radius = boardSize / 2 - 30;
        
        // Calculate angle based on position
        const angle = (position / 57) * 2 * Math.PI;
        
        // Calculate coordinates
        const x = radius + radius * Math.cos(angle);
        const y = radius + radius * Math.sin(angle);
        
        return { x, y };
    }
    
    getColorClass(color) {
        const colorMap = {
            '#F7931A': 'bitcoin',
            '#627EEA': 'ethereum',
            '#0088CC': 'ton',
            '#27AE60': 'stablecoin'
        };
        
        return colorMap[color] || 'bitcoin';
    }
    
    updateTurnIndicator() {
        if (!this.gameState || this.gameState.players.length === 0) return;
        
        const currentPlayer = this.gameState.players[this.gameState.current_turn_index];
        document.getElementById('current-player').textContent = currentPlayer.username;
        
        // Enable roll button if it's current player's turn
        const currentUser = this.telegramApp.initDataUnsafe.user;
        document.getElementById('roll-btn').disabled = 
            currentPlayer.user_id !== currentUser.id;
    }
    
    updateBetUI(amount) {
        document.getElementById('selected-bet-amount').textContent = amount;
        
        // Highlight selected bet button
        document.querySelectorAll('.bet-amount-btn').forEach(btn => {
            if (parseInt(btn.dataset.amount) === amount) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
        
        // Enable start game button if user is creator and all players have joined
        const user = this.telegramApp.initDataUnsafe.user;
        if (this.gameState && user.id === this.gameState.creator_id) {
            document.getElementById('start-game').disabled = 
                this.gameState.players.length < 2;
        }
    }
    
    showPieceSelection() {
        const pieceSelection = document.getElementById('piece-selection');
        pieceSelection.style.display = 'block';
        
        // Highlight available pieces (those that can move)
        const pieceOptions = document.querySelectorAll('.piece-option');
        pieceOptions.forEach((option, index) => {
            const currentUser = this.telegramApp.initDataUnsafe.user;
            const player = this.gameState.players.find(p => p.user_id === currentUser.id);
            
            if (player) {
                const canMove = this.canPieceMove(player, index);
                option.classList.toggle('available', canMove);
                
                // Set piece preview color
                const preview = option.querySelector('.piece-preview');
                preview.style.backgroundImage = `url('assets/pieces/piece-${this.getColorClass(player.color)}.png')`;
                
                option.onclick = canMove ? () => this.movePiece(index) : null;
            }
        });
    }
    
    hidePieceSelection() {
        document.getElementById('piece-selection').style.display = 'none';
    }
    
    canPieceMove(player, pieceIndex) {
        const position = player.pieces[pieceIndex];
        const diceValue = this.gameState.dice_value;
        
        // Piece at home needs a 6 to move
        if (position === 0 && diceValue === 6) {
            return true;
        }
        
        // Piece not at home can always move if it won't overshoot
        if (position > 0 && position + diceValue <= 57) {
            return true;
        }
        
        return false;
    }
    
    showBetInvoice(invoiceUrl, amount) {
        document.getElementById('bet-modal-amount').textContent = amount;
        this.showModal('bet-modal');
        
        document.getElementById('pay-bet').onclick = () => {
            this.telegramApp.openInvoice(invoiceUrl, (status) => {
                this.hideModal('bet-modal');
                if (status === 'paid') {
                    this.showMessage('Bet payment successful!', 'success');
                } else {
                    this.showMessage('Bet payment cancelled', 'error');
                }
            });
        };
        
        document.getElementById('cancel-bet').onclick = () => {
            this.hideModal('bet-modal');
            this.showMessage('Bet payment cancelled', 'error');
        };
    }
    
    showStakeModal() {
        this.showModal('stake-modal');
        
        document.getElementById('confirm-stake').onclick = () => {
            const amount = parseInt(document.getElementById('stake-amount-input').value);
            if (amount > 0) {
                this.stakeCoins(amount);
                this.hideModal('stake-modal');
            }
        };
        
        document.getElementById('cancel-stake').onclick = () => {
            this.hideModal('stake-modal');
        };
    }
    
    showModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    }
    
    hideModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }
    
    showGameOver(winnerId, winnings) {
        const winner = this.gameState.players.find(p => p.user_id === winnerId);
        if (winner) {
            document.getElementById('winner-name').textContent = winner.username;
            document.getElementById('winnings-amount').textContent = winnings;
            
            // Play celebration animation
            this.playCelebrationAnimation();
        }
    }
    
    playCelebrationAnimation() {
        const container = document.getElementById('celebration-animation');
        
        // Load Lottie animation
        if (typeof lottie !== 'undefined') {
            lottie.loadAnimation({
                container: container,
                renderer: 'svg',
                loop: true,
                autoplay: true,
                path: 'assets/animations/celebration.json'
            });
        }
    }
    
    playSound(soundId) {
        if (!this.soundEnabled) return;
        
        const sound = document.getElementById(soundId);
        if (sound) {
            sound.currentTime = 0;
            sound.play().catch(e => console.log('Audio play failed:', e));
        }
    }
    
    toggleSound() {
        this.soundEnabled = !this.soundEnabled;
        const soundBtn = document.getElementById('sound-btn');
        soundBtn.textContent = this.soundEnabled ? '🔊' : '🔇';
    }
    
    toggleMusic() {
        this.musicEnabled = !this.musicEnabled;
        const music = document.getElementById('background-music');
        
        if (this.musicEnabled) {
            music.play().catch(e => console.log('Music play failed:', e));
        } else {
            music.pause();
        }
    }
    
    showMessage(message, type = 'info') {
        const messagesContainer = document.getElementById('game-messages');
        const messageEl = document.createElement('div');
        messageEl.className = `message ${type}`;
        messageEl.textContent = message;
        
        messagesContainer.appendChild(messageEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageEl.parentNode) {
                messageEl.parentNode.removeChild(messageEl);
            }
        }, 5000);
    }
    
    getPlayerName(userId) {
        const player = this.gameState.players.find(p => p.user_id === userId);
        return player ? player.username : 'Unknown';
    }
    
    getGameStateName(state) {
        const states = ['Lobby', 'Waiting for bets', 'Playing', 'Finished'];
        return states[state] || 'Unknown';
    }
    
    renderLobby() {
        // Initial lobby rendering
        this.showScreen('lobby');
    }
    
    setupEventListeners() {
        // Color selection
        document.querySelectorAll('.color-option').forEach(option => {
            option.addEventListener('click', () => {
                document.querySelectorAll('.color-option').forEach(o => {
                    o.classList.remove('selected');
                });
                option.classList.add('selected');
                this.playerColor = option.getAttribute('data-color');
            });
        });
        
        // Bet amount selection
        document.querySelectorAll('.bet-amount-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const amount = parseInt(btn.dataset.amount);
                document.getElementById('selected-bet-amount').textContent = amount;
                
                document.querySelectorAll('.bet-amount-btn').forEach(b => {
                    b.classList.remove('selected');
                });
                btn.classList.add('selected');
            });
        });
        
        // Set bet button
        document.getElementById('set-bet').addEventListener('click', () => {
            const amount = document.getElementById('selected-bet-amount').textContent;
            if (amount > 0) {
                this.setBet(amount);
            } else {
                this.showMessage('Please select a bet amount', 'error');
            }
        });
        
        // Start game button
        document.getElementById('start-game').addEventListener('click', () => {
            // This would send a start game request to the server
            this.showMessage('Game starting...', 'info');
        });
        
        // Roll dice button
        document.getElementById('roll-btn').addEventListener('click', () => {
            this.rollDice();
        });
        
        // Stake button
        document.getElementById('stake-btn').addEventListener('click', () => {
            this.showStakeModal();
        });
        
        // Invite friends button
        document.getElementById('invite-friends').addEventListener('click', () => {
            this.inviteFriends();
        });
        
        // Sound toggle
        document.getElementById('sound-btn').addEventListener('click', () => {
            this.toggleSound();
        });
        
        // Game over buttons
        document.getElementById('play-again').addEventListener('click', () => {
            location.reload();
        });
        
        document.getElementById('back-to-lobby').addEventListener('click', () => {
            window.location.href = '/games';
        });
        
        document.getElementById('share-result').addEventListener('click', () => {
            this.shareResult();
        });
        
        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.modal').classList.remove('active');
            });
        });
    }
    
    async loadUserData() {
        try {
            // This would fetch user data from your backend
            const user = this.telegramApp.initDataUnsafe.user;
            document.getElementById('username').textContent = user.username || user.first_name;
            
            // Set avatar if available
            if (user.photo_url) {
                document.getElementById('player-avatar').src = user.photo_url;
            }
            
            // Example balances - would come from your backend
            document.getElementById('balance-gc').textContent = '15000 gc';
            document.getElementById('balance-stars').textContent = '250 ★';
            
        } catch (error) {
            console.error('Failed to load user data:', error);
        }
    }
    
    inviteFriends() {
        const shareUrl = `https://t.me/YourBotName?start=tonopoly_${this.gameId}`;
        this.telegramApp.showPopup({
            title: 'Invite Friends',
            message: `Invite friends to play TONopoly! Share this link: ${shareUrl}`,
            buttons: [{ type: 'ok' }]
        });
    }
    
    shareResult() {
        if (!this.gameState || !this.gameState.winner) return;
        
        const winner = this.gameState.players.find(p => p.user_id === this.gameState.winner);
        const message = `I just played TONopoly and ${winner.username} won ${this.gameState.total_pot * 0.95} Telegram Stars!`;
        
        this.telegramApp.shareMessage(message);
    }
}

// Initialize game when page loads
document.addEventListener('DOMContentLoaded', () => {
    new TONopolyGame();
});