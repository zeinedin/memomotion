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
  easy: { label: 'Easy', steps: 1, multiplier: 1 },
  medium: { label: 'Medium', steps: 3, multiplier: 2 },
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

  // Speedrun timer
  speedrunTimeRemaining: 0,
  speedrunTimeLimit: 0,
  isSpeedrun: false,
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

  // Speedrun timer elements
  elements.timerBox = document.getElementById('timerBox');
  elements.timerValue = document.getElementById('timerValue');
  elements.timerBar = document.getElementById('timerBar');

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

  // Buttons - with null checks
  elements.startGameBtn?.addEventListener('click', startGame);
  elements.viewLeaderboardBtn?.addEventListener('click', () =>
    showScreen('leaderboard'),
  );
  elements.backToStartBtn?.addEventListener('click', confirmExit);
  elements.backFromLeaderboardBtn?.addEventListener('click', () =>
    showScreen('start'),
  );
  elements.playAgainBtn?.addEventListener('click', playAgain);
  elements.backToMenuBtn?.addEventListener('click', () => showScreen('start'));

  // Enter key
  elements.teamNameInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startGame();
  });

  // Clear errors on input
  elements.teamNameInput?.addEventListener('input', () => {
    if (elements.teamNameError) {
      elements.teamNameError.style.display = 'none';
      elements.teamNameInput.setAttribute('aria-invalid', 'false');
      elements.teamNameInput.style.borderColor = '';
    }
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

  // Refresh leaderboard preview when returning to start screen
  if (screen === 'start') {
    loadLeaderboard();
    // Clear any error messages
    if (elements.teamNameError) {
      elements.teamNameError.style.display = 'none';
    }
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

  try {
    gameState.socket = new WebSocket(wsUrl);

    gameState.socket.onopen = () => {
      gameState.isConnected = true;
      gameState.reconnectAttempts = 0;
      updateConnectionUI();
    };

    gameState.socket.onclose = () => {
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

  switch (event) {
    case 'initial_state':
    case 'state_update':
      handleStateUpdate(data);
      break;

    case 'master_status':
    case 'master_connected':
      gameState.masterConnected = data.connected !== false;
      // If master disconnected during game, show pause message but don't clear tiles
      if (!gameState.masterConnected && gameState.isPlaying) {
        setMessage('⏸️', 'Hub disconnected - waiting for reconnection...');
      } else if (!gameState.masterConnected) {
        gameState.connectedTiles = [];
      }
      updateConnectionUI();
      if (!gameState.isPlaying) {
        updateTileGrid();
      }
      break;

    case 'master_disconnected':
      gameState.masterConnected = false;
      // If game is active, show pause message instead of clearing everything
      if (gameState.isPlaying) {
        setMessage('⏸️', 'Hub disconnected - waiting for reconnection...');
      } else {
        gameState.connectedTiles = [];
        updateTileGrid();
      }
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

    case 'game_won':
      handleGameWon(data);
      break;

    case 'speedrun_timer':
      handleSpeedrunTimer(data);
      break;

    case 'game_reset':
      // Admin triggered reset - return to start screen
      resetGameState();
      showScreen('start');
      setMessage('🔄', 'Game reset by admin');
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

  // Handle Speedrun mode
  if (data.speedrun) {
    gameState.isSpeedrun = true;
    gameState.speedrunTimeRemaining = data.time_remaining || 0;
    gameState.speedrunTimeLimit = data.time_limit || 60;
    showSpeedrunTimer(true);
    updateSpeedrunTimer(data.time_remaining, data.time_limit);
  } else {
    gameState.isSpeedrun = false;
    showSpeedrunTimer(false);
  }

  updateGameUI();
  setMessage(
    '👽',
    data.message || `Sequence ${data.round} - BoB is transmitting!`,
  );

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

  // Hide tile numbers in Classic mode after pattern is shown
  if (gameState.mode === 'classic') {
    document.querySelectorAll('.tile').forEach((tile) => {
      tile.classList.add('hide-number');
    });
  }

  setMessage('�', data.message || 'Run to the tiles! Fuel the ship!');
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
  setMessage('⛽', data.message || 'Fuel collected! BoB is happy!');

  // Flash success on tiles
  clearTileStates();

  setTimeout(() => {
    elements.stepsSection?.classList.remove('visible');
  }, 1500);
}

function handleGameOver(data) {
  gameState.isPlaying = false;
  gameState.isSelectingPhase = false;
  gameState.isSpeedrun = false;
  showSpeedrunTimer(false);
  gameState.score = data.final_score ?? gameState.score;
  gameState.round = data.rounds ?? gameState.round;

  // Update game over screen
  elements.finalScore.textContent = gameState.score;
  elements.finalRounds.textContent = gameState.round;
  elements.finalLevel.textContent =
    LEVEL_CONFIG[gameState.level]?.label || gameState.level;

  // Set title based on timeout or score - ZAP theme
  if (data.timeout) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">⏱️</span> TIME\'S UP! BoB is stranded!';
  } else if (gameState.score >= 1000) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🚀</span> LAUNCH SUCCESS!';
  } else if (gameState.score >= 500) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">🛸</span> ALMOST THERE!';
  } else if (gameState.score >= 100) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">👽</span> GOOD EFFORT!';
  } else if (gameState.score > 0) {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">💫</span> BoB believes in you!';
  } else {
    elements.gameOverTitle.innerHTML =
      '<span class="title-icon">👽</span> MISSION FAILED';
  }

  showScreen('gameOver');
}

function handleGameWon(data) {
  gameState.isPlaying = false;
  gameState.isSelectingPhase = false;
  gameState.isSpeedrun = false;
  showSpeedrunTimer(false);
  gameState.score = data.final_score ?? gameState.score;
  gameState.round = data.rounds ?? gameState.round;

  // Update game over screen with win message
  elements.finalScore.textContent = gameState.score;
  elements.finalRounds.textContent = gameState.round;
  elements.finalLevel.textContent =
    LEVEL_CONFIG[gameState.level]?.label || gameState.level;

  elements.gameOverTitle.innerHTML =
    '<span class="title-icon">🚀</span> BoB ESCAPED! YOU WIN!';

  showScreen('gameOver');
}

// ==================== SPEEDRUN TIMER ====================
function handleSpeedrunTimer(data) {
  if (!gameState.isSpeedrun) return;

  gameState.speedrunTimeRemaining = data.time_remaining || 0;
  gameState.speedrunTimeLimit = data.time_limit || 60;
  updateSpeedrunTimer(data.time_remaining, data.time_limit);

  // Client-side safeguard: if time reaches 0, show game over
  if (data.time_remaining <= 0 && gameState.isPlaying) {
    handleGameOver({
      timeout: true,
      final_score: gameState.score,
      rounds: gameState.round,
      mode: 'speedrun',
    });
  }
}

function showSpeedrunTimer(show) {
  if (elements.timerBox) {
    elements.timerBox.style.display = show ? 'flex' : 'none';
  }
}

function updateSpeedrunTimer(timeRemaining, timeLimit) {
  if (!elements.timerValue || !elements.timerBar || !elements.timerBox) return;

  // Update timer value
  const seconds = Math.ceil(timeRemaining);
  elements.timerValue.textContent = seconds;

  // Update timer bar
  const percentage = (timeRemaining / timeLimit) * 100;
  elements.timerBar.style.width = `${percentage}%`;

  // Color coding based on time remaining
  if (timeRemaining <= 10) {
    elements.timerBox.classList.add('timer-critical');
    elements.timerBox.classList.remove('timer-warning');
  } else if (timeRemaining <= 20) {
    elements.timerBox.classList.add('timer-warning');
    elements.timerBox.classList.remove('timer-critical');
  } else {
    elements.timerBox.classList.remove('timer-warning', 'timer-critical');
  }
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
        ? 'Hub: Connected ✓'
        : 'Hub: Active';
    }
  } else {
    elements.masterDot?.classList.remove('connected');
    if (elements.masterStatus) {
      elements.masterStatus.textContent = 'Hub: Waiting...';
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

  // Update message based on game state
  if (gameState.currentScreen === 'game') {
    if (gameState.isPlaying && !gameState.masterConnected) {
      // Game in progress but master disconnected - show pause message
      setMessage('⏸️', 'Hub disconnected - waiting for reconnection...');
    } else if (
      gameState.isPlaying &&
      gameState.masterConnected &&
      connected > 0
    ) {
      // Game in progress and master reconnected - show resume message
      setMessage('▶️', 'Hub reconnected! Continue playing...');
    } else if (!gameState.isPlaying) {
      // Not playing - show connection status
      if (gameState.masterConnected && connected > 0) {
        setMessage(
          '🎮',
          `${connected}/${TOTAL_TILES} tiles online! Press START to begin!`,
        );
      } else if (!gameState.masterConnected) {
        setMessage('📡', 'Waiting for Hub to connect...');
      } else {
        setMessage('📡', 'Waiting for tiles to connect...');
      }
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
    tile.classList.remove(
      'pattern',
      'selected',
      'active',
      'correct',
      'wrong',
      'hide-number',
    );
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

  setMessage(
    '👽',
    `BoB shows ${pattern.length} tiles! Memorize the launch sequence! (${duration}s)`,
  );
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

      setMessage('🛸', `Signal ${index + 1}/${pattern.length}`);

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
    setMessage('�', `${remaining} more tile(s) to power up!`);
  } else if (remaining === 0) {
    setMessage('🚀', 'Ready for launch! Press CONFIRM!');
  } else {
    setMessage('⚠️', `Overload! Too many selected (${-remaining} extra)`);
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

  // Rebuild tile grid with mode-specific settings (e.g., hide numbers for classic)
  buildTileGrid();

  showScreen('game');
  setMessage('👽', 'BoB is ready! Press START to begin the rescue mission!');
}

function showError(msg) {
  if (elements.teamNameError) {
    elements.teamNameError.textContent = msg;
    elements.teamNameError.style.display = 'block';
  }
  if (elements.teamNameInput) {
    elements.teamNameInput.setAttribute('aria-invalid', 'true');
    elements.teamNameInput.style.borderColor = 'var(--neon-red)';
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

  // Reset speedrun state
  gameState.isSpeedrun = false;
  gameState.speedrunTimeRemaining = 0;
  gameState.speedrunTimeLimit = 0;
  showSpeedrunTimer(false);

  elements.stepsSection?.classList.remove('visible');
  clearTileStates();
}

function playAgain() {
  resetGameState();
  gameState.scoreSubmitted = false; // Reset so new score can be saved
  sendMessage({
    type: 'start_game',
    team_name: gameState.teamName,
    level: gameState.level,
    mode: gameState.mode,
  });

  // Rebuild tile grid with mode-specific settings
  buildTileGrid();

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
