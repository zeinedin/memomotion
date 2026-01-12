// === CONFIG ===
const wsUrl = "wss://memo-motion.azurewebsites.net/ws/frontend"; 
let ws = new WebSocket(wsUrl);
let currentLevel = "Normal";

// === NAVIGATIE ===
function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function selectLevel(lvl, btn) {
    currentLevel = lvl;
    document.querySelectorAll('.lvl-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
}

// === API CALLS ===
async function registerTeam() {
    const name = document.getElementById('teamName').value;
    if(!name) return alert("Enter a name!");

    // Stuur naar Backend API
    await fetch('/api/register', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ team_name: name, level: currentLevel })
    });

    document.getElementById('displayTeam').innerText = name;
    showScreen('screen-game');
    
    // Start het spel via WebSocket
    ws.send(JSON.stringify({ event: "start_game" }));
}

async function loadLeaderboard() {
    const res = await fetch('/api/leaderboard');
    const data = await res.json();
    
    const tbody = document.querySelector('#lbTable tbody');
    tbody.innerHTML = "";
    
    data.forEach(row => {
        tbody.innerHTML += `<tr><td>${row.rank}</td><td>${row.name}</td><td>${row.score}</td></tr>`;
    });
    showScreen('screen-leaderboard');
}

// === WEBSOCKET GAME LOGIC ===
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    const data = msg.data;

    if (msg.event === 'game_started') {
        const grid = document.getElementById('gameGrid');
        grid.innerHTML = "";
        
        // Maak tegels (Visueel)
        data.pattern.forEach((id, index) => {
            const tile = document.createElement('div');
            tile.className = 'tile';
            tile.dataset.id = id; // Wel ID opslaan voor logica, maar niet tonen
            
            // Animatie
            setTimeout(() => {
                tile.classList.add('highlight');
            }, index * 500); 

            grid.appendChild(tile);
        });
        document.getElementById('gameMessage').innerText = data.message;
    }

    if (msg.event === 'memorizing_phase') {
        document.getElementById('gameMessage').innerText = data.message;
        // Verwijder highlights
        document.querySelectorAll('.tile').forEach(t => t.classList.remove('highlight'));
    }

    if (msg.event === 'player_stepped') {
        // Vind de visuele tegel die overeenkomt met de stap
        // Dit is simpel; in het echt moet je weten welke tegel bij welk ID hoort.
        // Voor nu kleuren we de laatst toegevoegde div (simulatie)
        // OF we maken vaste tegels. Voor demo is dit OK.
    }

    if (msg.event === 'game_ended') {
        document.getElementById('gameMessage').innerText = data.message;
        setTimeout(() => {
            if(data.won) loadLeaderboard(); // Ga naar leaderboard bij winst
            else showScreen('screen-start');
        }, 3000);
    }
};