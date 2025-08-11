// trivia.js
window.gameInputHistory = [];
window.answerTimes = [];
window.userId = Telegram.WebApp.initDataUnsafe.user.id;
window.userId = Telegram.WebApp.initDataUnsafe?.user?.id || 'guest';

Telegram.WebApp.ready();
Telegram.WebApp.expand();  // Use full screen

// Safe way to get user data
const initData = Telegram.WebApp.initDataUnsafe;
const user = initData.user || {};
const userId = user.id;



async function loadUserData() {
  showSpinner();
  try {
    // API call here
  } catch (error) {
    // Handle error
  } finally {
    hideSpinner();
  }
}

document.querySelectorAll('.answer-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const questionStart = Date.now() - currentQuestionStart;
        window.answerTimes.push(questionStart);
        
        window.gameInputHistory.push({
            type: 'answer',
            question_id: currentQuestion.id,
            selected: this.dataset.answer,
            time: questionStart,
            timestamp: Date.now()
        });
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const tg = window.Telegram.WebApp;
    const userId = tg.initDataUnsafe.user?.id || 'guest';
    
    // DOM elements
    const questionEl = document.getElementById('question-text');
    const optionsEl = document.getElementById('options');
    const timerFillEl = document.getElementById('timer-fill');
    const scoreEl = document.getElementById('score');
    const answeredEl = document.getElementById('answered');
    const correctEl = document.getElementById('correct');
    const accuracyEl = document.getElementById('accuracy');
    const gameScreen = document.getElementById('game-screen');
    const resultsScreen = document.getElementById('results-screen');
    
    // Game state
    let currentQuestion = null;
    let timer = null;
    let timeLeft = 0;
    let gameActive = false;
    
    // Initialize game
    startGame();
    
    function startGame() {
        fetch(`/games/trivia/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.question) {
                gameActive = true;
                displayQuestion(data.question);
            }
        });
    }
    
    function displayQuestion(question) {
        currentQuestion = question;
        questionEl.textContent = question.question;
        optionsEl.innerHTML = '';
        
        // Create option buttons
        question.options.forEach((option, index) => {
            const button = document.createElement('button');
            button.className = 'option-btn';
            button.textContent = option;
            button.dataset.index = index;
            button.addEventListener('click', () => selectOption(index));
            optionsEl.appendChild(button);
        });
        
        // Start timer
        startTimer(30);
    }
    
    function startTimer(seconds) {
        timeLeft = seconds;
        timerFillEl.style.width = '100%';
        
        clearInterval(timer);
        timer = setInterval(() => {
            timeLeft--;
            timerFillEl.style.width = `${(timeLeft / 30) * 100}%`;
            
            if (timeLeft <= 0) {
                clearInterval(timer);
                handleAnswer(-1); // Time's up
            }
        }, 1000);
    }
    
    function selectOption(optionIndex) {
        if (!gameActive) return;
        clearInterval(timer);
        handleAnswer(optionIndex);
    }
    
    function handleAnswer(selectedIndex) {
        gameActive = false;
        
        fetch(`/games/trivia/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                action: "answer",
                data: {
                    question_id: currentQuestion.id,
                    selected: selectedIndex
                }
            })
        })
        .then(res => res.json())
        .then(data => {
            // Update UI with answer feedback
            highlightAnswer(data.correct_index, selectedIndex);
            
            // Update score and stats
            scoreEl.textContent = data.score.toFixed(6);
            answeredEl.textContent = data.stats.answered;
            correctEl.textContent = data.stats.correct;
            accuracyEl.textContent = `${Math.round(data.stats.correct / data.stats.answered * 100)}%`;
            
            // Show next question after delay
            setTimeout(() => {
                if (data.next_question) {
                    displayQuestion(data.next_question);
                    gameActive = true;
                } else {
                    endGame();
                }
            }, 3000);
        });
    }
    
    function highlightAnswer(correctIndex, selectedIndex) {
        const options = document.querySelectorAll('.option-btn');
        
        options.forEach((option, index) => {
            if (index === correctIndex) {
                option.classList.add('correct');
            }
            
            if (index === selectedIndex && index !== correctIndex) {
                option.classList.add('incorrect');
            }
            
            option.disabled = true;
        });
    }
    
    function endGame() {
        fetch(`/games/trivia/end`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        })
        .then(res => res.json())
        .then(data => {
            gameScreen.style.display = 'none';
            resultsScreen.style.display = 'block';
            
            document.getElementById('total-questions').textContent = data.stats.total_questions;
            document.getElementById('final-correct').textContent = data.stats.correct_answers;
            document.getElementById('final-accuracy').textContent = `${data.stats.accuracy}%`;
            document.getElementById('base-reward').textContent = `${data.base_reward.toFixed(6)} TON`;
            document.getElementById('bonus').textContent = `${data.bonus.toFixed(6)} TON`;
            document.getElementById('total-reward').textContent = `${data.total_reward.toFixed(6)} TON`;
            
            // Handle claim button
            document.getElementById('claim-button').addEventListener('click', claimRewards);
        });

        const session_data = {
            startTime: gameStartTime,
            endTime: Date.now(),
            correct: correctAnswers,
            total: totalQuestions,
            categories: usedCategories,
            answer_times: answerTimes,
            userActions: window.gameInputHistory
        };
        
        window.reportGameCompletion(correctAnswers, session_data);
    }
    
    function claimRewards() {
        tg.sendData(JSON.stringify({
            type: "claim_rewards",
            game: "trivia",
            user_id: userId
        }));
        tg.close();
    }
});

window.reportGameCompletion = function(score, session_data) {
    fetch('/api/game/complete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Security-Token': window.securityToken
        },
        body: JSON.stringify({
            user_id: window.userId,
            game_id: 'trivia',
            score: score,
            session_data: session_data
        })
    });
};

