// CONFIGURATIE (Direct naar Azure)
const wsUrl = "wss://memo-motion.azurewebsites.net/ws/frontend";

console.log("Connecting to:", wsUrl);

let ws = null;
let state = {
    pattern: [],
    playerSteps: [],
    gamePhase: 'idle'
};

// Connect WebSocket
function connect() {
    // Let op: we gebruiken hier de variabele wsUrl (kleine letters)
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('✓ Connected');
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
    };

    ws.onclose = () => {
        console.log('✗ Disconnected');
        setTimeout(connect, 3000);
    };
}

function handleMessage(msg) {
    console.log('←', msg.event);

    switch (msg.event) {
        case 'initial_state':
            updateStatus(msg.data);
            break;

        case 'master_status':
            updateMasterStatus(msg.data.connected);
            break;

        case 'tile_status':
            updateTileStatus(msg.data);
            break;

        case 'game_started':
            showPattern(msg.data.pattern);
            showMessage(msg.data.message);
            break;

        case 'pattern_displayed':
            state.pattern = msg.data.pattern;
            showMessage(msg.data.message);
            break;

        case 'memorizing_phase':
            state.gamePhase = 'memorizing';
            state.playerSteps = [];
            document.getElementById('stepsSection').classList.add('show');
            showMessage(msg.data.message);
            break;

        case 'player_stepped':
            addPlayerStep(msg.data.tile_id);
            break;

        case 'pattern_correct':
            showResult(true, msg.data);
            break;

        case 'pattern_wrong':
            showResult(false, msg.data);
            break;

        case 'game_ended':
            updateStats(msg.data);
            setTimeout(reset, 3000);
            break;
    }
}

function showPattern(pattern) {
    state.pattern = pattern;
    state.playerSteps = [];

    const grid = document.getElementById('patternGrid');
    grid.innerHTML = '';

    pattern.forEach((tileId, index) => {
        const tile = document.createElement('div');
        tile.className = 'pattern-tile';
        tile.textContent = tileId;
        tile.style.animationDelay = `${index * 0.1}s`;
        grid.appendChild(tile);
    });

    document.getElementById('patternSection').classList.add('show');
    document.getElementById('stepsSection').classList.remove('show');
}

function addPlayerStep(tileId) {
    state.playerSteps.push(tileId);

    const stepsGrid = document.getElementById('stepsGrid');
    const step = document.createElement('div');
    step.className = 'step-indicator';
    step.textContent = tileId;
    stepsGrid.appendChild(step);
}

function showResult(correct, data) {
    const patternGrid = document.getElementById('patternGrid');
    const tiles = patternGrid.children;

    if (correct) {
        // Highlight all as correct
        for (let tile of tiles) {
            tile.classList.add('correct');
        }
        showMessage('🎉 Perfect! You got it right!', 'success');
    } else {
        // Show which were wrong
        data.player_steps.forEach((stepId, index) => {
            if (tiles[index]) {
                if (stepId === data.expected[index]) {
                    tiles[index].classList.add('correct');
                } else {
                    tiles[index].classList.add('wrong');
                }
            }
        });
        showMessage('Oops! Try again!', 'error');
    }
}

function showMessage(text, type = '') {
    const msg = document.getElementById('message');
    const msgText = document.getElementById('messageText');

    msgText.textContent = text;
    msg.className = `message show ${type}`;

    if (type) {
        setTimeout(() => {
            msg.classList.remove('show');
        }, 3000);
    }
}

function reset() {
    state.pattern = [];
    state.playerSteps = [];
    state.gamePhase = 'idle';

    document.getElementById('patternSection').classList.remove('show');
    document.getElementById('stepsSection').classList.remove('show');
    document.getElementById('stepsGrid').innerHTML = '';
    document.getElementById('message').classList.remove('show');
}

function updateMasterStatus(connected) {
    const dot = document.getElementById('masterDot');
    const status = document.getElementById('masterStatus');

    if (connected) {
        dot.classList.add('connected');
        status.textContent = 'Master: Connected';
    } else {
        dot.classList.remove('connected');
        status.textContent = 'Master: Disconnected';
    }
}

function updateTileStatus(data) {
    const dot = document.getElementById('tilesDot');
    const status = document.getElementById('tilesStatus');

    status.textContent = `Tiles: ${data.connected}/${data.total}`;

    if (data.connected > 0) {
        dot.classList.add('connected');
    } else {
        dot.classList.remove('connected');
    }
}

function updateStats(data) {
    document.getElementById('gamesPlayed').textContent = data.games_played;
    document.getElementById('highScore').textContent = data.high_score;
}

function updateStatus(data) {
    updateMasterStatus(data.master_connected);
    if (data.tiles) {
        updateTileStatus({
            total: Object.keys(data.tiles).length,
            connected: Object.values(data.tiles).filter(t => t.connected).length
        });
    }
    updateStats(data);
}

// Start connection
connect();