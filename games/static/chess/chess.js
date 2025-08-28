// Chess game frontend logic
document.addEventListener('DOMContentLoaded', function() {
    let game = new Chess();
    let board = null;
    let gameId = null;
    let userColor = null;
    let userStars = 0;
    let userCoins = 0;
    let userId = null;
    
    // Initialize the chess board
    function initBoard() {
        let config = {
            position: 'start',
            draggable: true,
            onDrop: handleMove,
            pieceTheme: '/games/assets/chess/pieces/{piece}.png'
        };
        board = Chessboard('chessboard', config);
    }
    
    // Initialize game data
    function initGame() {
        // Get user ID from URL or storage
        const urlParams = new URLSearchParams(window.location.search);
        userId = urlParams.get('user_id') || localStorage.getItem('user_id');
        
        if (!userId) {
            alert('User authentication required');
            return;
        }
        
        // Store user ID for future use
        localStorage.setItem('user_id', userId);
        
        // Load initial game data
        fetch('/games/api/chess/init', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                userStars = data.game_data.user_data.stars_balance || 0;
                userCoins = data.game_data.user_data.game_coins || 0;
                
                updateUI();
                loadChallenges();
                
                // Check if user has active games
                if (data.game_data.active_games && data.game_data.active_games.length > 0) {
                    const activeGame = data.game_data.active_games[0];
                    gameId = activeGame.game_id;
                    userColor = activeGame.your_color;
                    loadGameState();
                }
            } else {
                alert('Failed to initialize game: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error initializing game:', error);
            alert('Failed to initialize game');
        });
    }
    
    // Update UI with current data
    function updateUI() {
        document.getElementById('user-stars').textContent = `Stars: ${userStars}`;
        document.getElementById('user-coins').textContent = `Coins: ${userCoins}`;
    }
    
    // Load available challenges
    function loadChallenges() {
        fetch('/games/api/chess/init', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const challengesList = document.getElementById('challenges-list');
                challengesList.innerHTML = '';
                
                if (data.game_data.available_challenges && data.game_data.available_challenges.length > 0) {
                    data.game_data.available_challenges.forEach(challenge => {
                        const challengeItem = document.createElement('div');
                        challengeItem.className = 'challenge-item';
                        challengeItem.innerHTML = `
                            <p>Challenger: ${challenge.challenger_id}</p>
                            <p>Stake: ${challenge.stake} Stars</p>
                            <p>Color: ${challenge.challenger_color}</p>
                            <button onclick="acceptChallenge('${challenge.challenge_id}')">Accept Challenge</button>
                        `;
                        challengesList.appendChild(challengeItem);
                    });
                } else {
                    challengesList.innerHTML = '<p>No challenges available</p>';
                }
            }
        })
        .catch(error => {
            console.error('Error loading challenges:', error);
        });
    }
    
    // Handle chess move
    function handleMove(source, target) {
        // If it's not the user's turn, don't allow moves
        if ((userColor === 'white' && game.turn() !== 'w') || 
            (userColor === 'black' && game.turn() !== 'b')) {
            return 'snapback';
        }
        
        // Make the move
        const move = game.move({
            from: source,
            to: target,
            promotion: 'q' // Always promote to queen for simplicity
        });
        
        // If illegal move, snapback
        if (move === null) return 'snapback';
        
        // Update board
        board.position(game.fen());
        
        // Send move to server
        fetch('/games/api/chess/move', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            },
            body: JSON.stringify({
                game_id: gameId,
                move: move.san
            })
        })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Move failed: ' + (data.error || 'Unknown error'));
                // Revert the move on the board
                game.undo();
                board.position(game.fen());
            } else if (data.is_game_over) {
                alert(`Game over! Result: ${data.game_result.winner || 'Draw'}`);
            }
        })
        .catch(error => {
            console.error('Error making move:', error);
            alert('Failed to make move');
            // Revert the move on the board
            game.undo();
            board.position(game.fen());
        });
        
        return move;
    }
    
    // Load game state from server
    function loadGameState() {
        if (!gameId) return;
        
        fetch(`/games/api/chess/state?game_id=${gameId}`, {
            headers: {
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                game.load(data.fen);
                board.position(data.fen);
                
                // Update status message
                let statusMsg = `Game: ${data.white_player} (White) vs ${data.black_player} (Black) | `;
                statusMsg += `Stake: ${data.white_stake} Stars | `;
                statusMsg += `Turn: ${data.current_turn}`;
                
                if (data.is_check) statusMsg += ' | Check!';
                if (data.is_checkmate) statusMsg += ' | Checkmate!';
                if (data.is_stalemate) statusMsg += ' | Stalemate!';
                
                document.getElementById('status-message').textContent = statusMsg;
            }
        })
        .catch(error => {
            console.error('Error loading game state:', error);
        });
    }
    
    // Create a new challenge
    window.createChallenge = function() {
        const stake = parseInt(document.getElementById('stake-amount').value);
        const color = document.getElementById('color-preference').value;
        
        fetch('/games/api/chess/create_challenge', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            },
            body: JSON.stringify({
                stake: stake,
                color: color
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(`Challenge created! Challenge ID: ${data.challenge_id}`);
                loadChallenges();
            } else {
                alert('Failed to create challenge: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error creating challenge:', error);
            alert('Failed to create challenge');
        });
    };
    
    // Accept a challenge
    window.acceptChallenge = function(challengeId) {
        fetch('/games/api/chess/accept_challenge', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            },
            body: JSON.stringify({
                challenge_id: challengeId
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                gameId = data.game_id;
                userColor = data.your_color;
                alert(`Challenge accepted! Game ID: ${gameId}, Your color: ${userColor}`);
                loadGameState();
            } else {
                alert('Failed to accept challenge: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error accepting challenge:', error);
            alert('Failed to accept challenge');
        });
    };
    
    // Place a bet
    window.placeBet = function() {
        if (!gameId) {
            alert('No active game to bet on');
            return;
        }
        
        const amount = parseInt(document.getElementById('bet-amount').value);
        const player = document.getElementById('bet-player').value;
        
        fetch('/games/api/chess/bet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Telegram-InitData': window.Telegram.WebApp.initData || ''
            },
            body: JSON.stringify({
                game_id: gameId,
                amount: amount,
                on_player: player
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                userCoins = data.new_balance;
                updateUI();
                alert(`Bet placed! ${amount} coins on ${player}`);
            } else {
                alert('Failed to place bet: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error placing bet:', error);
            alert('Failed to place bet');
        });
    };
    
    // Initialize the game
    initBoard();
    initGame();
    
    // Set up event listeners
    document.getElementById('create-challenge-btn').addEventListener('click', window.createChallenge);
    document.getElementById('place-bet-btn').addEventListener('click', window.placeBet);
    
    // Set up Telegram Web App integration if available
    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
    }
});