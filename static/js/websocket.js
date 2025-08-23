// WebSocket for real-time updates
function initWebSocket() {
    const socket = new WebSocket('wss://your-api-endpoint/ws');
    
    socket.onopen = function() {
        console.log('WebSocket connection established');
        const authData = {
            userId: Telegram.WebApp.initData.user?.id,
            hash: window.Telegram.WebApp.initData
        };
        socket.send(JSON.stringify(authData));
    };
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        switch(data.type) {
            case 'balance':
                document.getElementById('balance').textContent = 
                    `Balance: ${data.balance.toFixed(6)} TON`;
                break;
            case 'staking':
                document.getElementById('staked-amount').textContent = data.staked.toFixed(6);
                document.getElementById('staked-rewards').textContent = data.rewards.toFixed(6);
                break;
            case 'priceAlert':
                showPriceAlert(data);
                break;
            case 'event':
                showEventNotification(data);
                break;
            // Add sabotage game events
            case 'sabotage_update':
                updateSabotageGame(data.game_data);
                break;
            case 'sabotage_meeting':
                showSabotageMeeting(data.meeting_data);
                break;
            case 'sabotage_vote':
                updateSabotageVotes(data.votes);
                break;
            case 'sabotage_end':
                showSabotageResults(data.results);
                break;
        }
    };
    
    socket.onerror = function(error) {
        console.error('WebSocket error:', error);
    };
    
    socket.onclose = function() {
        console.log('WebSocket connection closed');
        setTimeout(initWebSocket, 5000); // Reconnect after 5 seconds
    };
}

function showPriceAlert(data) {
    const alertMsg = `TON price alert: $${data.price} reached!`;
    if (Notification.permission === 'granted') {
        new Notification('Price Alert', { body: alertMsg });
    } else {
        Telegram.WebApp.showAlert(alertMsg);
    }
}

function updateSabotageGame(gameData) {
    // Update game UI with current state
    if (currentPage === 'sabotage') {
        document.getElementById('vault-gold').textContent = gameData.vault_gold;
        document.getElementById('saboteurs-stash').textContent = gameData.saboteurs_stash;
        document.getElementById('time-left').textContent = formatTime(gameData.time_left);
        
        // Update player positions
        updatePlayerPositions(gameData.players);
        
        // Update task progress
        updateTaskProgress(gameData.tasks);
    }
}

function showSabotageMeeting(meetingData) {
    if (currentPage === 'sabotage') {
        // Show meeting modal
        const modal = document.getElementById('meeting-modal');
        modal.style.display = 'flex';
        
        // Populate voting options
        const optionsContainer = document.getElementById('voting-options');
        optionsContainer.innerHTML = '';
        
        meetingData.players.forEach(player => {
            if (player.is_alive && player.id !== currentPlayerId) {
                const option = document.createElement('div');
                option.className = 'vote-option';
                option.textContent = player.name;
                option.onclick = () => castVote(player.id);
                optionsContainer.appendChild(option);
            }
        });
    }
}

function showEventNotification(data) {
    const notification = document.createElement('div');
    notification.className = 'event-notification';
    notification.innerHTML = `
        <h3>${data.title}</h3>
        <p>${data.message}</p>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}