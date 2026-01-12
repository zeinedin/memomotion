// ============================================
// MEMORY XXL - GAME APPLICATION
// Dynamic Tiles based on connected ESP32 devices
// ============================================

// Game State
const gameState = {
  teamName: '',
  level: 'easy',
  score: 0,
  round: 0,
  pattern: [],
  playerSteps: [],
  connectedTiles: [],
  expectedTiles: 0,
  masterConnected: false,
  isPlaying: false,
};

// Level Configuration
const LEVEL_CONFIG = {
  easy: { steps: 4, pointsPerRound: 10, label: 'Easy Mode' },
  medium: { steps: 6, pointsPerRound: 15, label: 'Medium Mode' },
  hard: { steps: 8, pointsPerRound: 25, label: 'Hard Mode' },
};

// WebSocket connection
let socket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

// DOM Elements cache
const elements = {};

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
  cacheElements();
  setupEventListeners();
  connectWebSocket();
  loadLeaderboard();
});

function cacheElements() {
  // Screens
  elements.startScreen = document.getElementById('startScreen');
  elements.gameScreen = document.getElementById('gameScreen');
  elements.leaderboardScreen = document.getElementById('leaderboardScreen');
  elements.gameOverScreen = document.getElementById('gameOverScreen');

  // Start screen
  elements.teamNameInput = document.getElementById('teamName');
  elements.levelBtns = document.querySelectorAll('.level-btn');
  elements.startGameBtn = document.getElementById('startGameBtn');
  elements.viewLeaderboardBtn = document.getElementById('viewLeaderboardBtn');
  elements.leaderboardPreview = document.getElementById('leaderboardPreview');

  // Game screen
  elements.currentTeamName = document.getElementById('currentTeamName');
  elements.currentLevel = document.getElementById('currentLevel');
  elements.currentScore = document.getElementById('currentScore');
  elements.roundNumber = document.getElementById('roundNumber');
  elements.backToStartBtn = document.getElementById('backToStartBtn');
  elements.masterDot = document.getElementById('masterDot');
  elements.masterStatus = document.getElementById('masterStatus');
  elements.tilesDot = document.getElementById('tilesDot');
  elements.tilesStatus = document.getElementById('tilesStatus');
  elements.messageIcon = document.getElementById('messageIcon');
  elements.messageText = document.getElementById('messageText');
  elements.tileGrid = document.getElementById('tileGrid');
  elements.sequenceSection = document.getElementById('sequenceSection');
  elements.sequenceGrid = document.getElementById('sequenceGrid');
  elements.stepsSection = document.getElementById('stepsSection');
  elements.stepsGrid = document.getElementById('stepsGrid');

  // Leaderboard screen
  elements.leaderboardFull = document.getElementById('leaderboardFull');
  elements.backFromLeaderboardBtn = document.getElementById(
    'backFromLeaderboardBtn'
  );

  // Game over screen
  elements.gameOverTitle = document.getElementById('gameOverTitle');
  elements.finalScore = document.getElementById('finalScore');
  elements.finalRounds = document.getElementById('finalRounds');
  elements.finalLevel = document.getElementById('finalLevel');
  elements.playAgainBtn = document.getElementById('playAgainBtn');
  elements.backToMenuBtn = document.getElementById('backToMenuBtn');
}

function setupEventListeners() {
  // Level selection
  elements.levelBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      elements.levelBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.level = btn.dataset.level;
    });
  });

  // Navigation buttons
  elements.startGameBtn.addEventListener('click', startGame);
  elements.viewLeaderboardBtn.addEventListener('click', () =>
    showScreen('leaderboard')
  );
  elements.backToStartBtn.addEventListener('click', confirmExit);
  elements.backFromLeaderboardBtn.addEventListener('click', () =>
    showScreen('start')
  );
  elements.playAgainBtn.addEventListener('click', playAgain);
  elements.backToMenuBtn.addEventListener('click', () => showScreen('start'));

  // Enter key for team name
  elements.teamNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startGame();
  });
}

// ============================================
// SCREEN NAVIGATION
// ============================================

function showScreen(screen) {
  const screens = ['start', 'game', 'leaderboard', 'gameOver'];
  screens.forEach((s) => {
    const el = document.getElementById(`${s}Screen`);
    if (el) el.classList.remove('active');
  });

  const targetScreen = document.getElementById(`${screen}Screen`);
  if (targetScreen) {
    targetScreen.classList.add('active');
  }

  if (screen === 'leaderboard') {
    loadFullLeaderboard();
  }
}

function confirmExit() {
  if (gameState.isPlaying) {
    if (confirm('Are you sure you want to quit? Your progress will be lost!')) {
      resetGame();
      showScreen('start');
    }
  } else {
    showScreen('start');
  }
}

// ============================================
// WEBSOCKET CONNECTION
// ============================================

function connectWebSocket() {
  const wsUrl = `ws://${window.location.host}/ws/frontend`;

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('🔌 WebSocket connected');
      reconnectAttempts = 0;
      updateConnectionStatus(true);
    };

    socket.onclose = () => {
      console.log('🔌 WebSocket disconnected');
      updateConnectionStatus(false);
      attemptReconnect();
    };

    socket.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (e) {
        console.error('❌ Failed to parse message:', e);
      }
    };
  } catch (error) {
    console.error('❌ Failed to create WebSocket:', error);
    attemptReconnect();
  }
}

function attemptReconnect() {
  if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
    reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
    console.log(
      `🔄 Reconnecting in ${
        delay / 1000
      }s (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`
    );
    setTimeout(connectWebSocket, delay);
  }
}

function sendMessage(message) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(message));
  }
}

// ============================================
// WEBSOCKET MESSAGE HANDLERS
// ============================================

function handleWebSocketMessage(message) {
  console.log('📩 Received:', message);

  switch (message.type) {
    case 'status':
      handleStatusUpdate(message);
      break;
    case 'tile_status':
      updateTileStatus(message.connected_tiles, message.expected_tiles);
      break;
    case 'tile_connected':
      handleTileConnected(message.tile_id);
      break;
    case 'tile_disconnected':
      handleTileDisconnected(message.tile_id);
      break;
    case 'tile_activated':
      handleTileActivated(message.tile_id);
      break;
    case 'show_pattern':
      showPattern(message.pattern);
      break;
    case 'player_turn':
      startPlayerTurn(
        message.expected_count || LEVEL_CONFIG[gameState.level].steps
      );
      break;
    case 'step_received':
      handleStepReceived(
        message.tile_id,
        message.step_number,
        message.is_correct
      );
      break;
    case 'round_complete':
      handleRoundComplete(message.round, message.score);
      break;
    case 'game_over':
      handleGameOver(message.final_score, message.rounds);
      break;
    case 'waiting_for_start':
      setMessage('🎮', 'Press the START button on the master to begin!');
      break;
    case 'game_started':
      gameState.isPlaying = true;
      gameState.round = 0;
      gameState.score = 0;
      updateGameStats();
      setMessage('🚀', 'Game Started! Get ready...');
      break;
  }
}

function handleStatusUpdate(message) {
  gameState.masterConnected = message.master_connected;
  updateMasterStatus();

  if (message.connected_tiles) {
    updateTileStatus(message.connected_tiles, message.expected_tiles || 0);
  }
}

function updateConnectionStatus(connected) {
  if (!connected) {
    elements.masterDot.classList.remove('connected');
    elements.masterStatus.textContent = 'Master: Disconnected';
    elements.tilesDot.classList.remove('connected');
  }
}

function updateMasterStatus() {
  if (gameState.masterConnected) {
    elements.masterDot.classList.add('connected');
    elements.masterStatus.textContent = 'Master: Connected';
  } else {
    elements.masterDot.classList.remove('connected');
    elements.masterStatus.textContent = 'Master: Waiting...';
  }
}

// ============================================
// DYNAMIC TILE GRID
// ============================================

function updateTileStatus(connectedTiles, expectedTiles) {
  gameState.connectedTiles = connectedTiles || [];
  gameState.expectedTiles = expectedTiles || gameState.connectedTiles.length;

  // Update status display
  const connected = gameState.connectedTiles.length;
  const expected = Math.max(gameState.expectedTiles, connected);

  elements.tilesStatus.textContent = `Tiles: ${connected}/${expected}`;

  if (connected > 0 && connected >= expected) {
    elements.tilesDot.classList.add('connected');
  } else if (connected > 0) {
    elements.tilesDot.classList.remove('connected');
  } else {
    elements.tilesDot.classList.remove('connected');
  }

  // Rebuild the tile grid dynamically
  buildTileGrid();
}

function buildTileGrid() {
  const grid = elements.tileGrid;

  // If no tiles connected, show waiting message
  if (gameState.connectedTiles.length === 0) {
    grid.innerHTML = `
            <div class="no-tiles-message">
                <span class="no-tiles-icon">📡</span>
                <p>Waiting for tiles to connect...</p>
            </div>
        `;
    return;
  }

  // Sort tiles by ID for consistent display
  const sortedTiles = [...gameState.connectedTiles].sort((a, b) => a - b);

  // Create tile elements dynamically
  grid.innerHTML = sortedTiles
    .map(
      (tileId) => `
        <div class="tile" data-tile-id="${tileId}" id="tile-${tileId}">
            <span class="tile-number">${tileId}</span>
        </div>
    `
    )
    .join('');

  // Adjust grid columns based on tile count
  const tileCount = sortedTiles.length;
  let columns = Math.ceil(Math.sqrt(tileCount));
  if (columns < 2) columns = 2;
  if (columns > 6) columns = 6;

  grid.style.gridTemplateColumns = `repeat(${columns}, minmax(80px, 1fr))`;
}

function handleTileConnected(tileId) {
  if (!gameState.connectedTiles.includes(tileId)) {
    gameState.connectedTiles.push(tileId);
    updateTileStatus(gameState.connectedTiles, gameState.expectedTiles);
  }
}

function handleTileDisconnected(tileId) {
  const index = gameState.connectedTiles.indexOf(tileId);
  if (index > -1) {
    gameState.connectedTiles.splice(index, 1);
    updateTileStatus(gameState.connectedTiles, gameState.expectedTiles);
  }
}

function handleTileActivated(tileId) {
  const tile = document.getElementById(`tile-${tileId}`);
  if (tile) {
    tile.classList.add('active');
    setTimeout(() => {
      tile.classList.remove('active');
    }, 500);
  }
}

// ============================================
// GAME LOGIC
// ============================================

function startGame() {
  const teamName = elements.teamNameInput.value.trim();

  if (!teamName) {
    elements.teamNameInput.focus();
    elements.teamNameInput.style.borderColor = 'var(--neon-red)';
    setTimeout(() => {
      elements.teamNameInput.style.borderColor = '';
    }, 1000);
    return;
  }

  gameState.teamName = teamName;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.playerSteps = [];

  // Update UI
  elements.currentTeamName.textContent = teamName;
  elements.currentLevel.textContent = LEVEL_CONFIG[gameState.level].label;
  updateGameStats();

  // Hide pattern sections initially
  elements.sequenceSection.classList.remove('visible');
  elements.stepsSection.classList.remove('visible');

  // Set initial message
  setMessage('⏳', 'Connecting to game master...');

  // Send game start to backend
  sendMessage({
    type: 'start_game',
    team_name: teamName,
    level: gameState.level,
  });

  showScreen('game');
}

function resetGame() {
  gameState.isPlaying = false;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.playerSteps = [];

  elements.sequenceSection.classList.remove('visible');
  elements.stepsSection.classList.remove('visible');
  elements.sequenceGrid.innerHTML = '';
  elements.stepsGrid.innerHTML = '';

  // Clear tile states
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove('active', 'pattern', 'step', 'correct', 'wrong');
  });
}

function playAgain() {
  resetGame();
  sendMessage({
    type: 'start_game',
    team_name: gameState.teamName,
    level: gameState.level,
  });
  showScreen('game');
}

function updateGameStats() {
  elements.currentScore.textContent = gameState.score;
  elements.roundNumber.textContent = gameState.round;
}

function setMessage(icon, text) {
  elements.messageIcon.textContent = icon;
  elements.messageText.textContent = text;
}

// ============================================
// PATTERN DISPLAY
// ============================================

function showPattern(pattern) {
  gameState.pattern = pattern;
  setMessage('🧠', 'Watch the pattern carefully!');

  // Show sequence section
  elements.sequenceSection.classList.add('visible');
  elements.stepsSection.classList.remove('visible');
  elements.sequenceGrid.innerHTML = '';

  // Clear previous tile highlights
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove('pattern', 'step', 'correct', 'wrong');
  });

  // Animate pattern display
  let delay = 0;
  pattern.forEach((tileId, index) => {
    setTimeout(() => {
      // Add to sequence grid
      const box = document.createElement('div');
      box.className = 'sequence-box';
      box.textContent = index + 1;
      elements.sequenceGrid.appendChild(box);

      // Highlight tile on grid
      const tile = document.getElementById(`tile-${tileId}`);
      if (tile) {
        tile.classList.add('pattern');
        setTimeout(() => {
          tile.classList.remove('pattern');
        }, 600);
      }
    }, delay);
    delay += 800;
  });
}

// ============================================
// PLAYER TURN
// ============================================

function startPlayerTurn(expectedCount) {
  gameState.playerSteps = [];
  setMessage('👟', `Your turn! Repeat the pattern (${expectedCount} steps)`);

  // Show steps section
  elements.stepsSection.classList.add('visible');
  elements.stepsGrid.innerHTML = '';

  // Add waiting placeholders
  for (let i = 0; i < expectedCount; i++) {
    const box = document.createElement('div');
    box.className = 'step-box waiting';
    box.textContent = i + 1;
    elements.stepsGrid.appendChild(box);
  }
}

function handleStepReceived(tileId, stepNumber, isCorrect) {
  gameState.playerSteps.push(tileId);

  const tile = document.getElementById(`tile-${tileId}`);

  // Update step display
  const stepBoxes = elements.stepsGrid.querySelectorAll('.step-box');
  if (stepBoxes[stepNumber - 1]) {
    stepBoxes[stepNumber - 1].classList.remove('waiting');
    if (!isCorrect) {
      stepBoxes[stepNumber - 1].style.background = 'var(--gradient-danger)';
    }
  }

  // Animate tile
  if (tile) {
    if (isCorrect) {
      tile.classList.add('step', 'correct');
      setTimeout(() => {
        tile.classList.remove('correct');
      }, 500);
    } else {
      tile.classList.add('wrong');
    }
  }

  // Update message
  if (isCorrect) {
    setMessage('✅', `Step ${stepNumber} correct!`);
  } else {
    setMessage('❌', `Wrong step! Game Over!`);
  }
}

// ============================================
// ROUND COMPLETION
// ============================================

function handleRoundComplete(round, score) {
  gameState.round = round;
  gameState.score = score;
  updateGameStats();

  setMessage(
    '🎉',
    `Round ${round} Complete! +${
      LEVEL_CONFIG[gameState.level].pointsPerRound
    } points!`
  );

  // Clear tile states after a moment
  setTimeout(() => {
    document.querySelectorAll('.tile').forEach((tile) => {
      tile.classList.remove('step', 'pattern', 'correct');
    });
    elements.sequenceSection.classList.remove('visible');
    elements.stepsSection.classList.remove('visible');
  }, 1500);
}

// ============================================
// GAME OVER
// ============================================

function handleGameOver(finalScore, rounds) {
  gameState.isPlaying = false;
  gameState.score = finalScore;
  gameState.round = rounds;

  // Update game over screen
  elements.finalScore.textContent = finalScore;
  elements.finalRounds.textContent = rounds;
  elements.finalLevel.textContent = LEVEL_CONFIG[gameState.level].label.replace(
    ' Mode',
    ''
  );

  // Set title based on score
  if (finalScore >= 100) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🏆</span> INCREDIBLE!';
  } else if (finalScore >= 50) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">⭐</span> GREAT JOB!';
  } else if (finalScore > 0) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">👍</span> NICE TRY!';
  } else {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🎮</span> GAME OVER';
  }

  // Submit score
  submitScore(gameState.teamName, finalScore, gameState.level, rounds);

  showScreen('gameOver');
}

// ============================================
// LEADERBOARD
// ============================================

async function loadLeaderboard() {
  try {
    const response = await fetch('/api/leaderboard?limit=5');
    const data = await response.json();
    renderLeaderboard(elements.leaderboardPreview, data, true);
  } catch (error) {
    console.error('Failed to load leaderboard:', error);
    elements.leaderboardPreview.innerHTML =
      '<p class="empty-leaderboard">Unable to load leaderboard</p>';
  }
}

async function loadFullLeaderboard() {
  try {
    elements.leaderboardFull.innerHTML =
      '<div class="loading-spinner"><div class="spinner"></div><span>Loading...</span></div>';
    const response = await fetch('/api/leaderboard?limit=50');
    const data = await response.json();
    renderLeaderboard(elements.leaderboardFull, data, false);
  } catch (error) {
    console.error('Failed to load full leaderboard:', error);
    elements.leaderboardFull.innerHTML =
      '<p class="empty-leaderboard">Unable to load leaderboard</p>';
  }
}

function renderLeaderboard(container, entries, isPreview) {
  if (!entries || entries.length === 0) {
    container.innerHTML =
      '<p class="empty-leaderboard">No scores yet! Be the first to play!</p>';
    return;
  }

  container.innerHTML = entries
    .map((entry, index) => {
      const rank = index + 1;
      let rankClass = '';
      let itemClass = '';

      if (rank === 1) {
        rankClass = 'top-1';
        itemClass = 'gold';
      } else if (rank === 2) {
        rankClass = 'top-2';
        itemClass = 'silver';
      } else if (rank === 3) {
        rankClass = 'top-3';
        itemClass = 'bronze';
      }

      const medal =
        rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;

      return `
            <div class="leaderboard-item ${itemClass}">
                <span class="rank ${rankClass}">${medal}</span>
                <div class="team-info">
                    <span class="team-name">${escapeHtml(
                      entry.team_name
                    )}</span>
                    <span class="team-meta">${entry.level.toUpperCase()} • ${
        entry.rounds
      } rounds</span>
                </div>
                <span class="team-score">${entry.score}</span>
            </div>
        `;
    })
    .join('');
}

async function submitScore(teamName, score, level, rounds) {
  try {
    await fetch('/api/leaderboard', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        team_name: teamName,
        score: score,
        level: level,
        rounds: rounds,
      }),
    });

    // Refresh leaderboard preview
    loadLeaderboard();
  } catch (error) {
    console.error('Failed to submit score:', error);
  }
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
