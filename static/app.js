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
  selectedTiles: new Set(), // Tiles currently selected by player (toggle mode)
  connectedTiles: [],
  // expectedTiles removed - always 16 tiles
  masterConnected: false,
  isPlaying: false,
  isSelectingPhase: false, // True during tile selection phase
  scoreSubmitted: false, // Prevent duplicate score submissions
  leaderboardFilter: 'all', // Current leaderboard level filter
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
// Scoring: correct = (round * level_multiplier * 10) + base_points
// Wrong = -15 penalty
const LEVEL_CONFIG = {
  easy: {
    steps: 1,
    levelMultiplier: 1,
    basePoints: 20,
    label: 'Easy Mode',
  },
  medium: {
    steps: 3,
    levelMultiplier: 2,
    basePoints: 30,
    label: 'Medium Mode',
  },
  hard: {
    steps: 5,
    levelMultiplier: 3,
    basePoints: 50,
    label: 'Hard Mode',
  },
};

const WRONG_PENALTY = 15;

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
  // Build 16-tile grid immediately (all offline until connected)
  buildTileGrid();
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
  elements.stepsSection = document.getElementById('stepsSection');
  elements.stepsGrid = document.getElementById('stepsGrid');

  // Leaderboard screen
  elements.leaderboardFull = document.getElementById('leaderboardFull');
  elements.backFromLeaderboardBtn = document.getElementById(
    'backFromLeaderboardBtn',
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
  // Mode selection - only allow classic mode, others are disabled
  elements.modeBtns.forEach((btn) => {
    btn.addEventListener('click', () => {
      // Skip if disabled (coming soon modes)
      if (btn.classList.contains('disabled') || btn.disabled) {
        return;
      }
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
    showScreen('leaderboard'),
  );
  elements.backToStartBtn.addEventListener('click', confirmExit);
  elements.backFromLeaderboardBtn.addEventListener('click', () =>
    showScreen('start'),
  );
  elements.playAgainBtn.addEventListener('click', playAgain);
  elements.backToMenuBtn.addEventListener('click', () => showScreen('start'));

  // Enter key for team name
  elements.teamNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') startGame();
  });

  // Leaderboard filter buttons
  document.querySelectorAll('.filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document
        .querySelectorAll('.filter-btn')
        .forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      gameState.leaderboardFilter = btn.dataset.level;
      loadFullLeaderboard();
    });
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
      }s (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`,
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
        msgData.master_connected,
      );
      if (msgData.master_connected !== undefined) {
        gameState.masterConnected = msgData.master_connected;
        updateMasterStatus();
      }
      // Handle tile status - prefer connected_tiles array, fallback to tiles object
      if (msgData.connected_tiles) {
        updateTileStatus(msgData.connected_tiles);
      } else if (msgData.tiles) {
        const tileIds = Object.keys(msgData.tiles).map(Number);
        const connectedTiles = tileIds.filter(
          (id) => msgData.tiles[id]?.connected,
        );
        updateTileStatus(connectedTiles);
      } else {
        // No tile data - assume no tiles connected
        updateTileStatus([]);
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
          (id) => msgData.tiles[id]?.connected,
        );
        updateTileStatus(connectedTiles);
      } else {
        updateTileStatus(msgData.connected_tiles || message.connected_tiles);
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
          LEVEL_CONFIG[gameState.level].steps,
      );
      break;
    case 'step_received':
      handleStepReceived(
        msgData.tile_id || message.tile_id,
        msgData.step_number || message.step_number,
        msgData.is_correct || message.is_correct,
      );
      break;
    case 'round_complete':
      handleRoundComplete(
        msgData.round || message.round,
        msgData.score || message.score,
      );
      break;
    case 'pattern_correct':
      // Pattern was correct - update score and prepare for next round
      gameState.score = msgData.score || message.score || gameState.score;
      gameState.round = msgData.round || message.round || gameState.round;
      gameState.isSelectingPhase = false;
      gameState.selectedTiles = new Set();
      updateGameStats();
      setMessage('🎉', msgData.message || 'Perfect!');
      // Clear tile states
      setTimeout(() => {
        document.querySelectorAll('.tile').forEach((tile) => {
          tile.classList.remove(
            'step',
            'pattern',
            'correct',
            'selected',
            'active',
          );
        });
        elements.stepsSection.classList.remove('visible');
        setMessage('🎮', 'Next round starting...');
      }, 2000);
      break;
    case 'game_over':
      // Single game over event - show message and handle game over
      setMessage('❌', msgData.message || 'Game Over!');
      handleGameOver(
        msgData.final_score ?? msgData.score ?? gameState.score,
        msgData.rounds ?? msgData.round ?? gameState.round,
      );
      break;
    case 'waiting_for_start':
      setMessage('🎮', 'Press the START button on the master to begin!');
      break;
    case 'game_started':
      gameState.isPlaying = true;
      gameState.round = msgData.round || gameState.round || 0;
      // Only reset score on first round (round 1)
      if (msgData.round === 1) {
        gameState.score = 0;
      }
      gameState.selectedTiles = new Set();
      gameState.isSelectingPhase = false;
      updateGameStats();

      // Show pattern on website (physical tiles stay off)
      if (msgData.pattern) {
        // Simon Says uses sequential display, others use simultaneous
        if (gameState.mode === 'simon') {
          setMessage('🎯', msgData.message || `Simon says: Watch carefully!`);
          showPattern(msgData.pattern);
        } else {
          setMessage('🧠', msgData.message || `Ronde ${msgData.round}`);
          showPatternSimultaneous(msgData.pattern);
        }
      } else {
        setMessage('🚀', msgData.message || 'Game Started! Get ready...');
      }
      break;
    case 'selecting_phase':
      // Enter tile selection phase - player can now toggle tiles
      gameState.isSelectingPhase = true;
      gameState.selectedTiles = new Set();
      setMessage('👆', msgData.message || 'Selecteer de juiste tegels!');
      startSelectingPhase(
        msgData.pattern_length || LEVEL_CONFIG[gameState.level].steps,
      );
      break;
    case 'tile_toggled':
      // A tile was toggled on/off
      handleTileToggled(
        msgData.tile_id,
        msgData.is_selected,
        msgData.selected_tiles || [],
        msgData.expected_count || 0,
      );
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
      // Legacy event - redirect to game_over handling
      console.log(
        'pattern_wrong received, but game_over should handle this now',
      );
      break;
    case 'game_ended':
      // Legacy event - redirect to game_over handling
      console.log('game_ended received, but game_over should handle this now');
      break;
    case 'player_input_phase':
      // Player's turn to repeat the pattern
      startPlayerTurn(
        msgData.expected_count || LEVEL_CONFIG[gameState.level].steps,
      );
      break;
    case 'tile_pressed':
    case 'player_stepped':
      // A tile was pressed by the player
      console.log('🎯 Tile pressed:', msgData.tile_id);
      handleTileActivated(msgData.tile_id || message.tile_id);
      // Update step count if available
      if (msgData.step_number !== undefined) {
        const stepNum = msgData.step_number;
        const tileId = msgData.tile_id || message.tile_id;
        const isCorrect = msgData.is_correct !== false; // Default to true if not specified

        // Update step boxes in the UI
        const stepBoxes = elements.stepsGrid.querySelectorAll('.step-box');
        if (stepBoxes[stepNum - 1]) {
          stepBoxes[stepNum - 1].classList.remove('waiting');
          stepBoxes[stepNum - 1].textContent = tileId;
          if (isCorrect) {
            stepBoxes[stepNum - 1].classList.add('correct');
          } else {
            stepBoxes[stepNum - 1].classList.add('wrong');
          }
        }

        // Highlight tile on grid
        const tile = document.getElementById(`tile-${tileId}`);
        if (tile) {
          if (isCorrect) {
            tile.classList.add('step', 'correct');
          } else {
            tile.classList.add('step', 'wrong');
          }
        }

        if (isCorrect) {
          setMessage('✅', `Step ${stepNum} correct!`);
        } else {
          setMessage('❌', `Wrong tile! Game Over!`);
        }
      }
      break;
    case 'info':
      // Info message from backend - display it
      setMessage('ℹ️', msgData.message || 'Info');
      break;
    case 'game_registered':
      // Game registration confirmed
      setMessage(
        '✅',
        msgData.message || 'Game registered! Press START to begin!',
      );
      break;
    case 'master_status':
      // Master connection status update
      console.log('🔌 Master status:', msgData.connected);
      gameState.masterConnected = msgData.connected;
      updateMasterStatus();
      break;
    case 'error':
      // Error message from backend
      console.log('❌ Error:', msgData.message);
      setMessage('❌', msgData.message || 'An error occurred');
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
    updateTileStatus(statusData.connected_tiles);
  }

  if (statusData.tiles) {
    const tileIds = Object.keys(statusData.tiles).map(Number);
    const connectedTiles = tileIds.filter(
      (id) => statusData.tiles[id]?.connected,
    );
    updateTileStatus(connectedTiles);
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

function updateTileStatus(connectedTiles) {
  console.log('🎯 updateTileStatus called:', { connectedTiles });

  gameState.connectedTiles = connectedTiles || [];
  const TOTAL_TILES = 12; // Always expect 12 tiles

  // Update status display - show connected out of 12
  const connected = gameState.connectedTiles.length;

  console.log(`🎯 Tiles: ${connected}/${TOTAL_TILES}`);
  elements.tilesStatus.textContent = `Tiles: ${connected}/${TOTAL_TILES}`;

  if (connected > 0 && connected >= TOTAL_TILES) {
    elements.tilesDot.classList.add('connected');
  } else if (connected > 0) {
    // Partial connection - show yellow/warning state
    elements.tilesDot.classList.add('connected');
  } else {
    elements.tilesDot.classList.remove('connected');
  }

  // Rebuild the tile grid dynamically
  buildTileGrid();

  // Update message based on status
  if (gameState.masterConnected && connected > 0) {
    setMessage(
      '🎮',
      `${connected}/${TOTAL_TILES} tiles online! Press START on the master to begin!`,
    );
  }
}

function buildTileGrid() {
  const grid = elements.tileGrid;
  const TOTAL_TILES = 12; // Always show 12 tiles
  const connectedSet = new Set(gameState.connectedTiles);

  // Create array of all 12 tile IDs (1-12)
  const allTiles = Array.from({ length: TOTAL_TILES }, (_, i) => i + 1);

  // Check if tile list display needs update
  const existingTileIds = Array.from(grid.querySelectorAll('.tile'))
    .map((t) => parseInt(t.dataset.tileId))
    .sort((a, b) => a - b);

  const needsRebuild =
    existingTileIds.length !== TOTAL_TILES ||
    JSON.stringify(allTiles) !== JSON.stringify(existingTileIds);

  if (needsRebuild) {
    // Save current selected state
    const currentlySelected = new Set(gameState.selectedTiles);

    // Create all 12 tile elements - mark offline tiles differently
    grid.innerHTML = allTiles
      .map((tileId) => {
        const isConnected = connectedSet.has(tileId);
        const isSelected = currentlySelected.has(tileId);

        let classes = 'tile';
        if (!isConnected) classes += ' offline';
        if (isSelected && isConnected) classes += ' selected active';

        return `
          <div class="${classes}" data-tile-id="${tileId}" id="tile-${tileId}">
              <span class="tile-number">${tileId}</span>
              ${
                !isConnected
                  ? '<span class="tile-offline-label">offline</span>'
                  : ''
              }
          </div>
        `;
      })
      .join('');

    // Fixed 3x4 grid for 12 tiles
    grid.style.gridTemplateColumns = 'repeat(4, minmax(80px, 1fr))';
  } else {
    // Just update the connected/offline status without full rebuild
    allTiles.forEach((tileId) => {
      const tile = document.getElementById(`tile-${tileId}`);
      if (tile) {
        const isConnected = connectedSet.has(tileId);
        if (isConnected) {
          tile.classList.remove('offline');
          // Remove offline label if exists
          const label = tile.querySelector('.tile-offline-label');
          if (label) label.remove();
        } else {
          tile.classList.add('offline');
          // Add offline label if not exists
          if (!tile.querySelector('.tile-offline-label')) {
            const label = document.createElement('span');
            label.className = 'tile-offline-label';
            label.textContent = 'offline';
            tile.appendChild(label);
          }
        }
      }
    });
  }
}

function handleTileConnected(tileId) {
  if (!gameState.connectedTiles.includes(tileId)) {
    gameState.connectedTiles.push(tileId);
    updateTileStatus(gameState.connectedTiles);
  }
}

function handleTileDisconnected(tileId) {
  const index = gameState.connectedTiles.indexOf(tileId);
  if (index > -1) {
    gameState.connectedTiles.splice(index, 1);
    updateTileStatus(gameState.connectedTiles);
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

async function startGame() {
  const teamName = elements.teamNameInput.value.trim();
  const errorElement = document.getElementById('teamNameError');

  // Hide previous error
  if (errorElement) {
    errorElement.style.display = 'none';
  }

  if (!teamName || teamName.length < 2) {
    elements.teamNameInput.focus();
    elements.teamNameInput.style.borderColor = 'var(--neon-red)';
    if (errorElement) {
      errorElement.textContent = 'Please enter a team name (min. 2 characters)';
      errorElement.style.display = 'block';
    }
    setTimeout(() => {
      elements.teamNameInput.style.borderColor = '';
    }, 2000);
    return;
  }

  // Check if team name already exists
  try {
    console.log('Checking if team name exists:', teamName);
    const response = await fetch(
      `/api/leaderboard/check-name?name=${encodeURIComponent(teamName)}`,
    );
    const data = await response.json();
    console.log('Team name check result:', data);

    if (data.exists) {
      elements.teamNameInput.focus();
      elements.teamNameInput.style.borderColor = 'var(--neon-red)';
      if (errorElement) {
        errorElement.textContent =
          'This team name is already taken! Choose a different name.';
        errorElement.style.display = 'block';
      }
      setTimeout(() => {
        elements.teamNameInput.style.borderColor = '';
      }, 3000);
      return;
    }
  } catch (error) {
    console.error('Error checking team name:', error);
    // Continue anyway if check fails
  }

  gameState.teamName = teamName;
  gameState.score = 0;
  gameState.round = 0;
  gameState.pattern = [];
  gameState.playerSteps = [];
  gameState.scoreSubmitted = false;

  // Update UI
  elements.currentTeamName.textContent = teamName;
  elements.currentLevel.textContent = LEVEL_CONFIG[
    gameState.level
  ].label.replace(' Mode', '');
  elements.currentMode.textContent = MODE_CONFIG[gameState.mode].name;
  updateGameStats();

  // Hide steps section initially
  elements.stepsSection.classList.remove('visible');

  // Set initial message based on mode
  const modeMessage = getModeStartMessage();
  setMessage(MODE_CONFIG[gameState.mode].icon, modeMessage);

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
  gameState.selectedTiles = new Set();
  gameState.isSelectingPhase = false;

  elements.stepsSection.classList.remove('visible');
  elements.stepsGrid.innerHTML = '';

  // Clear tile states
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove(
      'active',
      'pattern',
      'step',
      'correct',
      'wrong',
      'selected',
    );
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
// PATTERN DISPLAY (internal - no UI display)
// ============================================

function showPattern(pattern) {
  gameState.pattern = pattern;
  gameState.selectedTiles = new Set();
  gameState.isSelectingPhase = false;

  // Pattern display on website
  elements.stepsSection.classList.remove('visible');

  // Clear previous tile highlights
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove(
      'pattern',
      'step',
      'correct',
      'wrong',
      'selected',
      'active',
    );
  });

  // Animate pattern display on website tiles sequentially
  console.log('🎯 Displaying pattern sequentially:', pattern);
  let delay = 0;
  pattern.forEach((tileId, index) => {
    setTimeout(() => {
      // Highlight tile on grid
      const tile = document.getElementById(`tile-${tileId}`);
      if (tile) {
        tile.classList.add('pattern', 'active');
        setTimeout(() => {
          tile.classList.remove('pattern', 'active');
        }, 600);
      }
    }, delay);
    delay += 800;
  });
}

// ============================================
// SIMULTANEOUS PATTERN DISPLAY (8 seconds)
// ============================================

function showPatternSimultaneous(pattern) {
  gameState.pattern = pattern;
  gameState.selectedTiles = new Set();
  gameState.isSelectingPhase = false;

  // Display pattern on both physical tiles AND website
  elements.stepsSection.classList.remove('visible');

  // Clear previous tile highlights
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove(
      'pattern',
      'step',
      'correct',
      'wrong',
      'selected',
      'active',
    );
  });

  // Highlight pattern tiles on website grid - keep visible for memorization
  console.log('🎯 Displaying pattern on website:', pattern);
  pattern.forEach((tileId) => {
    const tile = document.getElementById(`tile-${tileId}`);
    if (tile) {
      tile.classList.add('pattern', 'active');
      console.log(`✓ Tile ${tileId} highlighted on website`);
    } else {
      console.warn(`⚠️ Tile ${tileId} not found in DOM`);
    }
  });

  // Update message to show memorization instruction
  setMessage('🧠', `Memoreer deze ${pattern.length} tegels! (8 seconden)`);

  // Pattern stays visible until selecting_phase event (handled by backend after 8 seconds)
}

// ============================================
// SELECTING PHASE - Toggle tiles on/off
// ============================================

function startSelectingPhase(expectedCount) {
  gameState.playerSteps = [];
  gameState.selectedTiles = new Set();
  gameState.isSelectingPhase = true;

  // Show steps section with selection info
  elements.stepsSection.classList.add('visible');

  // Clear pattern highlights - pattern is now hidden
  document.querySelectorAll('.tile').forEach((tile) => {
    tile.classList.remove('pattern');
  });

  // Update steps grid with selection counter and instruction
  elements.stepsGrid.innerHTML = `
    <div class="selection-counter">
      <span id="selected-count">0</span> / <span id="expected-count">${expectedCount}</span>
    </div>
    <div class="selection-instruction">
      <p>Selecteer ${expectedCount} tegels</p>
      <p class="hint">Stap op een tegel om te selecteren/deselecteren</p>
      <p class="hint">Druk op CONFIRM als je klaar bent</p>
    </div>
  `;
}

// ============================================
// TILE TOGGLE HANDLING - Tile Authority Model
// ============================================
// The physical tile is the source of truth:
// 1. Tile toggles its LED instantly when stepped on (no delay)
// 2. Tile remembers its state (ON/OFF)
// 3. Tile sends its state to website - we just mirror it
// ============================================

function handleTileToggled(tileId, isSelected, selectedTiles, expectedCount) {
  console.log('🔄 Tile', tileId, 'reports:', isSelected ? 'ON (green)' : 'OFF');

  // Mirror the tile's state - tile is authoritative
  if (isSelected) {
    gameState.selectedTiles.add(tileId);
  } else {
    gameState.selectedTiles.delete(tileId);
  }

  // Update tile visual to match physical tile
  const tile = document.getElementById(`tile-${tileId}`);
  if (tile) {
    if (isSelected) {
      // Tile LED is ON (green) - show as selected
      tile.classList.add('selected', 'active');
      tile.classList.remove('off');
    } else {
      // Tile LED is OFF - show as deselected
      tile.classList.remove('selected', 'active');
      tile.classList.add('off');
      // Remove 'off' class after brief moment
      setTimeout(() => tile.classList.remove('off'), 200);
    }
  }

  // Update selection counter
  const selectedCountEl = document.getElementById('selected-count');
  if (selectedCountEl) {
    selectedCountEl.textContent = selectedTiles.length;
  }

  // Update message
  const remaining = expectedCount - selectedTiles.length;
  if (remaining > 0) {
    setMessage('👆', `Nog ${remaining} tegels selecteren`);
  } else if (remaining === 0) {
    setMessage('✅', 'Druk op CONFIRM om te bevestigen!');
  } else {
    setMessage('⚠️', `Te veel tegels geselecteerd (${-remaining} extra)`);
  }
}

// ============================================
// PLAYER TURN
// ============================================

function startPlayerTurn(expectedCount) {
  gameState.playerSteps = [];

  const modeConfig = MODE_CONFIG[gameState.mode];

  // Set message based on mode
  if (gameState.mode === 'speedrun') {
    setMessage('⚡', 'Quick! Complete the pattern!');
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
    '',
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

  // Score is now submitted from backend only - no duplicate submissions
  gameState.scoreSubmitted = true;

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
    const filter = gameState.leaderboardFilter || 'all';
    const filterParam = filter !== 'all' ? `&level=${filter}` : '';
    const response = await fetch(`/api/leaderboard?limit=50${filterParam}`);
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

  // Keep only the best score per team name
  const bestScores = {};
  entries.forEach((entry) => {
    const teamName = entry.team_name.toLowerCase();
    if (!bestScores[teamName] || entry.score > bestScores[teamName].score) {
      bestScores[teamName] = entry;
    }
  });

  // Convert back to array and sort by score descending
  const uniqueEntries = Object.values(bestScores).sort(
    (a, b) => b.score - a.score,
  );

  container.innerHTML = uniqueEntries
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
                      entry.team_name,
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
