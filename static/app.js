/**
 * Memory XXL Frontend - Testing Version
 * January 9, 2025
 */

// Configuration
const WS_HOST = window.location.hostname || 'localhost';
const WS_PORT = 8000;
const WS_URL = `ws://${WS_HOST}:${WS_PORT}/ws/frontend`;

// State
const state = {
    ws: null,
    connected: false,
    masterConnected: false,
    tiles: {},
    gameActive: false,
    gamesPlayed: 0,
    highScore: 0,
    currentScore: 0,
    patternLength: 0,
    progress: 0
};

// DOM Elements
const elements = {
    masterStatus: document.getElementById('masterStatus'),
    masterDot: document.getElementById('masterDot'),
    tilesStatus: document.getElementById('tilesStatus'),
    tilesDot: document.getElementById('tilesDot'),
    startBtn: document.getElementById('startBtn'),
    testBtn: document.getElementById('testBtn'),
    gamesPlayed: document.getElementById('gamesPlayed'),
    highScore: document.getElementById('highScore'),
    currentScore: document.getElementById('currentScore'),
    currentScoreCard: document.getElementById('currentScoreCard'),
    gameMessage: document.getElementById('gameMessage'),
    messageText: document.getElementById('messageText'),
    progressContainer: document.getElementById('progressContainer'),
    progressFill: document.getElementById('progressFill'),
    progressText: document.getElementById('progressText'),
    progressNumbers: document.getElementById('progressNumbers'),
    debugInfo: document.getElementById('debugInfo'),
    debugContent: document.getElementById('debugContent')
};

// ==================== WEBSOCKET ====================
function connectWebSocket() {
    console.log(`Connecting to ${WS_URL}...`);
    
    state.ws = new WebSocket(WS_URL);
    
    state.ws.onopen = () => {
        console.log('✓ WebSocket connected');
        state.connected = true;
        updateDebug();
    };
    
    state.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };
    
    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    state.ws.onclose = () => {
        console.log('✗ WebSocket disconnected');
        state.connected = false;
        state.masterConnected = false;
        updateUI();
        
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
    };
}

// ==================== MESSAGE HANDLING ====================
function handleMessage(msg) {
    console.log('←', msg.event, msg.data);
    
    switch (msg.event) {
        case 'initial_state':
            handleInitialState(msg.data);
            break;
        case 'master_status':
            handleMasterStatus(msg.data);
            break;
        case 'tile_status':
            handleTileStatus(msg.data);
            break;
        case 'game_started':
            handleGameStarted(msg.data);
            break;
        case 'pattern_complete':
            showMessage(msg.data.message, 'info');
            break;
        case 'player_turn':
            handlePlayerTurn(msg.data);
            break;
        case 'step_correct':
            handleStepCorrect(msg.data);
            break;
        case 'step_incorrect':
            handleStepIncorrect(msg.data);
            break;
        case 'round_complete':
            handleRoundComplete(msg.data);
            break;
        case 'game_ended':
            handleGameEnded(msg.data);
            break;
        case 'error':
            showMessage(msg.data.message, 'error');
            break;
    }
    
    updateDebug();
}

function handleInitialState(data) {
    state.masterConnected = data.master_connected;
    state.tiles = data.tiles || {};
    state.gameActive = data.game_active;
    state.gamesPlayed = data.games_played;
    state.highScore = data.high_score;
    updateUI();
}

function handleMasterStatus(data) {
    state.masterConnected = data.connected;
    updateUI();
}

function handleTileStatus(data) {
    state.tiles = data.tiles || {};
    updateUI();
}

function handleGameStarted(data) {
    state.gameActive = true;
    state.currentScore = 0;
    state.patternLength = data.pattern_length;
    state.progress = 0;
    
    showMessage(data.message, 'info');
    elements.currentScoreCard.classList.remove('hidden');
    elements.progressContainer.classList.remove('hidden');
    elements.startBtn.disabled = true;
    
    updateScore();
    updateProgress();
}

function handlePlayerTurn(data) {
    state.patternLength = data.pattern_length;
    showMessage(data.message, 'success');
    updateProgress();
}

function handleStepCorrect(data) {
    state.progress = data.progress;
    state.currentScore = data.score;
    
    // Flash success
    elements.currentScoreCard.classList.add('success');
    setTimeout(() => {
        elements.currentScoreCard.classList.remove('success');
    }, 300);
    
    updateScore();
    updateProgress();
}

function handleStepIncorrect(data) {
    state.currentScore = data.score;
    
    // Flash error
    elements.currentScoreCard.classList.add('error');
    setTimeout(() => {
        elements.currentScoreCard.classList.remove('error');
    }, 500);
    
    showMessage(`Wrong tile! Expected tile ${data.expected}`, 'error');
    updateScore();
}

function handleRoundComplete(data) {
    state.currentScore = data.score;
    showMessage(data.message, 'success');
    updateScore();
}

function handleGameEnded(data) {
    state.gameActive = false;
    state.gamesPlayed = data.games_played;
    state.highScore = data.high_score;
    
    showMessage(`Game Over! Final Score: ${data.score}`, 'info');
    
    setTimeout(() => {
        elements.currentScoreCard.classList.add('hidden');
        elements.progressContainer.classList.add('hidden');
        elements.startBtn.disabled = false;
    }, 3000);
    
    updateUI();
}

// ==================== UI UPDATES ====================
function updateUI() {
    // Master status
    if (state.masterConnected) {
        elements.masterStatus.textContent = 'Master: Connected';
        elements.masterDot.classList.add('connected');
        elements.masterDot.classList.remove('disconnected');
    } else {
        elements.masterStatus.textContent = 'Master: Disconnected';
        elements.masterDot.classList.remove('connected');
        elements.masterDot.classList.add('disconnected');
    }
    
    // Tiles status
    const tileIds = Object.keys(state.tiles);
    const connected = tileIds.filter(id => state.tiles[id].connected).length;
    elements.tilesStatus.textContent = `Tiles: ${connected}/${tileIds.length}`;
    
    if (connected > 0) {
        elements.tilesDot.classList.add('connected');
        elements.tilesDot.classList.remove('disconnected');
    } else {
        elements.tilesDot.classList.remove('connected');
        elements.tilesDot.classList.add('disconnected');
    }
    
    // Stats
    elements.gamesPlayed.textContent = state.gamesPlayed;
    elements.highScore.textContent = state.highScore;
    
    // Start button
    const canStart = state.masterConnected && connected >= 2 && !state.gameActive;
    elements.startBtn.disabled = !canStart;
}

function updateScore() {
    elements.currentScore.textContent = state.currentScore;
}

function updateProgress() {
    const percent = (state.progress / state.patternLength) * 100;
    elements.progressFill.style.width = `${percent}%`;
    elements.progressNumbers.textContent = `${state.progress}/${state.patternLength}`;
}

function showMessage(text, type = 'info') {
    elements.messageText.textContent = text;
    elements.gameMessage.classList.remove('hidden');
    
    // Auto-hide after 3 seconds for non-error messages
    if (type !== 'error') {
        setTimeout(() => {
            elements.gameMessage.classList.add('hidden');
        }, 3000);
    }
}

function updateDebug() {
    if (!elements.debugInfo.classList.contains('hidden')) {
        elements.debugContent.innerHTML = `
            <strong>Connection:</strong> ${state.connected ? '✓' : '✗'}<br>
            <strong>Master:</strong> ${state.masterConnected ? '✓' : '✗'}<br>
            <strong>Tiles:</strong> ${JSON.stringify(state.tiles)}<br>
            <strong>Game Active:</strong> ${state.gameActive}<br>
            <strong>Score:</strong> ${state.currentScore}<br>
            <strong>Progress:</strong> ${state.progress}/${state.patternLength}
        `;
    }
}

// ==================== BUTTON HANDLERS ====================
elements.startBtn.addEventListener('click', () => {
    if (!state.ws || !state.masterConnected) {
        alert('Not connected to backend or master!');
        return;
    }
    
    console.log('→ Starting game...');
    state.ws.send(JSON.stringify({
        event: 'start_game',
        data: {}
    }));
});

elements.testBtn.addEventListener('click', () => {
    if (!state.ws) {
        alert('Not connected to backend!');
        return;
    }
    
    console.log('→ Test button pressed');
    showMessage('Testing tiles...', 'info');
    
    // Request current state
    state.ws.send(JSON.stringify({
        event: 'request_state',
        data: {}
    }));
});

// Debug toggle (press 'd' key)
document.addEventListener('keypress', (e) => {
    if (e.key === 'd' || e.key === 'D') {
        elements.debugInfo.classList.toggle('hidden');
        updateDebug();
    }
});

// ==================== INITIALIZATION ====================
console.log('Memory XXL Frontend - Testing Version');
console.log('January 9, 2025');
connectWebSocket();

// Initial UI update
updateUI();
