// BerryPoker Game Client

class PokerGame {
    constructor() {
        this.ws = null;
        this.roomId = null;
        this.playerName = null;
        this.gameState = null;
        this.raiseMin = 0;
        this.raiseMax = 0;
        this.isSeated = false;  // Track if player has chosen a seat
        this.buyInAmount = 100;

        this.initElements();
        this.initEventListeners();
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

        // Game controls
        this.startGameBtn = document.getElementById('start-game-btn');
        this.sitOutBtn = document.getElementById('sit-out-btn');

        // Side panel
        this.actionLog = document.getElementById('action-log');
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

        // Actions
        this.foldBtn.addEventListener('click', () => this.sendAction('fold'));
        this.checkBtn.addEventListener('click', () => this.sendAction('check'));
        this.callBtn.addEventListener('click', () => this.sendAction('call'));
        this.raiseBtn.addEventListener('click', () => this.toggleRaiseControls());
        this.allinBtn.addEventListener('click', () => this.sendAction('all_in'));
        this.confirmRaiseBtn.addEventListener('click', () => this.confirmRaise());
        this.raiseSlider.addEventListener('input', () => this.updateRaiseInput());
        this.raiseInput.addEventListener('change', () => this.updateRaiseSlider());

        // Game controls
        this.startGameBtn.addEventListener('click', () => this.startGame());
        this.sitOutBtn.addEventListener('click', () => this.toggleSitOut());

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

    async createRoom() {
        const name = this.playerNameInput.value.trim();
        if (!name) {
            this.showToast('请输入昵称', 'error');
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
            this.showToast('创建房间失败', 'error');
        }
    }

    joinRoom() {
        const name = this.playerNameInput.value.trim();
        const roomId = this.roomIdInput.value.trim();

        if (!name) {
            this.showToast('请输入昵称', 'error');
            return;
        }
        if (!roomId) {
            this.showToast('请输入房间ID', 'error');
            return;
        }

        this.roomId = roomId;
        this.playerName = name;
        this.connectWebSocket();
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws/${this.roomId}`);
        this.buyInAmount = parseInt(this.buyInInput.value) || 100;

        this.ws.onopen = () => {
            // First, enter as spectator to see the table
            this.ws.send(JSON.stringify({
                type: 'spectate',
                data: {
                    player_name: this.playerName
                }
            }));
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };

        this.ws.onclose = () => {
            this.showToast('连接已断开', 'error');
        };

        this.ws.onerror = () => {
            this.showToast('连接错误', 'error');
        };
    }

    selectSeat(seat) {
        if (this.isSeated) {
            this.showToast('你已经坐下了', 'error');
            return;
        }

        this.ws.send(JSON.stringify({
            type: 'join',
            data: {
                player_name: this.playerName,
                stack: this.buyInAmount,
                seat: seat
            }
        }));
    }

    handleMessage(message) {
        switch (message.type) {
            case 'spectating':
                // Entered room as spectator, can now choose a seat
                this.isSeated = false;
                this.showGamePage();
                this.showToast('请点击空座位坐下', 'info');
                break;

            case 'joined':
                // Successfully sat down at a seat
                this.isSeated = true;
                this.showGamePage();
                this.showToast(`已坐下 (座位 ${message.data.seat + 1})`, 'success');
                break;

            case 'error':
                this.showToast(message.data.message, 'error');
                break;

            case 'game_state':
                this.updateGameState(message.data);
                break;

            case 'player_joined':
                this.showToast(`${message.data.player_name} 加入了游戏`, 'info');
                this.addActionLog(`${message.data.player_name} 加入了游戏`, 'info');
                break;

            case 'player_left':
                this.showToast(`${message.data.player_name} 离开了游戏`, 'info');
                this.addActionLog(`${message.data.player_name} 离开了游戏`, 'info');
                break;

            case 'player_disconnected':
                this.showToast(`${message.data.player_name} 断开连接`, 'info');
                break;

            case 'hand_started':
                this.addActionLog(`=== 第 ${message.data.hand_number} 局开始 ===`, 'info');
                break;

            case 'player_action':
                this.handlePlayerAction(message.data);
                break;

            case 'hand_ended':
                this.showHandResult(message.data);
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
    }

    renderCommunityCards(cards) {
        this.communityCards.innerHTML = '';
        cards.forEach(card => {
            this.communityCards.appendChild(this.createCardElement(card));
        });
    }

    renderSeats(players, dealerSeat, currentPlayerSeat) {
        // Track occupied seats
        const occupiedSeats = new Set(players.map(p => p.seat));

        // Clear all seats first
        for (let i = 0; i < 9; i++) {
            const seatEl = document.querySelector(`.seat-${i}`);
            seatEl.innerHTML = '';
            seatEl.className = `seat seat-${i}`;
            seatEl.onclick = null;

            if (!occupiedSeats.has(i)) {
                // Empty seat
                seatEl.classList.add('empty');

                if (!this.isSeated) {
                    // Player can click to sit here
                    seatEl.classList.add('available');
                    seatEl.innerHTML = `
                        <div class="seat-number">座位 ${i + 1}</div>
                        <div class="sit-here">点击坐下</div>
                    `;
                    seatEl.onclick = () => this.selectSeat(i);
                } else {
                    seatEl.innerHTML = `<div class="seat-number">座位 ${i + 1}</div>`;
                }
            }
        }

        // Render players
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
            if (player.is_folded) statusHtml = '<div class="player-status">已弃牌</div>';
            else if (player.is_all_in) statusHtml = '<div class="player-status">All In</div>';
            else if (player.is_sitting_out) statusHtml = '<div class="player-status">暂离</div>';

            // Position badge
            let positionHtml = '';
            if (player.position) {
                positionHtml = `<div class="player-position" data-pos="${player.position}">${player.position}</div>`;
            }

            seatEl.innerHTML = `
                ${positionHtml}
                <div class="player-name">${this.escapeHtml(player.name)}</div>
                <div class="player-stack">${player.stack}</div>
                ${player.current_bet > 0 ? `<div class="player-bet">下注: ${player.current_bet}</div>` : ''}
                ${cardsHtml}
                ${statusHtml}
            `;
        });

        // Position dealer button
        if (dealerSeat !== null) {
            const dealerBtn = document.getElementById('dealer-button');
            dealerBtn.classList.remove('hidden');
            const seatEl = document.querySelector(`.seat-${dealerSeat}`);
            if (seatEl) {
                const rect = seatEl.getBoundingClientRect();
                const tableRect = document.querySelector('.poker-table').getBoundingClientRect();
                dealerBtn.style.left = `${rect.left - tableRect.left + rect.width + 5}px`;
                dealerBtn.style.top = `${rect.top - tableRect.top}px`;
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
        // Disable all buttons first
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
        // Hide controls if not seated
        const actionPanel = document.getElementById('action-panel');
        const gameControls = document.querySelector('.game-controls');

        if (!this.isSeated) {
            actionPanel.classList.add('hidden');
            gameControls.classList.add('hidden');
            return;
        }

        actionPanel.classList.remove('hidden');
        gameControls.classList.remove('hidden');

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
            'fold': '弃牌',
            'check': '过牌',
            'call': '跟注',
            'raise': '加注',
            'all_in': 'All In'
        };

        let text = `${data.player_name} ${actionNames[data.action] || data.action}`;
        if (data.amount > 0) {
            text += ` ${data.amount}`;
        }

        this.addActionLog(text, data.action);
    }

    addActionLog(text, type = 'info') {
        const el = document.createElement('div');
        el.className = `action-log-item ${type}`;
        el.innerHTML = `<span class="action-type">${this.escapeHtml(text)}</span>`;
        this.actionLog.insertBefore(el, this.actionLog.firstChild);

        // Keep only last 50 items
        while (this.actionLog.children.length > 50) {
            this.actionLog.removeChild(this.actionLog.lastChild);
        }
    }

    showHandResult(result) {
        if (!result.winners || result.winners.length === 0) return;

        const winnersText = result.winners.join(', ');
        let handDesc = '';

        if (result.hand_results && result.hand_results.length > 0) {
            const winnerResult = result.hand_results.find(r =>
                result.winners.includes(r.player.name)
            );
            if (winnerResult) {
                handDesc = winnerResult.description;
            }
        }

        this.resultBody.innerHTML = `
            <div class="winner-display">
                ${this.escapeHtml(winnersText)} 赢得 ${result.pot}
            </div>
            ${handDesc ? `<div class="hand-display">${handDesc}</div>` : ''}
        `;

        this.resultModal.classList.remove('hidden');
        this.addActionLog(`=== ${winnersText} 赢得 ${result.pot} ===`, 'info');
    }

    closeResultModal() {
        this.resultModal.classList.add('hidden');
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
        this.statsContent.innerHTML = players.map(p => `
            <div class="stat-item">
                <span>${this.escapeHtml(p.name)}</span>
                <span>${p.stack}</span>
            </div>
        `).join('');
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
        navigator.clipboard.writeText(this.roomId).then(() => {
            this.showToast('房间ID已复制', 'success');
        });
    }

    leaveRoom() {
        if (this.ws) {
            this.ws.send(JSON.stringify({ type: 'leave' }));
            this.ws.close();
        }
        this.gamePage.classList.add('hidden');
        this.landingPage.classList.remove('hidden');
        this.roomId = null;
        this.playerName = null;
        this.gameState = null;
        this.isSeated = false;
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
