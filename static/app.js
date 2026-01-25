// ============================================
// MEMORY XXL - ROBUST GAME APPLICATION
// Production-ready with proper state management
// ============================================

// ==================== CONSTANTS ====================
const TOTAL_TILES = 12;
const RECONNECT_MAX_ATTEMPTS = 10;
const RECONNECT_BASE_DELAY = 1000;

// Game Mode Configuration
const MODE_CONFIG = {
  classic: {
    name: 'Classic',
    icon: '🧠',
    description: 'Repeat the pattern shown',
  },
  speedrun: { name: 'Speed Run', icon: '⚡', description: 'Race against time' },
  endless: {
    name: 'Endless',
    icon: '♾️',
    description: 'Pattern grows each round',
  },
  simon: {
    name: 'Simon Says',
    icon: '🎯',
    description: 'Repeat the exact sequence',
  },
};

const LEVEL_CONFIG = {
  easy: { label: 'Easy', steps: 3, multiplier: 1 },
  medium: { label: 'Medium', steps: 4, multiplier: 2 },
  hard: { label: 'Hard', steps: 5, multiplier: 3 },
};

// ==================== GAME STATE ====================
const gameState = {
  // Connection
  socket: null,
  reconnectAttempts: 0,
  isConnected: false,

  // Game setup
  teamName: '',
  level: 'easy',
  mode: 'classic',

  // Game progress
  score: 0,
  round: 0,
  pattern: [],
  selectedTiles: new Set(),
  playerSequence: [], // For Simon Says

  // Hardware status
  masterConnected: false,
  connectedTiles: [],

  // UI state
  currentScreen: 'start',
  isPlaying: false,
  isShowingPattern: false,
  isSelectingPhase: false,
  scoreSubmitted: false,
};

// ==================== DOM ELEMENTS ====================
const elements = {};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
  cacheElements();
  setupEventListeners();
  buildTileGrid();
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
  elements.teamNameError = document.getElementById('teamNameError');
  elements.modeBtns = document.querySelectorAll('.mode-btn');
  elements.levelBtns = document.querySelectorAll('.level-btn');
  elements.startGameBtn = document.getElementById('startGameBtn');
  elements.viewLeaderboardBtn = document.getElementById('viewLeaderboardBtn');
  elements.leaderboardPreview = document.getElementById('leaderboardPreview');

  // Game screen
  elements.currentTeamName = document.getElementById('currentTeamName');
  elements.currentLevel = document.getElementById('currentLevel');
  elements.currentMode = document.getElementById('currentMode');
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
  elements.stepsSection = document.getElementById('stepsSection');
  elements.stepsGrid = document.getElementById('stepsGrid');

  // Leaderboard
  elements.leaderboardFull = document.getElementById('leaderboardFull');
  elements.backFromLeaderboardBtn = document.getElementById(
    'backFromLeaderboardBtn',
  );

  // Game over
  elements.gameOverTitle = document.getElementById('gameOverTitle');
  elements.finalScore = document.getElementById('finalScore');
  elements.finalRounds = document.getElementById('finalRounds');
  elements.finalLevel = document.getElementById('finalLevel');
  elements.playAgainBtn = document.getElementById('playAgainBtn');
  elements.backToMenuBtn = document.getElementById('backToMenuBtn');
}

function setupEventListeners() {
  // Mode selection
  elements.modeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('disabled')) return;
      elements.modeBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.mode = btn.dataset.mode;
    });
  });

  // Level selection
  elements.levelBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      elements.levelBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.level = btn.dataset.level;
    });
  });

  // Buttons
  elements.startGameBtn.addEventListener('click', startGame);
  elements.viewLeaderboardBtn.addEventListener('click', () =>
    showScreen('leaderboard'),
  );
  elements.backToStartBtn.addEventListener('click', confirmExit);
  elements.backFromLeaderboardBtn.addEventListener('click', () =>
    showScreen('start'),
  );
  elements.playAgainBtn.addEventListener('click', playAgain);
  elements.backToMenuBtn.addEventListener('click', () => showScreen('start'));

  // Enter key
  elements.teamNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startGame();
  });

  // Leaderboard filters
  document.querySelectorAll('.filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document
        .querySelectorAll('.filter-btn')
        .forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      loadFullLeaderboard(btn.dataset.level);
    });
  });
}

// ==================== SCREEN NAVIGATION ====================
function showScreen(screen) {
  ['start', 'game', 'leaderboard', 'gameOver'].forEach((s) => {
    const el = document.getElementById(`${s}Screen`);
    if (el) el.classList.remove('active');
  });

  const target = document.getElementById(`${screen}Screen`);
  if (target) {
    target.classList.add('active');
    gameState.currentScreen = screen;
  }

  if (screen === 'leaderboard') {
    loadFullLeaderboard();
  }
}

function confirmExit() {
  if (gameState.isPlaying) {
    if (confirm('Quit game? Your progress will be lost!')) {
      resetGameState();
      showScreen('start');
    }
  } else {
    showScreen('start');
  }
}

// ==================== WEBSOCKET ====================
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/frontend`;

  console.log('🔌 Connecting:', wsUrl);

  try {
    gameState.socket = new WebSocket(wsUrl);

    gameState.socket.onopen = () => {
      console.log('✓ WebSocket connected');
      gameState.isConnected = true;
      gameState.reconnectAttempts = 0;
      updateConnectionUI();
    };

    gameState.socket.onclose = () => {
      console.log('✗ WebSocket closed');
      gameState.isConnected = false;
      gameState.masterConnected = false;
      updateConnectionUI();
      attemptReconnect();
    };

    gameState.socket.onerror = (err) => {
      console.error('WebSocket error:', err);
    };

    gameState.socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error('Parse error:', e);
      }
    };
  } catch (err) {
    console.error('WebSocket create error:', err);
    attemptReconnect();
  }
}

function attemptReconnect() {
  if (gameState.reconnectAttempts < RECONNECT_MAX_ATTEMPTS) {
    gameState.reconnectAttempts++;
    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, gameState.reconnectAttempts - 1),
      30000,
    );
    console.log(
      `🔄 Reconnecting in ${delay}ms (${gameState.reconnectAttempts}/${RECONNECT_MAX_ATTEMPTS})`,
    );
    setTimeout(connectWebSocket, delay);
  }
}

function sendMessage(msg) {
  if (gameState.socket?.readyState === WebSocket.OPEN) {
    gameState.socket.send(JSON.stringify(msg));
  }
}

// ==================== MESSAGE HANDLING ====================
function handleMessage(msg) {
  const event = msg.event || msg.type;
  const data = msg.data || msg;

  // Reduce logging for frequent events
  if (event !== 'tile_status') {
    console.log('📩', event, data);
  }

  switch (event) {
    case 'initial_state':
    case 'state_update':
      handleStateUpdate(data);
      break;

    case 'master_status':
    case 'master_connected':
      gameState.masterConnected = data.connected !== false;
      updateConnectionUI();
      break;

    case 'master_disconnected':
      gameState.masterConnected = false;
      updateConnectionUI();
      break;

    case 'tile_status':
      handleTileStatus(data);
      break;

    case 'game_registered':
      setMessage('✅', data.message || 'Ready! Press START');
      break;

    case 'game_started':
      handleGameStarted(data);
      break;

    case 'selecting_phase':
      handleSelectingPhase(data);
      break;

    case 'tile_toggled':
      handleTileToggled(data);
      break;

    case 'pattern_correct':
      handlePatternCorrect(data);
      break;

    case 'game_over':
      handleGameOver(data);
      break;

    case 'error':
      setMessage('❌', data.message || 'Error');
      break;

    case 'info':
      setMessage('ℹ️', data.message);
      break;
  }
}

function handleStateUpdate(data) {
  if (data.master_connected !== undefined) {
    gameState.masterConnected = data.master_connected;
  }

  if (data.connected_tiles) {
    gameState.connectedTiles = data.connected_tiles;
  } else if (data.tiles) {
    gameState.connectedTiles = Object.keys(data.tiles)
      .map(Number)
      .filter((id) => data.tiles[id]?.connected);
  }

  updateConnectionUI();
  updateTileGrid();
}

function handleTileStatus(data) {
  // Extract connected tiles
  if (data.connected_tiles) {
    gameState.connectedTiles = data.connected_tiles;
  } else if (data.tiles) {
    gameState.connectedTiles = Object.keys(data.tiles)
      .map(Number)
      .filter((id) => data.tiles[id]?.connected);
  }

  // Update master status if provided
  if (data.master_connected !== undefined) {
    gameState.masterConnected = data.master_connected;
  }

  updateConnectionUI();
  updateTileGrid();
}

function handleGameStarted(data) {
  gameState.isPlaying = true;
  gameState.round = data.round || 1;
  gameState.pattern = data.pattern || [];
  gameState.selectedTiles = new Set();
  gameState.playerSequence = [];
  gameState.isShowingPattern = true;
  gameState.isSelectingPhase = false;

  if (data.round === 1) {
    gameState.score = 0;
  }

  updateGameUI();
  setMessage('🧠', data.message || `Round ${data.round}`);

  // Display pattern
  if (data.display_mode === 'sequential') {
    displayPatternSequential(data.pattern);
  } else {
    displayPatternSimultaneous(data.pattern, data.show_time || 5);
  }
}

function handleSelectingPhase(data) {
  gameState.isShowingPattern = false;
  gameState.isSelectingPhase = true;
  gameState.selectedTiles = new Set();
  gameState.playerSequence = [];

  // Clear pattern display
  clearPatternDisplay();

  setMessage('👆', data.message || 'Select the tiles!');
  showSelectionUI(data.pattern_length);
}

function handleTileToggled(data) {
  if (!gameState.isSelectingPhase) return;

  const { tile_id, is_selected, selected_tiles, expected_count } = data;

  // Update local state
  if (is_selected) {
    gameState.selectedTiles.add(tile_id);
    if (gameState.mode === 'simon') {
      gameState.playerSequence.push(tile_id);
    }
  } else if (gameState.mode !== 'simon') {
    gameState.selectedTiles.delete(tile_id);
  }

  // Update tile UI
  updateTileSelection(tile_id, is_selected);

  // Update selection counter
  updateSelectionCounter(
    selected_tiles?.length || gameState.selectedTiles.size,
    expected_count,
  );
}

function handlePatternCorrect(data) {
  gameState.score = data.score || gameState.score;
  gameState.isSelectingPhase = false;

  updateGameUI();
  setMessage('🎉', data.message || 'Perfect!');

  // Flash success on tiles
  clearTileStates();

  setTimeout(() => {
    elements.stepsSection.classList.remove('visible');
  }, 1500);
}

function handleGameOver(data) {
  gameState.isPlaying = false;
  gameState.isSelectingPhase = false;
  gameState.score = data.final_score ?? gameState.score;
  gameState.round = data.rounds ?? gameState.round;

  // Update game over screen
  elements.finalScore.textContent = gameState.score;
  elements.finalRounds.textContent = gameState.round;
  elements.finalLevel.textContent =
    LEVEL_CONFIG[gameState.level]?.label || gameState.level;

  // Set title
  if (gameState.score >= 100) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🏆</span> INCREDIBLE!';
  } else if (gameState.score >= 50) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">⭐</span> GREAT JOB!';
  } else if (gameState.score > 0) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">👍</span> NICE TRY!';
  } else {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🎮</span> GAME OVER';
  }

  showScreen('gameOver');
}

// ==================== UI UPDATES ====================
function updateConnectionUI() {
  // Master status - consider connected if we have tiles OR explicit master connection
  const hasConnection =
    gameState.masterConnected || gameState.connectedTiles.length > 0;

  if (hasConnection) {
    elements.masterDot?.classList.add('connected');
    if (elements.masterStatus) {
      elements.masterStatus.textContent = gameState.masterConnected
        ? 'Master: Connected ✓'
        : 'Master: Active';
    }
  } else {
    elements.masterDot?.classList.remove('connected');
    if (elements.masterStatus) {
      elements.masterStatus.textContent = 'Master: Waiting...';
    }
  }

  // Tiles status
  const connected = gameState.connectedTiles.length;
  if (elements.tilesStatus) {
    elements.tilesStatus.textContent = `Tiles: ${connected}/${TOTAL_TILES}`;
  }

  if (connected > 0) {
    elements.tilesDot?.classList.add('connected');
  } else {
    elements.tilesDot?.classList.remove('connected');
  }

  // Update message
  if (gameState.currentScreen === 'game' && !gameState.isPlaying) {
    if (gameState.masterConnected && connected > 0) {
      setMessage(
        '🎮',
        `${connected}/${TOTAL_TILES} tiles online! Press START to begin!`,
      );
    } else if (!gameState.masterConnected) {
      setMessage('📡', 'Waiting for Master ESP32...');
    } else {
      setMessage('📡', 'Waiting for tiles to connect...');
    }
  }
}

function updateGameUI() {
  if (elements.currentScore)
    elements.currentScore.textContent = gameState.score;
  if (elements.roundNumber) elements.roundNumber.textContent = gameState.round;
}

function setMessage(icon, text) {
  if (elements.messageIcon) elements.messageIcon.textContent = icon;
  if (elements.messageText) elements.messageText.textContent = text;
}

// ==================== TILE GRID ====================
function buildTileGrid() {
  if (!elements.tileGrid) return;

  const connectedSet = new Set(gameState.connectedTiles);

  elements.tileGrid.innerHTML = Array.from({ length: TOTAL_TILES }, (_, i) => {
    const tileId = i + 1;
    const isConnected = connectedSet.has(tileId);
    const classes = ['tile'];
    if (!isConnected) classes.push('offline');

    return `
            <div class="${classes.join(' ')}" data-tile-id="${tileId}" id="tile-${tileId}">
                <span class="tile-number">${tileId}</span>
                ${!isConnected ? '<span class="tile-offline-label">offline</span>' : ''}
            </div>
        `;
  }).join('');

  // Fixed 4x3 grid
  elements.tileGrid.style.gridTemplateColumns = 'repeat(4, minmax(70px, 1fr))';
}

function updateTileGrid() {
  const connectedSet = new Set(gameState.connectedTiles);

  for (let i = 1; i <= TOTAL_TILES; i++) {
    const tile = document.getElementById(`tile-${i}`);
    if (!tile) continue;

    const isConnected = connectedSet.has(i);

    if (isConnected) {
      tile.classList.remove('offline');
      const label = tile.querySelector('.tile-offline-label');
      if (label) label.remove();
    } else {
      tile.classList.add('offline');
      if (!tile.querySelector('.tile-offline-label')) {
        const label = document.createElement('span');
        label.className = 'tile-offline-label';
        label.textContent = 'offline';
        tile.appendChild(label);
      }
    }
  }
}

function updateTileSelection(tileId, isSelected) {
  const tile = document.getElementById(`tile-${tileId}`);
  if (!tile) return;

  if (isSelected) {
    tile.classList.add('selected', 'active');
  } else {
    tile.classList.remove('selected', 'active');
  }
}

function clearTileStates() {
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove('pattern', 'selected', 'active', 'correct', 'wrong');
  });
}

function clearPatternDisplay() {
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove('pattern', 'active');
  });
}

// ==================== PATTERN DISPLAY ====================
function displayPatternSimultaneous(pattern, duration = 5) {
  clearTileStates();

  // Light up all pattern tiles at once
  pattern.forEach((tileId) => {
    const tile = document.getElementById(`tile-${tileId}`);
    if (tile) {
      tile.classList.add('pattern', 'active');
    }
  });

  setMessage('🧠', `Memorize ${pattern.length} tiles! (${duration}s)`);
}

function displayPatternSequential(pattern) {
  clearTileStates();

  let delay = 0;
  pattern.forEach((tileId, index) => {
    setTimeout(() => {
      // Clear previous
      clearPatternDisplay();

      // Show current
      const tile = document.getElementById(`tile-${tileId}`);
      if (tile) {
        tile.classList.add('pattern', 'active');
      }

      setMessage('🎯', `Step ${index + 1}/${pattern.length}`);

      // Hide after delay
      setTimeout(() => {
        tile?.classList.remove('pattern', 'active');
      }, 600);
    }, delay);
    delay += 800;
  });
}

// ==================== SELECTION UI ====================
function showSelectionUI(expectedCount) {
  elements.stepsSection?.classList.add('visible');

  if (elements.stepsGrid) {
    elements.stepsGrid.innerHTML = `
            <div class="selection-counter">
                <span id="selected-count">0</span> / <span id="expected-count">${expectedCount}</span>
            </div>
            <div class="selection-instruction">
                <p>Select ${expectedCount} tiles</p>
                <p class="hint">${gameState.mode === 'simon' ? 'Repeat the sequence in order!' : 'Step on tiles to select'}</p>
                <p class="hint">Press CONFIRM when done</p>
            </div>
        `;
  }
}

function updateSelectionCounter(selected, expected) {
  const countEl = document.getElementById('selected-count');
  if (countEl) countEl.textContent = selected;

  const remaining = expected - selected;
  if (remaining > 0) {
    setMessage('👆', `${remaining} more tile(s) to select`);
  } else if (remaining === 0) {
    setMessage('✅', 'Press CONFIRM!');
  } else {
    setMessage('⚠️', `Too many selected (${-remaining} extra)`);
  }
}

// ==================== GAME FLOW ====================
async function startGame() {
  const teamName = elements.teamNameInput?.value.trim();

  // Validate team name
  if (!teamName || teamName.length < 2) {
    showError('Enter a team name (min 2 chars)');
    elements.teamNameInput?.focus();
    return;
  }

  // Check for duplicate name
  try {
    const res = await fetch(
      `/api/leaderboard/check-name?name=${encodeURIComponent(teamName)}`,
    );
    const data = await res.json();
    if (data.exists) {
      showError('Team name already taken!');
      return;
    }
  } catch (e) {
    console.warn('Name check failed:', e);
  }

  // Setup game state
  gameState.teamName = teamName;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.selectedTiles = new Set();
  gameState.scoreSubmitted = false;
  gameState.isPlaying = false;

  // Update UI
  if (elements.currentTeamName) elements.currentTeamName.textContent = teamName;
  if (elements.currentLevel)
    elements.currentLevel.textContent =
      LEVEL_CONFIG[gameState.level]?.label || gameState.level;
  if (elements.currentMode)
    elements.currentMode.textContent =
      MODE_CONFIG[gameState.mode]?.name || gameState.mode;
  updateGameUI();

  elements.stepsSection?.classList.remove('visible');

  // Send to backend
  sendMessage({
    type: 'start_game',
    team_name: teamName,
    level: gameState.level,
    mode: gameState.mode,
  });

  showScreen('game');
  setMessage('🎮', 'Press START on the master to begin!');
}

function showError(msg) {
  if (elements.teamNameError) {
    elements.teamNameError.textContent = msg;
    elements.teamNameError.style.display = 'block';
  }
  if (elements.teamNameInput) {
    elements.teamNameInput.style.borderColor = 'var(--neon-red)';
    setTimeout(() => {
      elements.teamNameInput.style.borderColor = '';
    }, 2000);
  }
}

function resetGameState() {
  gameState.isPlaying = false;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.selectedTiles = new Set();
  gameState.playerSequence = [];
  gameState.isShowingPattern = false;
  gameState.isSelectingPhase = false;

  elements.stepsSection?.classList.remove('visible');
  clearTileStates();
}

function playAgain() {
  resetGameState();
  sendMessage({
    type: 'start_game',
    team_name: gameState.teamName,
    level: gameState.level,
    mode: gameState.mode,
  });
  showScreen('game');
}

// ==================== LEADERBOARD ====================
async function loadLeaderboard() {
  try {
    const res = await fetch('/api/leaderboard?limit=5');
    const data = await res.json();
    const entries = data.leaderboard || data || [];
    renderLeaderboard(elements.leaderboardPreview, entries);
  } catch (e) {
    console.error('Leaderboard load error:', e);
    if (elements.leaderboardPreview) {
      elements.leaderboardPreview.innerHTML =
        '<p class="empty-leaderboard">Unable to load</p>';
    }
  }
}

async function loadFullLeaderboard(level = 'all') {
  if (elements.leaderboardFull) {
    elements.leaderboardFull.innerHTML =
      '<div class="loading-spinner"><div class="spinner"></div></div>';
  }

  try {
    const url =
      level !== 'all'
        ? `/api/leaderboard?limit=50&level=${level}`
        : '/api/leaderboard?limit=50';
    const res = await fetch(url);
    const data = await res.json();
    const entries = data.leaderboard || data || [];
    renderLeaderboard(elements.leaderboardFull, entries);
  } catch (e) {
    console.error('Full leaderboard error:', e);
    if (elements.leaderboardFull) {
      elements.leaderboardFull.innerHTML =
        '<p class="empty-leaderboard">Unable to load</p>';
    }
  }
}

function renderLeaderboard(container, entries) {
  if (!container) return;

  if (!entries || entries.length === 0) {
    container.innerHTML =
      '<p class="empty-leaderboard">No scores yet! Be the first!</p>';
    return;
  }

  // Deduplicate by team name (keep best score)
  const best = {};
  entries.forEach((e) => {
    const key = e.team_name?.toLowerCase();
    if (!best[key] || e.score > best[key].score) {
      best[key] = e;
    }
  });

  const sorted = Object.values(best).sort((a, b) => b.score - a.score);

  container.innerHTML = sorted
    .map((entry, i) => {
      const rank = i + 1;
      const medal =
        rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : rank;
      const itemClass =
        rank === 1
          ? 'gold'
          : rank === 2
            ? 'silver'
            : rank === 3
              ? 'bronze'
              : '';
      const rankClass = rank <= 3 ? `top-${rank}` : '';

      return `
            <div class="leaderboard-item ${itemClass}">
                <span class="rank ${rankClass}">${medal}</span>
                <div class="team-info">
                    <span class="team-name">${escapeHtml(entry.team_name)}</span>
                    <span class="team-meta">${(entry.level || 'easy').toUpperCase()} • ${entry.rounds || 0} rounds</span>
                </div>
                <span class="team-score">${entry.score || 0}</span>
            </div>
        `;
    })
    .join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}
