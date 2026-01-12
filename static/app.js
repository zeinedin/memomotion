// Memory XXL - Frontend Application

// ==================== CONFIGURATION ====================
const API_URL = window.location.origin;
const WS_PROTOCOL = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${WS_PROTOCOL}//${window.location.host}/ws/frontend`;

console.log('API URL:', API_URL);
console.log('WebSocket URL:', WS_URL);

// ==================== STATE ====================
let ws = null;
let gameState = {
  teamName: '',
  level: 'easy',
  pattern: [],
  playerSteps: [],
  currentScore: 0,
  roundNumber: 0,
  gamePhase: 'idle',
  connectedTiles: [],
};

const levelConfig = {
  easy: { patternLength: 4, pointsPerTile: 10, name: 'Easy' },
  medium: { patternLength: 6, pointsPerTile: 15, name: 'Medium' },
  hard: { patternLength: 8, pointsPerTile: 25, name: 'Hard' },
};

// ==================== DOM ELEMENTS ====================
const screens = {
  start: document.getElementById('startScreen'),
  game: document.getElementById('gameScreen'),
  leaderboard: document.getElementById('leaderboardScreen'),
  gameOver: document.getElementById('gameOverScreen'),
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  connectWebSocket();
  loadLeaderboard();
});

function initEventListeners() {
  // Level selector
  document.querySelectorAll('.level-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document
        .querySelectorAll('.level-btn')
        .forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.level = btn.dataset.level;
    });
  });

  // Start game button
  document.getElementById('startGameBtn').addEventListener('click', startGame);

  // Navigation buttons
  document
    .getElementById('viewLeaderboardBtn')
    .addEventListener('click', () => showScreen('leaderboard'));
  document
    .getElementById('backFromLeaderboardBtn')
    .addEventListener('click', () => showScreen('start'));
  document.getElementById('backToStartBtn').addEventListener('click', () => {
    if (confirm('Weet je zeker dat je wilt stoppen?')) {
      showScreen('start');
    }
  });

  // Game over buttons
  document.getElementById('playAgainBtn').addEventListener('click', () => {
    showScreen('game');
    resetGameState();
  });
  document
    .getElementById('backToMenuBtn')
    .addEventListener('click', () => showScreen('start'));
}

// ==================== SCREEN MANAGEMENT ====================
function showScreen(screenName) {
  Object.values(screens).forEach((screen) => screen.classList.remove('active'));
  screens[screenName].classList.add('active');

  if (screenName === 'leaderboard') {
    loadFullLeaderboard();
  }
}

// ==================== WEBSOCKET ====================
function connectWebSocket() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log('✓ WebSocket connected');
    updateConnectionStatus(true);
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleWebSocketMessage(msg);
  };

  ws.onclose = () => {
    console.log('✗ WebSocket disconnected');
    updateConnectionStatus(false);
    setTimeout(connectWebSocket, 3000);
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
}

function handleWebSocketMessage(msg) {
  console.log('← Received:', msg.event);

  switch (msg.event) {
    case 'initial_state':
      updateMasterStatus(msg.data.master_connected);
      break;

    case 'master_status':
      updateMasterStatus(msg.data.connected);
      break;

    case 'tile_status':
      updateTileStatus(msg.data);
      break;

    case 'game_started':
      handleGameStarted(msg.data);
      break;

    case 'pattern_displayed':
      handlePatternDisplayed(msg.data);
      break;

    case 'memorizing_phase':
      handleMemorizingPhase(msg.data);
      break;

    case 'player_stepped':
      handlePlayerStep(msg.data);
      break;

    case 'pattern_correct':
      handlePatternResult(true, msg.data);
      break;

    case 'pattern_wrong':
      handlePatternResult(false, msg.data);
      break;

    case 'game_ended':
      handleGameEnded(msg.data);
      break;
  }
}

// ==================== GAME FUNCTIONS ====================
function startGame() {
  const teamName = document.getElementById('teamName').value.trim();

  if (!teamName) {
    alert('Voer een teamnaam in!');
    return;
  }

  gameState.teamName = teamName;
  gameState.currentScore = 0;
  gameState.roundNumber = 0;

  // Update UI
  document.getElementById('currentTeamName').textContent = teamName;
  document.getElementById('currentLevel').textContent =
    levelConfig[gameState.level].name;
  document.getElementById('currentScore').textContent = '0';
  document.getElementById('roundNumber').textContent = '0';

  // Send team info to backend
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        event: 'start_game',
        data: {
          team_name: teamName,
          level: gameState.level,
        },
      })
    );
  }

  showScreen('game');
  resetGameUI();
  showMessage('Druk op de START knop om te beginnen!');
}

function resetGameState() {
  gameState.pattern = [];
  gameState.playerSteps = [];
  gameState.roundNumber = 0;
  gameState.currentScore = 0;
  gameState.gamePhase = 'idle';
  document.getElementById('currentScore').textContent = '0';
  document.getElementById('roundNumber').textContent = '0';
  resetGameUI();
}

function resetGameUI() {
  // Reset tile grid
  document.querySelectorAll('.tile-box').forEach((tile) => {
    tile.classList.remove('highlight', 'active', 'correct', 'wrong', 'stepped');
  });

  // Hide sections
  document.getElementById('sequenceSection').classList.remove('show');
  document.getElementById('stepsSection').classList.remove('show');
  document.getElementById('sequenceGrid').innerHTML = '';
  document.getElementById('stepsGrid').innerHTML = '';
}

function handleGameStarted(data) {
  gameState.gamePhase = 'showing_pattern';
  gameState.pattern = data.pattern;
  gameState.roundNumber++;

  document.getElementById('roundNumber').textContent = gameState.roundNumber;
  showMessage('Kijk naar het patroon! 👀');

  // Show pattern on tile grid with animation
  animatePattern(data.pattern);

  // Show pattern sequence
  showPatternSequence(data.pattern);
}

function animatePattern(pattern) {
  resetGameUI();
  document.getElementById('sequenceSection').classList.add('show');

  pattern.forEach((tileId, index) => {
    setTimeout(() => {
      // Highlight tile in grid
      const tile = document.querySelector(`.tile-box[data-tile="${tileId}"]`);
      if (tile) {
        tile.classList.add('highlight');

        // Remove highlight after a moment
        setTimeout(() => {
          tile.classList.remove('highlight');
          tile.classList.add('active');
        }, 600);
      }

      // Fill sequence box
      const sequenceBoxes = document.querySelectorAll(
        '#sequenceGrid .sequence-box'
      );
      if (sequenceBoxes[index]) {
        sequenceBoxes[index].classList.add('filled');
      }
    }, index * 800);
  });
}

function showPatternSequence(pattern) {
  const grid = document.getElementById('sequenceGrid');
  grid.innerHTML = '';

  pattern.forEach((tileId, index) => {
    const box = document.createElement('div');
    box.className = 'sequence-box';
    box.innerHTML = `<span class="step-number">${index + 1}</span>`;
    grid.appendChild(box);
  });
}

function handlePatternDisplayed(data) {
  gameState.pattern = data.pattern;
  showMessage('Onthoud het patroon!');
}

function handleMemorizingPhase(data) {
  gameState.gamePhase = 'memorizing';
  gameState.playerSteps = [];

  showMessage('Stap op de tegels in de juiste volgorde! 🦶');

  document.getElementById('stepsSection').classList.add('show');
  document.getElementById('stepsGrid').innerHTML = '';

  // Create empty step boxes
  for (let i = 0; i < gameState.pattern.length; i++) {
    const box = document.createElement('div');
    box.className = 'sequence-box';
    box.innerHTML = `<span class="step-number">${i + 1}</span>`;
    document.getElementById('stepsGrid').appendChild(box);
  }
}

function handlePlayerStep(data) {
  gameState.playerSteps.push(data.tile_id);

  // Highlight stepped tile in grid
  const tile = document.querySelector(`.tile-box[data-tile="${data.tile_id}"]`);
  if (tile) {
    tile.classList.add('stepped');
  }

  // Fill step box
  const stepBoxes = document.querySelectorAll('#stepsGrid .sequence-box');
  const stepIndex = gameState.playerSteps.length - 1;
  if (stepBoxes[stepIndex]) {
    stepBoxes[stepIndex].classList.add('filled');
  }

  showMessage(
    `Stap ${gameState.playerSteps.length} van ${gameState.pattern.length}`
  );
}

function handlePatternResult(correct, data) {
  gameState.gamePhase = 'result';

  const stepBoxes = document.querySelectorAll('#stepsGrid .sequence-box');
  const patternBoxes = document.querySelectorAll('#sequenceGrid .sequence-box');

  if (correct) {
    // All correct
    stepBoxes.forEach((box) => box.classList.add('correct'));
    patternBoxes.forEach((box) => box.classList.add('correct'));

    // Update score
    const points =
      gameState.pattern.length * levelConfig[gameState.level].pointsPerTile;
    gameState.currentScore += points;
    document.getElementById('currentScore').textContent =
      gameState.currentScore;

    showMessage('🎉 Perfect! +' + points + ' punten!', 'success');

    // Save score to leaderboard
    saveScore();
  } else {
    // Show which were wrong
    data.player_steps.forEach((stepId, index) => {
      if (stepBoxes[index]) {
        if (stepId === data.expected[index]) {
          stepBoxes[index].classList.add('correct');
        } else {
          stepBoxes[index].classList.add('wrong');
        }
      }
    });

    showMessage('❌ Fout! Probeer opnieuw!', 'error');
  }
}

function handleGameEnded(data) {
  // Show game over screen after a delay
  setTimeout(() => {
    document.getElementById('finalScore').textContent = gameState.currentScore;
    document.getElementById('finalRounds').textContent = gameState.roundNumber;
    document.getElementById('finalLevel').textContent =
      levelConfig[gameState.level].name;

    if (gameState.currentScore > 0) {
      document.getElementById('gameOverTitle').textContent =
        '🎉 Goed gespeeld!';
    } else {
      document.getElementById('gameOverTitle').textContent = 'Spel Voorbij!';
    }

    showScreen('gameOver');
  }, 2000);
}

// ==================== UI UPDATES ====================
function showMessage(text, type = '') {
  const messageEl = document.getElementById('gameMessage');
  const textEl = document.getElementById('messageText');

  textEl.textContent = text;
  messageEl.className = 'game-message ' + type;
  messageEl.style.animation = 'none';
  messageEl.offsetHeight; // Trigger reflow
  messageEl.style.animation = 'slideIn 0.3s ease-out';
}

function updateConnectionStatus(connected) {
  // Update UI based on websocket connection
}

function updateMasterStatus(connected) {
  const dot = document.getElementById('masterDot');
  const status = document.getElementById('masterStatus');

  if (connected) {
    dot.classList.add('connected');
    status.textContent = 'Master: Verbonden';
  } else {
    dot.classList.remove('connected');
    status.textContent = 'Master: Niet verbonden';
  }
}

function updateTileStatus(data) {
  const dot = document.getElementById('tilesDot');
  const status = document.getElementById('tilesStatus');

  gameState.connectedTiles = Object.entries(data.tiles || {})
    .filter(([id, info]) => info.connected)
    .map(([id]) => parseInt(id));

  status.textContent = `Tegels: ${data.connected}/${data.total}`;

  if (data.connected > 0) {
    dot.classList.add('connected');
  } else {
    dot.classList.remove('connected');
  }

  // Update tile grid to show connected tiles
  document.querySelectorAll('.tile-box').forEach((tile) => {
    const tileId = parseInt(tile.dataset.tile);
    if (gameState.connectedTiles.includes(tileId)) {
      tile.classList.add('active');
    } else {
      tile.classList.remove('active');
    }
  });
}

// ==================== LEADERBOARD ====================
async function loadLeaderboard() {
  try {
    const response = await fetch(`${API_URL}/api/leaderboard?limit=5`);
    if (response.ok) {
      const data = await response.json();
      renderLeaderboardPreview(data.leaderboard);
    }
  } catch (error) {
    console.error('Error loading leaderboard:', error);
    document.getElementById('leaderboardPreview').innerHTML =
      '<div class="loading">Kon leaderboard niet laden</div>';
  }
}

async function loadFullLeaderboard() {
  try {
    const response = await fetch(`${API_URL}/api/leaderboard?limit=50`);
    if (response.ok) {
      const data = await response.json();
      renderFullLeaderboard(data.leaderboard);
    }
  } catch (error) {
    console.error('Error loading leaderboard:', error);
    document.getElementById('leaderboardFull').innerHTML =
      '<div class="loading">Kon leaderboard niet laden</div>';
  }
}

function renderLeaderboardPreview(entries) {
  const container = document.getElementById('leaderboardPreview');

  if (!entries || entries.length === 0) {
    container.innerHTML = '<div class="loading">Nog geen scores!</div>';
    return;
  }

  container.innerHTML = entries
    .map((entry, index) => createLeaderboardItem(entry, index))
    .join('');
}

function renderFullLeaderboard(entries) {
  const container = document.getElementById('leaderboardFull');

  if (!entries || entries.length === 0) {
    container.innerHTML = '<div class="loading">Nog geen scores!</div>';
    return;
  }

  container.innerHTML = entries
    .map((entry, index) => createLeaderboardItem(entry, index))
    .join('');
}

function createLeaderboardItem(entry, index) {
  let rankClass = '';
  if (index === 0) rankClass = 'gold';
  else if (index === 1) rankClass = 'silver';
  else if (index === 2) rankClass = 'bronze';

  return `
        <div class="leaderboard-item ${rankClass}">
            <div class="rank ${rankClass}">${index + 1}</div>
            <div class="team-details">
                <div class="team-name-lb">${escapeHtml(entry.team_name)}</div>
                <div class="team-level-lb">${entry.level}</div>
            </div>
            <div class="team-score">${entry.score}</div>
        </div>
    `;
}

async function saveScore() {
  if (gameState.currentScore <= 0) return;

  try {
    await fetch(`${API_URL}/api/leaderboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        team_name: gameState.teamName,
        score: gameState.currentScore,
        level: gameState.level,
        rounds: gameState.roundNumber,
      }),
    });
    console.log('Score saved!');
  } catch (error) {
    console.error('Error saving score:', error);
  }
}

// ==================== UTILITIES ====================
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
