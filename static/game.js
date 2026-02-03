// BerryPoker Game Client

class PokerGame {
    constructor() {
        this.ws = null;
        this.roomId = null;
        this.playerName = null;
        this.gameState = null;
        this.raiseMin = 0;
        this.raiseMax = 0;
        this.isSeated = false;
        this.buyInAmount = 100;
        this.isSpectating = false;  // Watching but not seated

        // Track hands and actions
        this.handHistory = {};  // handNumber -> {actions: [], result: {}}
        this.currentHandNumber = 0;
        this.playerStats = {};  // playerName -> {buyIn, currentStack, profit, isActive}
        this.leftPlayerStats = {};  // Keep stats for players who left

        this.initElements();
        this.initEventListeners();
        this.checkSessionReconnect();
    }

    initElements() {
        // Landing page elements
        this.landingPage = document.getElementById('landing-page');
        this.gamePage = document.getElementById('game-page');
        this.playerNameInput = document.getElementById('player-name');
        this.buyInInput = document.getElementById('buy-in');
        this.createRoomBtn = document.getElementById('create-room-btn');
        this.joinRoomBtn = document.getElementById('join-room-btn');
        this.roomIdInput = document.getElementById('room-id-input');
        this.smallBlindInput = document.getElementById('small-blind');
        this.bigBlindInput = document.getElementById('big-blind');
        this.minBuyInInput = document.getElementById('min-buy-in');
        this.maxBuyInInput = document.getElementById('max-buy-in');

        // Game page elements
        this.displayRoomId = document.getElementById('display-room-id');
        this.displayBlinds = document.getElementById('display-blinds');
        this.copyRoomIdBtn = document.getElementById('copy-room-id');
        this.leaveRoomBtn = document.getElementById('leave-room-btn');
        this.potAmount = document.getElementById('pot-amount');
        this.communityCards = document.getElementById('community-cards');
        this.myCards = document.getElementById('my-cards');
        this.currentActions = document.getElementById('current-actions');

        // Action buttons
        this.foldBtn = document.getElementById('fold-btn');
        this.checkBtn = document.getElementById('check-btn');
        this.callBtn = document.getElementById('call-btn');
        this.raiseBtn = document.getElementById('raise-btn');
        this.allinBtn = document.getElementById('allin-btn');
        this.raiseControls = document.getElementById('raise-controls');
        this.raiseSlider = document.getElementById('raise-slider');
        this.raiseInput = document.getElementById('raise-input');
        this.confirmRaiseBtn = document.getElementById('confirm-raise-btn');

        // Run it twice
        this.runTwicePanel = document.getElementById('run-twice-panel');
        this.runOnceBtn = document.getElementById('run-once-btn');
        this.runTwiceBtn = document.getElementById('run-twice-btn');

        // Game controls
        this.startGameBtn = document.getElementById('start-game-btn');
        this.sitOutBtn = document.getElementById('sit-out-btn');

        // Side panel
        this.actionLog = document.getElementById('action-log');
        this.handSelect = document.getElementById('hand-select');
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendChatBtn = document.getElementById('send-chat-btn');
        this.statsContent = document.getElementById('stats-content');

        // Modal
        this.resultModal = document.getElementById('result-modal');
        this.resultTitle = document.getElementById('result-title');
        this.resultBody = document.getElementById('result-body');
        this.closeResultBtn = document.getElementById('close-result-btn');

        // Tabs
        this.tabBtns = document.querySelectorAll('.tab-btn');
    }

    initEventListeners() {
        // Landing page
        this.createRoomBtn.addEventListener('click', () => this.createRoom());
        this.joinRoomBtn.addEventListener('click', () => this.joinRoom());
        this.playerNameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.joinRoom();
        });
        this.roomIdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.joinRoom();
        });

        // Game page
        this.copyRoomIdBtn.addEventListener('click', () => this.copyRoomId());
        this.leaveRoomBtn.addEventListener('click', () => this.leaveRoom());

        // Rejoin button (if exists)
        const rejoinBtn = document.getElementById('rejoin-btn');
        if (rejoinBtn) {
            rejoinBtn.addEventListener('click', () => this.rejoinGame());
        }

        // Actions
        this.foldBtn.addEventListener('click', () => this.sendAction('fold'));
        this.checkBtn.addEventListener('click', () => this.sendAction('check'));
        this.callBtn.addEventListener('click', () => this.sendAction('call'));
        this.raiseBtn.addEventListener('click', () => this.toggleRaiseControls());
        this.allinBtn.addEventListener('click', () => this.sendAction('all_in'));
        this.confirmRaiseBtn.addEventListener('click', () => this.confirmRaise());
        this.raiseSlider.addEventListener('input', () => this.updateRaiseInput());
        this.raiseInput.addEventListener('change', () => this.updateRaiseSlider());

        // Run it twice
        if (this.runOnceBtn) {
            this.runOnceBtn.addEventListener('click', () => this.sendRunChoice(false));
        }
        if (this.runTwiceBtn) {
            this.runTwiceBtn.addEventListener('click', () => this.sendRunChoice(true));
        }

        // Game controls
        this.startGameBtn.addEventListener('click', () => this.startGame());
        this.sitOutBtn.addEventListener('click', () => this.toggleSitOut());

        // Hand selector
        this.handSelect.addEventListener('change', () => this.displayHandHistory());

        // Chat
        this.sendChatBtn.addEventListener('click', () => this.sendChat());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendChat();
        });

        // Modal
        this.closeResultBtn.addEventListener('click', () => this.closeResultModal());

        // Tabs
        this.tabBtns.forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });
    }

    checkSessionReconnect() {
        // Check if we have a saved session to reconnect to
        const savedRoom = sessionStorage.getItem('berrypoker_room');
        const savedName = sessionStorage.getItem('berrypoker_name');
        const savedBuyIn = sessionStorage.getItem('berrypoker_buyin');
        const savedStats = sessionStorage.getItem('berrypoker_stats');

        if (savedRoom && savedName) {
            this.roomId = savedRoom;
            this.playerName = savedName;
            this.buyInAmount = parseInt(savedBuyIn) || 100;

            // Restore player stats
            if (savedStats) {
                try {
                    this.playerStats = JSON.parse(savedStats);
                } catch (e) {}
            }

            // Auto-reconnect
            this.connectWebSocket(true);
        }
    }

    saveSession() {
        // Save session data for page refresh
        if (this.roomId && this.playerName) {
            sessionStorage.setItem('berrypoker_room', this.roomId);
            sessionStorage.setItem('berrypoker_name', this.playerName);
            sessionStorage.setItem('berrypoker_buyin', this.buyInAmount.toString());
            sessionStorage.setItem('berrypoker_stats', JSON.stringify(this.playerStats));
        }
    }

    clearSession() {
        sessionStorage.removeItem('berrypoker_room');
        sessionStorage.removeItem('berrypoker_name');
        sessionStorage.removeItem('berrypoker_buyin');
        sessionStorage.removeItem('berrypoker_stats');
    }

    async createRoom() {
        const name = this.playerNameInput.value.trim();
        if (!name) {
            this.showToast('Please enter your name', 'error');
            return;
        }

        const settings = {
            small_blind: parseInt(this.smallBlindInput.value) || 1,
            big_blind: parseInt(this.bigBlindInput.value) || 2,
            min_buy_in: parseInt(this.minBuyInInput.value) || 40,
            max_buy_in: parseInt(this.maxBuyInInput.value) || 200
        };

        try {
            const response = await fetch('/api/rooms', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings })
            });
            const data = await response.json();
            this.roomId = data.room_id;
            this.playerName = name;
            this.connectWebSocket();
        } catch (error) {
            this.showToast('Failed to create room', 'error');
        }
    }

    joinRoom() {
        const name = this.playerNameInput.value.trim();
        const roomId = this.roomIdInput.value.trim();

        if (!name) {
            this.showToast('Please enter your name', 'error');
            return;
        }
        if (!roomId) {
            this.showToast('Please enter room ID', 'error');
            return;
        }

        this.roomId = roomId;
        this.playerName = name;
        this.connectWebSocket();
    }

    connectWebSocket(isReconnect = false) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/${this.roomId}`);

        if (!isReconnect) {
            this.buyInAmount = parseInt(this.buyInInput.value) || 100;
        }

        this.ws.onopen = () => {
            this.ws.send(JSON.stringify({
                type: 'spectate',
                data: { player_name: this.playerName }
            }));
            this.saveSession();
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };

        this.ws.onclose = () => {
            if (!this.isSpectating) {
                this.showToast('Connection closed', 'error');
            }
        };

        this.ws.onerror = () => {
            this.showToast('Connection error', 'error');
            // If reconnect failed, go back to landing
            if (isReconnect) {
                this.clearSession();
            }
        };
    }

    selectSeat(seat) {
        if (this.isSeated) {
            this.showToast('You are already seated', 'error');
            return;
        }

        // If rejoining, ask for buy-in amount
        let buyIn = this.buyInAmount;
        if (this.leftPlayerStats[this.playerName]) {
            const input = prompt('Enter buy-in amount:', this.buyInAmount);
            if (input === null) return;  // Cancelled
            buyIn = parseInt(input) || this.buyInAmount;
        }

        this.buyInAmount = buyIn;
        this.ws.send(JSON.stringify({
            type: 'join',
            data: {
                player_name: this.playerName,
                stack: buyIn,
                seat: seat
            }
        }));
    }

    handleMessage(message) {
        switch (message.type) {
            case 'spectating':
                this.isSeated = false;
                this.isSpectating = true;
                this.showGamePage();
                this.updateSpectatorUI();
                if (!this.leftPlayerStats[this.playerName]) {
                    this.showToast('Click an empty seat to sit down', 'info');
                }
                break;

            case 'joined':
                this.isSeated = true;
                this.isSpectating = false;
                this.showGamePage();
                this.showToast(`Seated at position ${message.data.seat + 1}`, 'success');
                // Initialize player stats with buy-in (or restore from left stats)
                if (this.leftPlayerStats[this.playerName]) {
                    // Player rejoining - use previous buy-in for tracking
                    const prev = this.leftPlayerStats[this.playerName];
                    this.playerStats[this.playerName] = {
                        buyIn: prev.buyIn + this.buyInAmount,  // Add new buy-in to total
                        currentStack: this.buyInAmount,
                        profit: 0,
                        isActive: true
                    };
                    delete this.leftPlayerStats[this.playerName];
                } else {
                    this.playerStats[this.playerName] = {
                        buyIn: this.buyInAmount,
                        currentStack: this.buyInAmount,
                        profit: 0,
                        isActive: true
                    };
                }
                this.saveSession();
                this.updateSpectatorUI();
                break;

            case 'error':
                this.showToast(message.data.message, 'error');
                break;

            case 'game_state':
                this.updateGameState(message.data);
                break;

            case 'player_joined':
                this.showToast(`${message.data.player_name} joined the game`, 'info');
                this.addActionToCurrentHand(`${message.data.player_name} joined`, 'info');
                break;

            case 'player_left':
                this.showToast(`${message.data.player_name} left the game`, 'info');
                this.addActionToCurrentHand(`${message.data.player_name} left`, 'info');
                break;

            case 'player_disconnected':
                this.showToast(`${message.data.player_name} disconnected`, 'info');
                break;

            case 'hand_started':
                this.currentHandNumber = message.data.hand_number;
                this.handHistory[this.currentHandNumber] = { actions: [], result: null };
                this.updateHandSelector();
                this.addActionToCurrentHand(`=== Hand #${message.data.hand_number} started ===`, 'info');
                break;

            case 'player_action':
                this.handlePlayerAction(message.data);
                break;

            case 'hand_ended':
                this.showHandResult(message.data);
                break;

            case 'run_twice_prompt':
                this.showRunTwicePrompt();
                break;

            case 'chat':
                this.addChatMessage(message.data.player_name, message.data.message);
                break;
        }
    }

    showGamePage() {
        this.landingPage.classList.add('hidden');
        this.gamePage.classList.remove('hidden');
        this.displayRoomId.textContent = this.roomId;
        this.updateSpectatorUI();
    }

    updateGameState(state) {
        this.gameState = state;

        // Update blinds display
        this.displayBlinds.textContent = `${state.small_blind}/${state.big_blind}`;

        // Update pot
        this.potAmount.textContent = state.pot;

        // Update community cards
        this.renderCommunityCards(state.community_cards);

        // Update seats
        this.renderSeats(state.players, state.dealer_seat, state.current_player_seat);

        // Update my cards
        this.renderMyCards(state.players);

        // Update action buttons
        this.updateActionButtons(state.valid_actions);

        // Update game controls visibility
        this.updateGameControls(state.phase);

        // Update stats
        this.updateStats(state.players);

        // Update current hand actions display
        this.updateCurrentActionsDisplay();

        // Track hand number
        if (state.hand_number && state.hand_number !== this.currentHandNumber) {
            this.currentHandNumber = state.hand_number;
        }
    }

    renderCommunityCards(cards) {
        this.communityCards.innerHTML = '';
        cards.forEach(card => {
            this.communityCards.appendChild(this.createCardElement(card));
        });
    }

    renderSeats(players, dealerSeat, currentPlayerSeat) {
        const occupiedSeats = new Set(players.map(p => p.seat));
        const canSelectSeat = !this.isSeated && this.isSpectating;

        for (let i = 0; i < 9; i++) {
            const seatEl = document.querySelector(`.seat-${i}`);
            seatEl.innerHTML = '';
            seatEl.className = `seat seat-${i}`;
            seatEl.onclick = null;

            if (!occupiedSeats.has(i)) {
                seatEl.classList.add('empty');

                if (canSelectSeat) {
                    seatEl.classList.add('available');
                    seatEl.innerHTML = `
                        <div class="seat-number">Seat ${i + 1}</div>
                        <div class="sit-here">Click to sit</div>
                    `;
                    seatEl.onclick = () => this.selectSeat(i);
                } else {
                    seatEl.innerHTML = `<div class="seat-number">Seat ${i + 1}</div>`;
                }
            }
        }

        players.forEach(player => {
            const seatEl = document.querySelector(`.seat-${player.seat}`);
            seatEl.classList.remove('empty', 'available');
            seatEl.onclick = null;

            if (player.is_folded) seatEl.classList.add('folded');
            if (player.seat === currentPlayerSeat) seatEl.classList.add('active');

            let cardsHtml = '';
            if (player.hole_cards && player.hole_cards.length > 0) {
                cardsHtml = `<div class="player-cards">
                    ${player.hole_cards.map(c => this.createCardElement(c, true).outerHTML).join('')}
                </div>`;
            } else if (player.has_cards && !player.is_folded) {
                cardsHtml = `<div class="player-cards">
                    <div class="card small back"></div>
                    <div class="card small back"></div>
                </div>`;
            }

            let statusHtml = '';
            if (player.is_folded) statusHtml = '<div class="player-status">Folded</div>';
            else if (player.is_all_in) statusHtml = '<div class="player-status">All In</div>';
            else if (player.is_sitting_out) statusHtml = '<div class="player-status">Sitting Out</div>';

            let positionHtml = '';
            if (player.position) {
                positionHtml = `<div class="player-position" data-pos="${player.position}">${player.position}</div>`;
            }

            seatEl.innerHTML = `
                ${positionHtml}
                <div class="player-name">${this.escapeHtml(player.name)}</div>
                <div class="player-stack">${player.stack}</div>
                ${player.current_bet > 0 ? `<div class="player-bet">Bet: ${player.current_bet}</div>` : ''}
                ${cardsHtml}
                ${statusHtml}
            `;

            // Update player stats
            if (!this.playerStats[player.name]) {
                this.playerStats[player.name] = {
                    buyIn: player.stack,
                    currentStack: player.stack,
                    profit: 0
                };
            } else {
                this.playerStats[player.name].currentStack = player.stack;
                this.playerStats[player.name].profit = player.stack - this.playerStats[player.name].buyIn;
            }
        });

        // Position dealer button
        if (dealerSeat !== null) {
            const dealerBtn = document.getElementById('dealer-button');
            dealerBtn.classList.remove('hidden');
            const seatEl = document.querySelector(`.seat-${dealerSeat}`);
            if (seatEl) {
                const rect = seatEl.getBoundingClientRect();
                const tableRect = document.querySelector('.poker-table').getBoundingClientRect();
                dealerBtn.style.left = `${rect.left - tableRect.left + rect.width / 2 + 50}px`;
                dealerBtn.style.top = `${rect.top - tableRect.top + rect.height / 2}px`;
            }
        }
    }

    renderMyCards(players) {
        this.myCards.innerHTML = '';
        const myPlayer = players.find(p => p.name === this.playerName);
        if (myPlayer && myPlayer.hole_cards) {
            myPlayer.hole_cards.forEach(card => {
                this.myCards.appendChild(this.createCardElement(card));
            });
        }
    }

    createCardElement(card, small = false) {
        const el = document.createElement('div');
        el.className = `card ${card.suit}${small ? ' small' : ''}`;

        const suitSymbols = {
            'hearts': '♥',
            'diamonds': '♦',
            'clubs': '♣',
            'spades': '♠'
        };

        el.innerHTML = `
            <span class="rank">${card.rank}</span>
            <span class="suit">${suitSymbols[card.suit]}</span>
        `;
        return el;
    }

    updateActionButtons(validActions) {
        this.foldBtn.disabled = true;
        this.checkBtn.disabled = true;
        this.callBtn.disabled = true;
        this.raiseBtn.disabled = true;
        this.allinBtn.disabled = true;
        this.raiseControls.classList.add('hidden');

        if (!validActions || validActions.length === 0) return;

        validActions.forEach(action => {
            switch (action.action) {
                case 'fold':
                    this.foldBtn.disabled = false;
                    break;
                case 'check':
                    this.checkBtn.disabled = false;
                    break;
                case 'call':
                    this.callBtn.disabled = false;
                    document.getElementById('call-amount').textContent = action.amount;
                    break;
                case 'raise':
                    this.raiseBtn.disabled = false;
                    this.raiseMin = action.min;
                    this.raiseMax = action.max;
                    this.raiseSlider.min = action.min;
                    this.raiseSlider.max = action.max;
                    this.raiseSlider.value = action.min;
                    this.raiseInput.value = action.min;
                    break;
                case 'all_in':
                    this.allinBtn.disabled = false;
                    break;
            }
        });
    }

    updateGameControls(phase) {
        const actionPanel = document.getElementById('action-panel');
        const gameControls = document.querySelector('.game-controls');
        const rejoinPanel = document.getElementById('rejoin-panel');

        if (!this.isSeated) {
            actionPanel.classList.add('hidden');
            gameControls.classList.add('hidden');
            if (rejoinPanel) rejoinPanel.classList.remove('hidden');
            return;
        }

        actionPanel.classList.remove('hidden');
        gameControls.classList.remove('hidden');
        if (rejoinPanel) rejoinPanel.classList.add('hidden');

        if (phase === 'waiting') {
            this.startGameBtn.disabled = false;
        } else {
            this.startGameBtn.disabled = true;
        }
    }

    toggleRaiseControls() {
        this.raiseControls.classList.toggle('hidden');
    }

    updateRaiseInput() {
        this.raiseInput.value = this.raiseSlider.value;
    }

    updateRaiseSlider() {
        let value = parseInt(this.raiseInput.value);
        value = Math.max(this.raiseMin, Math.min(this.raiseMax, value));
        this.raiseInput.value = value;
        this.raiseSlider.value = value;
    }

    sendAction(action, amount = 0) {
        this.ws.send(JSON.stringify({
            type: 'action',
            data: { action, amount }
        }));
        this.raiseControls.classList.add('hidden');
    }

    confirmRaise() {
        const amount = parseInt(this.raiseInput.value);
        this.sendAction('raise', amount);
    }

    startGame() {
        this.ws.send(JSON.stringify({ type: 'start_game' }));
    }

    toggleSitOut() {
        this.ws.send(JSON.stringify({ type: 'sit_out' }));
    }

    handlePlayerAction(data) {
        const actionNames = {
            'fold': 'folds',
            'check': 'checks',
            'call': 'calls',
            'raise': 'raises to',
            'all_in': 'all-in'
        };

        let text = `${data.player_name} ${actionNames[data.action] || data.action}`;
        if (data.amount > 0 && data.action !== 'fold' && data.action !== 'check') {
            text += ` ${data.amount}`;
        }

        this.addActionToCurrentHand(text, data.action);
    }

    addActionToCurrentHand(text, type = 'info') {
        // Add to current hand history
        if (this.currentHandNumber && this.handHistory[this.currentHandNumber]) {
            this.handHistory[this.currentHandNumber].actions.push({ text, type });
        }

        // Update display if viewing current hand
        if (this.handSelect.value === 'current') {
            this.addActionLog(text, type);
        }

        // Update current actions display on table
        this.updateCurrentActionsDisplay();
    }

    addActionLog(text, type = 'info') {
        const el = document.createElement('div');
        el.className = `action-log-item ${type}`;
        el.innerHTML = `<span class="action-type">${this.escapeHtml(text)}</span>`;
        this.actionLog.insertBefore(el, this.actionLog.firstChild);

        while (this.actionLog.children.length > 50) {
            this.actionLog.removeChild(this.actionLog.lastChild);
        }
    }

    updateCurrentActionsDisplay() {
        if (!this.currentActions) return;

        const hand = this.handHistory[this.currentHandNumber];
        if (!hand || !hand.actions || hand.actions.length === 0) {
            this.currentActions.textContent = '';
            return;
        }

        // Show last 3 actions on the table
        const recentActions = hand.actions.slice(-3)
            .filter(a => a.type !== 'info')
            .map(a => a.text)
            .join(' | ');
        this.currentActions.textContent = recentActions;
    }

    updateHandSelector() {
        // Add new hand to selector
        const option = document.createElement('option');
        option.value = this.currentHandNumber;
        option.textContent = `Hand #${this.currentHandNumber}`;
        this.handSelect.insertBefore(option, this.handSelect.children[1]);

        // Keep selector on "Current"
        this.handSelect.value = 'current';

        // Clear action log for new hand
        this.actionLog.innerHTML = '';
    }

    displayHandHistory() {
        this.actionLog.innerHTML = '';
        const selectedValue = this.handSelect.value;

        if (selectedValue === 'current') {
            // Show current hand
            const hand = this.handHistory[this.currentHandNumber];
            if (hand && hand.actions) {
                hand.actions.forEach(action => {
                    this.addActionLog(action.text, action.type);
                });
            }
        } else {
            // Show historical hand
            const handNum = parseInt(selectedValue);
            const hand = this.handHistory[handNum];
            if (hand && hand.actions) {
                hand.actions.slice().reverse().forEach(action => {
                    this.addActionLog(action.text, action.type);
                });
            }
        }
    }

    showHandResult(result) {
        if (!result.winners || result.winners.length === 0) return;

        // Save result to hand history
        if (this.currentHandNumber && this.handHistory[this.currentHandNumber]) {
            this.handHistory[this.currentHandNumber].result = result;
        }

        const winnersText = result.winners.join(', ');
        let handDesc = '';

        if (result.hand_results && result.hand_results.length > 0) {
            const winnerResult = result.hand_results.find(r =>
                result.winners.includes(r.player_name)
            );
            if (winnerResult) {
                handDesc = winnerResult.description;
            }
        }

        // Build player results HTML
        let playersHtml = '<div class="result-details">';
        if (this.gameState && this.gameState.players) {
            this.gameState.players.forEach(p => {
                const stats = this.playerStats[p.name];
                if (stats) {
                    const profit = p.stack - stats.buyIn;
                    const profitClass = profit >= 0 ? 'positive' : 'negative';
                    const profitSign = profit >= 0 ? '+' : '';
                    playersHtml += `
                        <div class="result-player">
                            <span>${this.escapeHtml(p.name)}</span>
                            <span>Stack: ${p.stack} (Buy-in: ${stats.buyIn})</span>
                            <span class="profit ${profitClass}">${profitSign}${profit}</span>
                        </div>
                    `;
                }
            });
        }
        playersHtml += '</div>';

        this.resultBody.innerHTML = `
            <div class="winner-display">
                ${this.escapeHtml(winnersText)} wins ${result.pot}
            </div>
            ${handDesc ? `<div class="hand-display">${handDesc}</div>` : ''}
            ${playersHtml}
        `;

        this.resultModal.classList.remove('hidden');
        this.addActionToCurrentHand(`=== ${winnersText} wins ${result.pot} ===`, 'info');
    }

    closeResultModal() {
        this.resultModal.classList.add('hidden');
    }

    showRunTwicePrompt() {
        if (this.runTwicePanel) {
            this.runTwicePanel.classList.remove('hidden');
        }
    }

    sendRunChoice(runTwice) {
        this.ws.send(JSON.stringify({
            type: 'run_twice_choice',
            data: { run_twice: runTwice }
        }));
        if (this.runTwicePanel) {
            this.runTwicePanel.classList.add('hidden');
        }
    }

    sendChat() {
        const message = this.chatInput.value.trim();
        if (!message) return;

        this.ws.send(JSON.stringify({
            type: 'chat',
            data: { message }
        }));

        this.chatInput.value = '';
    }

    addChatMessage(sender, message) {
        const el = document.createElement('div');
        el.className = 'chat-message';
        el.innerHTML = `
            <span class="sender">${this.escapeHtml(sender)}:</span>
            <span class="text">${this.escapeHtml(message)}</span>
        `;
        this.chatMessages.appendChild(el);
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    updateStats(players) {
        // Build active player names set
        const activeNames = new Set(players.map(p => p.name));

        // Update active player stats
        let statsHtml = players.map(p => {
            const stats = this.playerStats[p.name] || { buyIn: p.stack, profit: 0 };
            const profit = p.stack - stats.buyIn;
            const profitClass = profit >= 0 ? 'positive' : 'negative';
            const profitSign = profit >= 0 ? '+' : '';

            // Mark as active
            if (this.playerStats[p.name]) {
                this.playerStats[p.name].isActive = true;
            }

            return `
                <div class="stat-item">
                    <div class="stat-header">
                        <span>${this.escapeHtml(p.name)}</span>
                        <span class="stat-profit ${profitClass}">${profitSign}${profit}</span>
                    </div>
                    <div class="stat-details">
                        Stack: ${p.stack} | Buy-in: ${stats.buyIn}
                    </div>
                </div>
            `;
        }).join('');

        // Add left players stats (greyed out)
        const leftPlayers = Object.entries(this.leftPlayerStats)
            .filter(([name, _]) => !activeNames.has(name));

        if (leftPlayers.length > 0) {
            statsHtml += '<div class="stat-divider">Left Players</div>';
            statsHtml += leftPlayers.map(([name, stats]) => {
                const profitClass = stats.profit >= 0 ? 'positive' : 'negative';
                const profitSign = stats.profit >= 0 ? '+' : '';

                return `
                    <div class="stat-item stat-inactive">
                        <div class="stat-header">
                            <span>${this.escapeHtml(name)} (left)</span>
                            <span class="stat-profit ${profitClass}">${profitSign}${stats.profit}</span>
                        </div>
                        <div class="stat-details">
                            Final: ${stats.currentStack} | Buy-in: ${stats.buyIn}
                        </div>
                    </div>
                `;
            }).join('');
        }

        this.statsContent.innerHTML = statsHtml;
        this.saveSession();
    }

    switchTab(tabId) {
        this.tabBtns.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });

        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.add('hidden');
        });

        document.getElementById(`${tabId}-tab`).classList.remove('hidden');
    }

    copyRoomId() {
        // Use multiple methods for clipboard copy
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(this.roomId)
                .then(() => this.showToast('Room ID copied!', 'success'))
                .catch(() => this.fallbackCopyRoomId());
        } else {
            this.fallbackCopyRoomId();
        }
    }

    fallbackCopyRoomId() {
        // Fallback for older browsers or non-HTTPS
        const textArea = document.createElement('textarea');
        textArea.value = this.roomId;
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            this.showToast('Room ID copied!', 'success');
        } catch (err) {
            this.showToast('Failed to copy. Room ID: ' + this.roomId, 'error');
        }
        document.body.removeChild(textArea);
    }

    leaveRoom() {
        if (this.ws && this.isSeated) {
            // Save current player's stats before leaving
            if (this.playerName && this.playerStats[this.playerName]) {
                this.leftPlayerStats[this.playerName] = { ...this.playerStats[this.playerName] };
                this.leftPlayerStats[this.playerName].isActive = false;
            }

            this.ws.send(JSON.stringify({ type: 'leave' }));
            this.isSeated = false;
            this.isSpectating = true;
            this.showToast('You left the table. Click Rejoin to sit back down.', 'info');
            this.updateSpectatorUI();
            this.saveSession();
        }
    }

    leaveRoomCompletely() {
        // Actually leave the room and go back to landing page
        if (this.ws) {
            this.ws.send(JSON.stringify({ type: 'leave' }));
            this.ws.close();
        }
        this.gamePage.classList.add('hidden');
        this.landingPage.classList.remove('hidden');
        this.clearSession();
        this.roomId = null;
        this.playerName = null;
        this.gameState = null;
        this.isSeated = false;
        this.isSpectating = false;
        this.handHistory = {};
        // Don't clear playerStats - preserve for stats tab
        this.currentHandNumber = 0;
    }

    rejoinGame() {
        if (!this.isSeated && this.ws && this.ws.readyState === WebSocket.OPEN) {
            // Show seat selection - just update UI to allow clicking seats
            this.isSpectating = true;
            this.showToast('Click an empty seat to sit down', 'info');
            this.updateSpectatorUI();
        }
    }

    updateSpectatorUI() {
        const actionPanel = document.getElementById('action-panel');
        const gameControls = document.querySelector('.game-controls');
        const rejoinPanel = document.getElementById('rejoin-panel');

        if (this.isSeated) {
            // Player is seated - show normal controls
            if (actionPanel) actionPanel.classList.remove('hidden');
            if (gameControls) gameControls.classList.remove('hidden');
            if (rejoinPanel) rejoinPanel.classList.add('hidden');
            this.leaveRoomBtn.textContent = 'Leave';
            this.leaveRoomBtn.onclick = () => this.leaveRoom();
        } else {
            // Player is spectating - show rejoin option
            if (actionPanel) actionPanel.classList.add('hidden');
            if (gameControls) gameControls.classList.add('hidden');
            if (rejoinPanel) rejoinPanel.classList.remove('hidden');
            this.leaveRoomBtn.textContent = 'Exit Room';
            this.leaveRoomBtn.onclick = () => this.leaveRoomCompletely();
        }
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize game when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.game = new PokerGame();
});
