// ============================================
// MEMORY XXL - GAME APPLICATION
// Dynamic Tiles based on connected ESP32 devices
// ============================================

// Game State
const gameState = {
  teamName: '',
  level: 'easy',
  mode: 'classic',
  score: 0,
  round: 0,
  pattern: [],
  playerSteps: [],
  connectedTiles: [],
  expectedTiles: 0,
  masterConnected: false,
  isPlaying: false,
  timeLeft: 0,
  timerInterval: null,
};

// Game Mode Configuration
const MODE_CONFIG = {
  classic: {
    name: 'Classic',
    description: 'Repeat the pattern shown',
    icon: '🧠',
    hasTimer: false,
    patternGrows: false,
  },
  speedrun: {
    name: 'Speed Run',
    description: 'Complete patterns before time runs out',
    icon: '⚡',
    hasTimer: true,
    timePerStep: 3, // seconds per step
    patternGrows: false,
  },
  endless: {
    name: 'Endless',
    description: 'Pattern grows each round until you fail',
    icon: '♾️',
    hasTimer: false,
    patternGrows: true,
    startSteps: 2,
  },
  simon: {
    name: 'Simon Says',
    description: 'Classic Simon Says style with colors',
    icon: '🎯',
    hasTimer: false,
    patternGrows: true,
    startSteps: 1,
  },
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
  elements.timerDisplay = document.getElementById('timerDisplay');
  elements.timerValue = document.getElementById('timerValue');
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
  // Mode selection
  elements.modeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      elements.modeBtns.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.mode = btn.dataset.mode;
      updateModeDescription();
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
  // Use wss:// for HTTPS, ws:// for HTTP
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/frontend`;

  console.log('🔌 Connecting to:', wsUrl);

  try {
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log('🔌 WebSocket connected!');
      reconnectAttempts = 0;
      updateConnectionStatus(true);
      // Backend sends initial_state automatically on connect
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

  // Handle both 'type' and 'event' formats from backend
  const msgType = message.type || message.event;
  const msgData = message.data || message;

  console.log('📩 Message type:', msgType, 'Data:', msgData);

  switch (msgType) {
    case 'initial_state':
    case 'state_update':
      // Initial connection or state update - update master status
      console.log(
        '✓ State received, master_connected:',
        msgData.master_connected
      );
      if (msgData.master_connected !== undefined) {
        gameState.masterConnected = msgData.master_connected;
        updateMasterStatus();
      }
      if (msgData.tiles) {
        const tileIds = Object.keys(msgData.tiles).map(Number);
        const connectedTiles = tileIds.filter(
          (id) => msgData.tiles[id]?.connected
        );
        updateTileStatus(connectedTiles, tileIds.length);
      }
      break;
    case 'status':
      handleStatusUpdate(msgData);
      break;
    case 'tile_status':
      // Handle different formats
      if (msgData.tiles) {
        const tileIds = Object.keys(msgData.tiles).map(Number);
        const connectedTiles = tileIds.filter(
          (id) => msgData.tiles[id]?.connected
        );
        updateTileStatus(connectedTiles, tileIds.length);
      } else {
        updateTileStatus(
          msgData.connected_tiles || message.connected_tiles,
          msgData.expected_tiles || message.expected_tiles
        );
      }
      break;
    case 'tile_connected':
      handleTileConnected(msgData.tile_id || message.tile_id);
      break;
    case 'tile_disconnected':
      handleTileDisconnected(msgData.tile_id || message.tile_id);
      break;
    case 'tile_activated':
      handleTileActivated(msgData.tile_id || message.tile_id);
      break;
    case 'show_pattern':
    case 'pattern_displayed':
      showPattern(msgData.pattern || message.pattern);
      break;
    case 'player_turn':
      startPlayerTurn(
        msgData.expected_count ||
          message.expected_count ||
          LEVEL_CONFIG[gameState.level].steps
      );
      break;
    case 'step_received':
      handleStepReceived(
        msgData.tile_id || message.tile_id,
        msgData.step_number || message.step_number,
        msgData.is_correct || message.is_correct
      );
      break;
    case 'round_complete':
      handleRoundComplete(
        msgData.round || message.round,
        msgData.score || message.score
      );
      break;
    case 'game_over':
      handleGameOver(
        msgData.final_score || message.final_score,
        msgData.rounds || message.rounds
      );
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
    case 'master_connected':
      gameState.masterConnected = true;
      updateMasterStatus();
      console.log('✓ Master connected');
      break;
    case 'master_disconnected':
      gameState.masterConnected = false;
      updateMasterStatus();
      console.log('✗ Master disconnected');
      break;
    case 'memorizing_phase':
      // Pattern is being shown - player should memorize
      setMessage('🧠', msgData.message || 'Memorize the pattern!');
      if (msgData.pattern) {
        showPattern(msgData.pattern);
      }
      break;
    case 'pattern_wrong':
      // Player made a mistake
      setMessage('❌', msgData.message || 'Wrong! Game Over!');
      handleGameOver(
        msgData.score || gameState.score,
        msgData.round || gameState.round
      );
      break;
    case 'game_ended':
      // Game has ended
      handleGameOver(
        msgData.score || gameState.score,
        msgData.rounds || gameState.round
      );
      break;
    case 'player_input_phase':
      // Player's turn to repeat the pattern
      startPlayerTurn(
        msgData.expected_count || LEVEL_CONFIG[gameState.level].steps
      );
      break;
    case 'tile_pressed':
    case 'player_stepped':
      // A tile was pressed by the player
      console.log('🎯 Tile pressed:', msgData.tile_id);
      handleTileActivated(msgData.tile_id || message.tile_id);
      // Update step count if available
      if (msgData.step_number) {
        setMessage(
          '👆',
          `Step ${msgData.step_number} - Tile ${msgData.tile_id}`
        );
      }
      break;
    default:
      // Reduce console spam - only log truly unknown types
      if (!['tile_status'].includes(msgType)) {
        console.log('Unknown message type:', msgType);
      }
  }
}

function handleStatusUpdate(data) {
  // Handle nested data format from backend
  const statusData = data.data || data;

  if (statusData.master_connected !== undefined) {
    gameState.masterConnected = statusData.master_connected;
    updateMasterStatus();
  }

  if (statusData.connected_tiles) {
    updateTileStatus(
      statusData.connected_tiles,
      statusData.expected_tiles || 0
    );
  }

  if (statusData.tiles) {
    const tileIds = Object.keys(statusData.tiles).map(Number);
    const connectedTiles = tileIds.filter(
      (id) => statusData.tiles[id]?.connected
    );
    updateTileStatus(connectedTiles, tileIds.length);
  }
}

function updateConnectionStatus(connected) {
  if (connected) {
    // WebSocket connected - waiting for hardware
    elements.masterStatus.textContent = 'Master: Waiting for hardware...';
    console.log('✓ WebSocket connected, waiting for master ESP32');
  } else {
    elements.masterDot.classList.remove('connected');
    elements.masterStatus.textContent = 'Server: Disconnected';
    elements.tilesDot.classList.remove('connected');
  }
}

function updateMasterStatus() {
  console.log('🔄 updateMasterStatus:', gameState.masterConnected);

  if (gameState.masterConnected) {
    elements.masterDot.classList.add('connected');
    elements.masterStatus.textContent = 'Master: Connected ✓';
    console.log('✅ Master status updated to CONNECTED');
  } else {
    elements.masterDot.classList.remove('connected');
    elements.masterStatus.textContent = 'Master: Waiting...';
    console.log('⏳ Master status updated to WAITING');
  }
}

// ============================================
// DYNAMIC TILE GRID
// ============================================

function updateTileStatus(connectedTiles, expectedTiles) {
  console.log('🎯 updateTileStatus called:', { connectedTiles, expectedTiles });

  gameState.connectedTiles = connectedTiles || [];
  gameState.expectedTiles = expectedTiles || gameState.connectedTiles.length;

  // Update status display
  const connected = gameState.connectedTiles.length;
  const expected = Math.max(gameState.expectedTiles, connected);

  console.log(`🎯 Tiles: ${connected}/${expected}`);
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

  // Update message based on status
  if (gameState.masterConnected && connected > 0) {
    setMessage(
      '🎮',
      `${connected} tiles ready! Press START on the master to begin!`
    );
  }
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
  console.log('🎯 handleTileActivated:', tileId);
  const tile = document.getElementById(`tile-${tileId}`);
  if (tile) {
    // Add visual feedback
    tile.classList.add('active');
    tile.classList.add('pressed');

    // Remove after animation
    setTimeout(() => {
      tile.classList.remove('active');
      tile.classList.remove('pressed');
    }, 500);
  } else {
    console.warn(`⚠️ Tile element not found: tile-${tileId}`);
    console.log('Available tiles:', gameState.connectedTiles);
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
  elements.currentLevel.textContent = LEVEL_CONFIG[
    gameState.level
  ].label.replace(' Mode', '');
  elements.currentMode.textContent = MODE_CONFIG[gameState.mode].name;
  updateGameStats();

  // Show/hide timer based on mode
  const modeConfig = MODE_CONFIG[gameState.mode];
  if (modeConfig.hasTimer && elements.timerDisplay) {
    elements.timerDisplay.style.display = 'flex';
  } else if (elements.timerDisplay) {
    elements.timerDisplay.style.display = 'none';
  }

  // Hide pattern sections initially
  elements.sequenceSection.classList.remove('visible');
  elements.stepsSection.classList.remove('visible');

  // Set initial message based on mode
  const modeMessage = getModeStartMessage();
  setMessage(modeConfig.icon, modeMessage);

  // Send game start to backend with mode
  sendMessage({
    type: 'start_game',
    team_name: teamName,
    level: gameState.level,
    mode: gameState.mode,
  });

  showScreen('game');
}

function getModeStartMessage() {
  if (!gameState.masterConnected) {
    return 'Waiting for Master ESP32 to connect...';
  }
  if (gameState.connectedTiles.length === 0) {
    return 'Waiting for tiles to connect...';
  }
  switch (gameState.mode) {
    case 'speedrun':
      return 'Speed Run! Complete patterns before time runs out!';
    case 'endless':
      return 'Endless Mode! Pattern grows each round!';
    case 'simon':
      return 'Simon Says! Watch and repeat the sequence!';
    default:
      return 'Ready! Press START on the master to begin!';
  }
}

function updateModeDescription() {
  // Visual feedback when mode changes
  const activeBtn = document.querySelector('.mode-btn.active');
  if (activeBtn) {
    activeBtn.style.transform = 'scale(1.02)';
    setTimeout(() => {
      activeBtn.style.transform = '';
    }, 200);
  }
}

function resetGame() {
  gameState.isPlaying = false;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.playerSteps = [];

  // Clear timer if running
  if (gameState.timerInterval) {
    clearInterval(gameState.timerInterval);
    gameState.timerInterval = null;
  }

  elements.sequenceSection.classList.remove('visible');
  elements.stepsSection.classList.remove('visible');
  elements.sequenceGrid.innerHTML = '';
  elements.stepsGrid.innerHTML = '';

  // Hide timer
  if (elements.timerDisplay) {
    elements.timerDisplay.style.display = 'none';
  }

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
    mode: gameState.mode,
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

  const modeConfig = MODE_CONFIG[gameState.mode];

  // Set message based on mode
  if (gameState.mode === 'speedrun') {
    const timeLimit = expectedCount * modeConfig.timePerStep;
    setMessage('⚡', `Quick! You have ${timeLimit} seconds!`);
    startTimer(timeLimit);
  } else if (gameState.mode === 'endless') {
    setMessage('♾️', `Round ${gameState.round + 1}: ${expectedCount} steps!`);
  } else if (gameState.mode === 'simon') {
    setMessage('🎯', `Simon says: repeat ${expectedCount} steps!`);
  } else {
    setMessage('👟', `Your turn! Repeat the pattern (${expectedCount} steps)`);
  }

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

// ============================================
// TIMER FUNCTIONS (Speed Run Mode)
// ============================================

function startTimer(seconds) {
  gameState.timeLeft = seconds;
  updateTimerDisplay();

  if (elements.timerDisplay) {
    elements.timerDisplay.style.display = 'flex';
    elements.timerDisplay.classList.remove('warning');
  }

  // Clear any existing timer
  if (gameState.timerInterval) {
    clearInterval(gameState.timerInterval);
  }

  gameState.timerInterval = setInterval(() => {
    gameState.timeLeft--;
    updateTimerDisplay();

    // Warning when time is low
    if (gameState.timeLeft <= 5 && elements.timerDisplay) {
      elements.timerDisplay.classList.add('warning');
    }

    if (gameState.timeLeft <= 0) {
      clearInterval(gameState.timerInterval);
      gameState.timerInterval = null;
      handleTimeOut();
    }
  }, 1000);
}

function stopTimer() {
  if (gameState.timerInterval) {
    clearInterval(gameState.timerInterval);
    gameState.timerInterval = null;
  }
  if (elements.timerDisplay) {
    elements.timerDisplay.classList.remove('warning');
  }
}

function updateTimerDisplay() {
  if (elements.timerValue) {
    elements.timerValue.textContent = gameState.timeLeft;
  }
}

function handleTimeOut() {
  setMessage('⏰', "Time's up! Game Over!");

  // Send timeout to backend
  sendMessage({
    type: 'timeout',
    team_name: gameState.teamName,
    score: gameState.score,
    round: gameState.round,
  });
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

  // Stop timer for speed run mode
  stopTimer();

  // Mode-specific completion message
  let message = `Round ${round} Complete! +${
    LEVEL_CONFIG[gameState.level].pointsPerRound
  } points!`;
  let icon = '🎉';

  if (gameState.mode === 'speedrun') {
    const bonus = Math.floor(gameState.timeLeft * 2);
    message = `Speed bonus: +${bonus}! Total: ${score} points!`;
    icon = '⚡';
  } else if (gameState.mode === 'endless') {
    message = `Endless Round ${round}! Pattern grows...`;
    icon = '♾️';
  } else if (gameState.mode === 'simon') {
    message = `Simon approves! Round ${round} complete!`;
    icon = '🎯';
  }

  setMessage(icon, message);

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

  // Stop timer if running
  stopTimer();

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
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    const data = await response.json();
    // Handle both array and object response formats
    const entries = Array.isArray(data)
      ? data
      : data.leaderboard || data.entries || [];
    renderLeaderboard(elements.leaderboardPreview, entries, true);
  } catch (error) {
    console.error('Failed to load leaderboard:', error.message);
    if (elements.leaderboardPreview) {
      elements.leaderboardPreview.innerHTML =
        '<p class="empty-leaderboard">Unable to load leaderboard</p>';
    }
  }
}

async function loadFullLeaderboard() {
  try {
    elements.leaderboardFull.innerHTML =
      '<div class="loading-spinner"><div class="spinner"></div><span>Loading...</span></div>';
    const response = await fetch('/api/leaderboard?limit=50');
    const data = await response.json();
    // Handle both array and object response formats
    const entries = Array.isArray(data)
      ? data
      : data.leaderboard || data.entries || [];
    renderLeaderboard(elements.leaderboardFull, entries, false);
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
