// WebSocket connection to game server
const socket = new WebSocket('wss://your-game-server.com/sabotage');

// Game state
const gameState = {
    timeLeft: 15 * 60, // 15 minutes in seconds
    vaultGold: 0,
    saboteursStash: 0,
    players: [],
    currentPlayer: {
        id: null,
        name: "Player",
        role: null,
        isAlive: true,
        room: "cafeteria"
    },
    tasks: [
        { id: 1, name: "Align Navigation Systems", room: "navigation", progress: 0, completed: false },
        { id: 2, name: "Fix Electrical Wiring", room: "electrical", progress: 0, completed: false },
        { id: 3, name: "Calibrate Oxygen Levels", room: "oxygen", progress: 0, completed: false },
        { id: 4, name: "Charge Weapon Systems", room: "weapons", progress: 0, completed: false },
        { id: 5, name: "Restock Food Supplies", room: "cafeteria", progress: 0, completed: false },
        { id: 6, name: "Organize Medical Supplies", room: "medbay", progress: 0, completed: false },
        { id: 7, name: "Sort Storage Containers", room: "storage", progress: 0, completed: false },
        { id: 8, name: "Update Admin Records", room: "admin", progress: 0, completed: false },
        { id: 9, name: "Establish Communications", room: "communications", progress: 0, completed: false }
    ],
    gameActive: false,
    isMeeting: false
};

// DOM Elements
const timeLeftEl = document.getElementById('time-left');
const vaultGoldEl = document.getElementById('vault-gold');
const playersCountEl = document.getElementById('players-count');
const playersContainerEl = document.getElementById('players-container');
const tasksContainerEl = document.getElementById('tasks-container');
const btnMine = document.getElementById('btn-mine');
const btnSteal = document.getElementById('btn-steal');
const btnMeeting = document.getElementById('btn-meeting');
const btnBribe = document.getElementById('btn-bribe');
const meetingModal = document.getElementById('meeting-modal');
const taskModal = document.getElementById('task-modal');
const bribeModal = document.getElementById('bribe-modal');
const roleModal = document.getElementById('role-modal');
const gameOverModal = document.getElementById('game-over-modal');
const notificationEl = document.getElementById('notification');

// WebSocket event handlers
socket.addEventListener('open', (event) => {
    console.log('Connected to game server');
    // Join game if we have a game ID from URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const gameId = urlParams.get('game_id');
    if (gameId) {
        socket.send(JSON.stringify({
            type: 'join_game',
            game_id: gameId,
            player_id: getPlayerId() // This would come from your auth system
        }));
    }
});

socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    handleGameMessage(data);
});

socket.addEventListener('close', (event) => {
    console.log('Disconnected from game server');
    showNotification('Connection Lost', 'Attempting to reconnect...');
    // Implement reconnection logic here
});

socket.addEventListener('error', (event) => {
    console.error('WebSocket error:', event);
    showNotification('Connection Error', 'Unable to connect to game server');
});

// Handle incoming game messages
function handleGameMessage(data) {
    switch (data.type) {
        case 'game_state':
            updateGameState(data.state);
            break;
        case 'role_assignment':
            assignRole(data.role, data.partner);
            break;
        case 'player_joined':
            playerJoined(data.player);
            break;
        case 'player_left':
            playerLeft(data.player_id);
            break;
        case 'task_completed':
            taskCompleted(data.task_id, data.player_id);
            break;
        case 'gold_stolen':
            goldStolen(data.amount, data.player_id);
            break;
        case 'meeting_called':
            meetingCalled(data.caller_id);
            break;
        case 'vote_result':
            voteResult(data.ejected_player, data.role);
            break;
        case 'bribe_offer':
            bribeOffer(data.saboteur_id, data.amount);
            break;
        case 'bribe_result':
            bribeResult(data.accepted, data.target_id);
            break;
        case 'game_over':
            gameOver(data.result, data.winners, data.rewards);
            break;
        default:
            console.warn('Unknown message type:', data.type);
    }
}

// Initialize game
function initGame() {
    // Add glowing balls to background
    addGlowingBalls();
    
    // In a real implementation, this would come from the backend via WebSocket
    gameState.players = [
        { id: 1, name: "You", role: "miner", isAlive: true, room: "cafeteria" },
        { id: 2, name: "SpaceExplorer", role: "miner", isAlive: true, room: "navigation" },
        { id: 3, name: "MoonWalker", role: "miner", isAlive: true, room: "electrical" },
        { id: 4, name: "StarGazer", role: "miner", isAlive: true, room: "oxygen" },
        { id: 5, name: "CosmoKid", role: "saboteur", isAlive: true, room: "weapons" },
        { id: 6, name: "OrbitQueen", role: "saboteur", isAlive: true, room: "medbay" }
    ];
    
    // Randomly assign role to current player (for demo purposes)
    const randomRole = Math.random() > 0.7 ? "saboteur" : "miner";
    gameState.currentPlayer.role = randomRole;
    gameState.players[0].role = randomRole;
    
    updatePlayersDisplay();
    updateTasksDisplay();
    showRoleModal();
    
    // Start game timer
    startGameTimer();
}

// Add glowing balls to background
function addGlowingBalls() {
    const container = document.querySelector('.container');
    for (let i = 0; i < 4; i++) {
        const ball = document.createElement('div');
        ball.className = 'glow-ball';
        container.appendChild(ball);
    }
}

// Show role modal at game start
function showRoleModal() {
    const roleIcon = document.getElementById('role-icon');
    const roleTitle = document.getElementById('role-title');
    const roleDescription = document.getElementById('role-description');
    
    if (gameState.currentPlayer.role === 'saboteur') {
        roleIcon.textContent = '🕵️';
        roleTitle.textContent = 'Saboteur';
        roleDescription.textContent = 'Your goal is to secretly steal gold from the common vault and avoid detection. You win if you collectively steal >50% of the total gold mined or if time runs out and you are not both ejected.';
        
        // Show saboteur actions
        btnSteal.style.display = 'block';
        btnBribe.style.display = 'block';
    } else {
        roleIcon.textContent = '👨‍🚀';
        roleTitle.textContent = 'Miner';
        roleDescription.textContent = 'Your goal is to complete tasks to mine gold and identify both Saboteurs before time runs out or before over 50% of the gold is stolen.';
    }
    
    roleModal.style.display = 'flex';
}

// Start game timer
function startGameTimer() {
    const timer = setInterval(() => {
        if (gameState.gameActive && !gameState.isMeeting) {
            gameState.timeLeft--;
            
            const minutes = Math.floor(gameState.timeLeft / 60);
            const seconds = gameState.timeLeft % 60;
            timeLeftEl.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            
            // Check for win conditions
            if (gameState.timeLeft <= 0) {
                clearInterval(timer);
                endGame('time');
            } else if (gameState.saboteursStash > gameState.vaultGold / 2) {
                clearInterval(timer);
                endGame('saboteurs');
            }
        }
    }, 1000);
}

// Update players display
function updatePlayersDisplay() {
    playersContainerEl.innerHTML = '';
    playersCountEl.textContent = `${gameState.players.filter(p => p.isAlive).length}/6`;
    
    gameState.players.forEach(player => {
        const playerEl = document.createElement('div');
        playerEl.className = 'player-item';
        
        playerEl.innerHTML = `
            <div class="player-avatar">${player.name.charAt(0)}</div>
            <div class="player-info">
                <div class="player-name">${player.name} ${player.id === 1 ? '(You)' : ''}</div>
                <div class="player-role">${player.isAlive ? (player.role === 'saboteur' ? 'Crewmate' : 'Crewmate') : 'Ejected'}</div>
            </div>
            <div class="player-status ${player.isAlive ? 'status-online' : 'status-offline'}"></div>
        `;
        
        playersContainerEl.appendChild(playerEl);
    });
    
    // Update player dots on map
    updatePlayerPositions();
}

// Update player positions on map
function updatePlayerPositions() {
    // Clear all player dots
    document.querySelectorAll('.player-dot').forEach(dot => {
        dot.style.display = 'none';
    });
    
    // Show player dots for each room
    gameState.players.forEach(player => {
        if (player.isAlive) {
            const roomEl = document.querySelector(`.room[data-room="${player.room}"]`);
            if (roomEl) {
                const dot = roomEl.querySelector('.player-dot');
                dot.style.display = 'block';
                dot.className = `player-dot ${player.role === 'saboteur' ? 'saboteur-dot' : 'miner-dot'}`;
            }
        }
    });
}

// Update tasks display
function updateTasksDisplay() {
    tasksContainerEl.innerHTML = '';
    
    gameState.tasks.forEach(task => {
        if (!task.completed) {
            const taskEl = document.createElement('div');
            taskEl.className = 'task-item';
            taskEl.innerHTML = `
                <div class="task-title">${task.name} (${task.room})</div>
                <div class="task-progress">
                    <div class="task-progress-bar" style="width: ${task.progress}%"></div>
                </div>
            `;
            tasksContainerEl.appendChild(taskEl);
        }
    });
}

// Show notification
function showNotification(title, message) {
    document.getElementById('notification-title').textContent = title;
    document.getElementById('notification-message').textContent = message;
    
    notificationEl.classList.add('show');
    
    setTimeout(() => {
        notificationEl.classList.remove('show');
    }, 3000);
}

// End game
function endGame(reason) {
    gameState.gameActive = false;
    
    const gameOverTitle = document.getElementById('game-over-title');
    const gameOverContent = document.getElementById('game-over-content');
    
    if (reason === 'saboteurs') {
        gameOverTitle.textContent = 'Saboteurs Win!';
        gameOverContent.innerHTML = `
            <p>The saboteurs have successfully stolen more than half of the gold!</p>
            <p>Total Gold Mined: ${gameState.vaultGold + gameState.saboteursStash}</p>
            <p>Gold Stolen: ${gameState.saboteursStash}</p>
            <h3>Rewards:</h3>
            <p>Saboteurs receive 4,000 GC each</p>
        `;
    } else if (reason === 'miners') {
        gameOverTitle.textContent = 'Miners Win!';
        gameOverContent.innerHTML = `
            <p>The miners have successfully identified and ejected all saboteurs!</p>
            <p>Total Gold Mined: ${gameState.vaultGold + gameState.saboteursStash}</p>
            <p>Gold Protected: ${gameState.vaultGold}</p>
            <h3>Rewards:</h3>
            <p>Miners receive 2,000 GC each</p>
        `;
    } else {
        gameOverTitle.textContent = 'Time\'s Up!';
        if (gameState.saboteursStash > gameState.vaultGold / 2) {
            gameOverContent.innerHTML = `
                <p>The saboteurs have successfully stolen more than half of the gold!</p>
                <p>Total Gold Mined: ${gameState.vaultGold + gameState.saboteursStash}</p>
                <p>Gold Stolen: ${gameState.saboteursStash}</p>
                <h3>Rewards:</h3>
                <p>Saboteurs receive 4,000 GC each</p>
            `;
        } else {
            gameOverContent.innerHTML = `
                <p>The game ended in a stalemate!</p>
                <p>Total Gold Mined: ${gameState.vaultGold + gameState.saboteursStash}</p>
                <p>Gold Stolen: ${gameState.saboteursStash}</p>
                <h3>Rewards:</h3>
                <p>All players receive 1,333 GC each</p>
            `;
        }
    }
    
    gameOverModal.style.display = 'flex';
}

// Event Listeners
document.getElementById('btn-start-game').addEventListener('click', () => {
    roleModal.style.display = 'none';
    gameState.gameActive = true;
});

btnMine.addEventListener('click', () => {
    // Find a task in the current room
    const availableTasks = gameState.tasks.filter(task => 
        task.room === gameState.currentPlayer.room && !task.completed
    );
    
    if (availableTasks.length > 0) {
        const task = availableTasks[0];
        openTaskModal(task);
    } else {
        showNotification('No Tasks', 'There are no available tasks in this room.');
    }
});

btnSteal.addEventListener('click', () => {
    if (gameState.vaultGold >= 267) {
        gameState.vaultGold -= 267;
        gameState.saboteursStash += 267;
        vaultGoldEl.textContent = gameState.vaultGold;
        showNotification('Gold Stolen', 'You successfully stole 267 gold from the vault!');
        
        // Send to server
        socket.send(JSON.stringify({
            type: 'steal_gold',
            amount: 267,
            player_id: gameState.currentPlayer.id
        }));
    } else {
        showNotification('Steal Failed', 'Not enough gold in the vault to steal.');
    }
});

btnMeeting.addEventListener('click', () => {
    openMeetingModal();
});

btnBribe.addEventListener('click', () => {
    if (gameState.saboteursStash >= 500) {
        openBribeModal();
    } else {
        showNotification('Bribe Failed', 'Not enough gold in the saboteurs stash for a bribe (500 required).');
    }
});

// Room click handling
document.querySelectorAll('.room').forEach(room => {
    room.addEventListener('click', () => {
        gameState.currentPlayer.room = room.dataset.room;
        updatePlayerPositions();
        showNotification('Room Changed', `You moved to ${room.dataset.room}`);
        
        // Send to server
        socket.send(JSON.stringify({
            type: 'move_player',
            room: room.dataset.room,
            player_id: gameState.currentPlayer.id
        }));
    });
});

// Modal close buttons
document.querySelectorAll('.close-modal').forEach(btn => {
    btn.addEventListener('click', () => {
        btn.closest('.modal').style.display = 'none';
    });
});

// These functions would be implemented based on the specific mini-games
function openTaskModal(task) {
    document.getElementById('task-modal-title').textContent = task.name;
    const gameContainer = document.getElementById('mini-game-container');
    
    // Simple mini-game implementation (would be more complex in real game)
    gameContainer.innerHTML = `
        <p>Click the buttons in the correct sequence to complete the task.</p>
        <div class="game-grid">
            <div class="game-cell">1</div>
            <div class="game-cell">2</div>
            <div class="game-cell">3</div>
            <div class="game-cell">4</div>
            <div class="game-cell">5</div>
            <div class="game-cell">6</div>
            <div class="game-cell">7</div>
            <div class="game-cell">8</div>
            <div class="game-cell">9</div>
        </div>
        <div class="game-controls">
            <button class="btn-primary" id="btn-complete-task">Complete Task</button>
            <button class="btn-secondary" id="btn-cancel-task">Cancel</button>
        </div>
    `;
    
    document.getElementById('btn-complete-task').addEventListener('click', () => {
        task.completed = true;
        gameState.vaultGold += 134;
        vaultGoldEl.textContent = gameState.vaultGold;
        updateTasksDisplay();
        taskModal.style.display = 'none';
        showNotification('Task Complete', 'You mined 134 gold for the vault!');
        
        // Send to server
        socket.send(JSON.stringify({
            type: 'complete_task',
            task_id: task.id,
            player_id: gameState.currentPlayer.id
        }));
    });
    
    document.getElementById('btn-cancel-task').addEventListener('click', () => {
        taskModal.style.display = 'none';
    });
    
    taskModal.style.display = 'flex';
}

function openMeetingModal() {
    const votingOptions = document.getElementById('voting-options');
    votingOptions.innerHTML = '';
    
    gameState.players.forEach(player => {
        if (player.id !== 1 && player.isAlive) {
            const option = document.createElement('div');
            option.className = 'vote-option';
            option.textContent = player.name;
            option.addEventListener('click', () => {
                showNotification('Vote Cast', `You voted to eject ${player.name}`);
                meetingModal.style.display = 'none';
                
                // Send to server
                socket.send(JSON.stringify({
                    type: 'cast_vote',
                    suspect_id: player.id,
                    voter_id: gameState.currentPlayer.id
                }));
            });
            
            votingOptions.appendChild(option);
        }
    });
    
    meetingModal.style.display = 'flex';
    gameState.isMeeting = true;
    
    // Close meeting after 2 minutes (for demo, we'll use 10 seconds)
    setTimeout(() => {
        if (meetingModal.style.display === 'flex') {
            meetingModal.style.display = 'none';
            gameState.isMeeting = false;
            showNotification('Meeting Ended', 'The meeting ended with no ejections.');
        }
    }, 10000);
}

function openBribeModal() {
    const bribeOptions = document.getElementById('bribe-options');
    bribeOptions.innerHTML = '';
    
    gameState.players.forEach(player => {
        if (player.role === 'miner' && player.isAlive) {
            const option = document.createElement('div');
            option.className = 'vote-option';
            option.textContent = player.name;
            option.addEventListener('click', () => {
                // Send to server
                socket.send(JSON.stringify({
                    type: 'offer_bribe',
                    target_id: player.id,
                    saboteur_id: gameState.currentPlayer.id,
                    amount: 500
                }));
                
                bribeModal.style.display = 'none';
            });
            
            bribeOptions.appendChild(option);
        }
    });
    
    bribeModal.style.display = 'flex';
}

// Initialize the game when page loads
window.addEventListener('load', initGame);

// Utility function to get player ID (would come from your auth system)
function getPlayerId() {
    // This is a placeholder - in a real implementation, you'd get this from
    // your authentication system or Telegram Mini App context
    return localStorage.getItem('player_id') || `player_${Math.random().toString(36).substr(2, 9)}`;
}