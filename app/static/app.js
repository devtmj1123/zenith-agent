// Zenith-OS Frontend Application
class ZenithApp {
    constructor() {
        this.ws = null;
        this.currentTab = 'chat';
        this.messages = [];
        this.particles = [];
        this.agentReady = false;
        this.activityLog = []; // Narrator activity log
        this.notificationPermission = false;
        this.init();
    }

    init() {
        this.checkAgentStatus();
        this.bindEvents();
        this.connectWebSocket();
        this.loadSettings();
        this.initParticles();
        this.initRippleEffects();
        this.requestNotificationPermission();
    }

    // ===== Loading Screen =====
    async checkAgentStatus() {
        const loadingScreen = document.getElementById('loadingScreen');
        const loadingBar = document.getElementById('loadingBar');
        const loadingStatus = document.getElementById('loadingStatus');
        const mainApp = document.getElementById('mainApp');

        const statusMessages = {
            'loading': 'Loading embedding model...',
            'loading_model': 'Loading embedding model...',
            'initializing_agent': 'Initializing agent...',
            'ready': 'Ready!',
        };

        let attempts = 0;
        const maxAttempts = 120; // 60 seconds max

        const poll = async () => {
            attempts++;
            if (attempts > maxAttempts) {
                loadingStatus.textContent = 'Timeout - agent may still be loading...';
                this.showMainApp();
                return;
            }

            try {
                const res = await fetch('/api/status');
                const data = await res.json();

                // Update loading bar
                const progress = data.ready ? 100 : Math.min(90, attempts * 2);
                loadingBar.style.width = progress + '%';

                // Update status text
                if (data.status && data.status.startsWith('error:')) {
                    loadingStatus.innerHTML = `<span style="color: var(--error)">${data.status}</span>`;
                    // Still show main app after error
                    setTimeout(() => this.showMainApp(), 2000);
                    return;
                }

                loadingStatus.textContent = statusMessages[data.status] || data.status;

                if (data.ready) {
                    this.agentReady = true;
                    loadingBar.style.width = '100%';
                    loadingStatus.textContent = 'Ready!';
                    setTimeout(() => this.showMainApp(), 500);
                    return;
                }

                // Continue polling
                setTimeout(poll, 500);
            } catch (err) {
                loadingStatus.textContent = 'Connecting to server...';
                setTimeout(poll, 1000);
            }
        };

        poll();
    }

    showMainApp() {
        const loadingScreen = document.getElementById('loadingScreen');
        const mainApp = document.getElementById('mainApp');

        loadingScreen.classList.add('hidden');
        mainApp.style.display = '';

        // Load data after showing main app
        this.loadTools();
        this.loadMemoryStats();
    }

    // ===== Particle Background =====
    initParticles() {
        const canvas = document.createElement('canvas');
        canvas.id = 'particleCanvas';
        canvas.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;opacity:0.3;';
        document.body.prepend(canvas);

        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;

        // Create particles
        for (let i = 0; i < 30; i++) {
            this.particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 3 + 1,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                opacity: Math.random() * 0.5 + 0.1
            });
        }

        const animate = () => {
            ctx.clearRect(0, 0, width, height);

            this.particles.forEach(p => {
                p.x += p.speedX;
                p.y += p.speedY;

                // Wrap around
                if (p.x < 0) p.x = width;
                if (p.x > width) p.x = 0;
                if (p.y < 0) p.y = height;
                if (p.y > height) p.y = 0;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(108, 92, 231, ${p.opacity})`;
                ctx.fill();
            });

            // Draw connections
            this.particles.forEach((p1, i) => {
                this.particles.slice(i + 1).forEach(p2 => {
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 150) {
                        ctx.beginPath();
                        ctx.strokeStyle = `rgba(108, 92, 231, ${0.1 * (1 - dist / 150)})`;
                        ctx.lineWidth = 0.5;
                        ctx.moveTo(p1.x, p1.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.stroke();
                    }
                });
            });

            requestAnimationFrame(animate);
        };

        animate();

        window.addEventListener('resize', () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
        });
    }

    // ===== Ripple Effects =====
    initRippleEffects() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.neu-btn, .nav-btn, .send-btn');
            if (!btn) return;

            const ripple = document.createElement('span');
            ripple.style.cssText = `
                position: absolute;
                border-radius: 50%;
                background: rgba(108, 92, 231, 0.3);
                transform: scale(0);
                animation: ripple 0.6s ease-out;
                pointer-events: none;
            `;

            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';

            btn.style.position = btn.style.position || 'relative';
            btn.style.overflow = 'hidden';
            btn.appendChild(ripple);

            setTimeout(() => ripple.remove(), 600);
        });

        // Add ripple animation to stylesheet
        const style = document.createElement('style');
        style.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }

    // ===== WebSocket Connection =====
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        this.ws.onopen = () => {
            console.log('Connected to Zenith-OS');
            this.updateConnectionStatus(true);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onclose = () => {
            console.log('Disconnected from Zenith-OS');
            this.updateConnectionStatus(false);
            // Reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    reconnectWebSocket() {
        if (this.ws) {
            this.ws.close();
        }
        this.connectWebSocket();
    }

    updateConnectionStatus(connected) {
        // Could add a visual indicator
    }

    // ===== Event Binding =====
    bindEvents() {
        // Tab navigation
        document.querySelectorAll('.nav-btn[data-tab]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchTab(btn.dataset.tab);
            });
        });

        // Chat input
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');

        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        chatInput.addEventListener('input', () => {
            this.autoResizeTextarea(chatInput);
        });

        sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });

        // Research
        document.getElementById('researchBtn')?.addEventListener('click', () => {
            this.startResearch();
        });

        // Reminders
        document.getElementById('createReminderBtn')?.addEventListener('click', () => {
            this.createReminder();
        });

        // Dream
        document.getElementById('dreamBtn')?.addEventListener('click', () => {
            this.startDreamCycle();
        });

        // Diagnosis
        document.getElementById('runDiagnosisBtn')?.addEventListener('click', () => {
            this.runDiagnosis();
        });
        document.getElementById('runAutoFixBtn')?.addEventListener('click', () => {
            this.runAutoFix();
        });

        // Settings
        document.getElementById('saveSettings')?.addEventListener('click', () => {
            this.saveSettings();
        });

        // Theme toggle
        document.getElementById('settingTheme')?.addEventListener('change', (e) => {
            document.documentElement.setAttribute('data-theme', e.target.value);
            localStorage.setItem('zenith-theme', e.target.value);
        });
    }

    // ===== Tab Switching =====
    switchTab(tabName) {
        // Update nav buttons
        document.querySelectorAll('.nav-btn[data-tab]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.classList.toggle('active', tab.id === `tab-${tabName}`);
        });

        this.currentTab = tabName;

        // Load tab-specific data
        if (tabName === 'memory') {
            this.loadMemoryStats();
        } else if (tabName === 'tools') {
            this.loadTools();
        } else if (tabName === 'dream') {
            this.loadDreamStats();
        } else if (tabName === 'reminders') {
            this.loadReminders();
        }
    }

    // ===== Chat =====
    sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();

        if (!message) return;

        // Clear welcome message
        const welcome = document.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }

        // Add user message
        this.addMessage('user', message);
        input.value = '';
        this.autoResizeTextarea(input);

        // Show typing indicator
        this.showTypingIndicator();

        // Send to backend
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'chat',
                content: message
            }));
        } else {
            // Fallback to HTTP
            fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message })
            })
            .then(res => res.json())
            .then(data => {
                this.hideTypingIndicator();
                this.addMessage('assistant', data.response, {
                    tool_calls: data.tool_calls || 0,
                    tokens_used: data.tokens_used || 0,
                });
                if (data.tool_calls > 0) {
                    this.addNarratorEntry(`Response generated using ${data.tool_calls} tool${data.tool_calls > 1 ? 's' : ''}`, '✅');
                }
                const preview = (data.response || '').substring(0, 100).replace(/\n/g, ' ');
                this.sendNotification('Zenith-OS', preview, '⚡');
            })
            .catch(err => {
                this.hideTypingIndicator();
                this.addMessage('assistant', 'Error: Could not connect to backend.');
            });
        }
    }

    addMessage(role, content, meta = {}) {
        const container = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = role === 'assistant' ? 'Z' : 'You';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessage(content);

        // Metadata bar (timestamp, tokens, tools)
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';

        const now = new Date();
        const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        let metaHtml = `<span class="meta-time">${timeStr}</span>`;

        if (meta.tool_calls > 0) {
            metaHtml += `<span class="meta-tools">🔧 ${meta.tool_calls} tools</span>`;
        }
        if (meta.tokens_used > 0) {
            metaHtml += `<span class="meta-tokens">📊 ${meta.tokens_used} tokens</span>`;
        }
        if (meta.tokens_in > 0) {
            metaHtml += `<span class="meta-tokens-in">↓${meta.tokens_in}</span>`;
        }
        if (meta.tokens_out > 0) {
            metaHtml += `<span class="meta-tokens-out">↑${meta.tokens_out}</span>`;
        }

        metaDiv.innerHTML = metaHtml;

        messageDiv.appendChild(avatar);
        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper';
        wrapper.appendChild(contentDiv);
        wrapper.appendChild(metaDiv);
        messageDiv.appendChild(wrapper);
        container.appendChild(messageDiv);

        // Scroll to bottom
        container.scrollTop = container.scrollHeight;

        // Store message
        this.messages.push({ role, content, timestamp: Date.now(), meta });
    }

    formatMessage(content) {
        // Simple markdown-like formatting
        let formatted = content
            // Code blocks
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            // Inline code
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            // Bold
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            // Line breaks
            .replace(/\n/g, '<br>');

        return formatted;
    }

    showTypingIndicator() {
        const container = document.getElementById('chatMessages');
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typingIndicator';
        indicator.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
            <span class="typing-text">Thinking...</span>
        `;
        container.appendChild(indicator);
        container.scrollTop = container.scrollHeight;
    }

    hideTypingIndicator() {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            indicator.remove();
        }
    }

    autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }

    // ===== WebSocket Message Handling =====
    handleMessage(data) {
        switch (data.type) {
            case 'chat_response':
                this.hideTypingIndicator();
                this.addMessage('assistant', data.content, {
                    tool_calls: data.tool_calls || 0,
                    tokens_used: data.tokens_used || 0,
                    tokens_in: data.prompt_tokens || 0,
                    tokens_out: data.completion_tokens || 0,
                });
                // Narrator summary
                if (data.tool_calls > 0) {
                    this.addNarratorEntry(`Response generated using ${data.tool_calls} tool${data.tool_calls > 1 ? 's' : ''}`, '✅');
                }
                // Browser notification
                const preview = data.content.substring(0, 100).replace(/\n/g, ' ');
                this.sendNotification('Zenith-OS', preview, '⚡');
                break;

            case 'thinking':
                this.addNarratorEntry('Thinking and planning...', '🧠');
                this.updateTypingText('Thinking...');
                break;

            case 'action':
                // Narrator: show which tool is being used
                const toolName = data.content || 'tool';
                const toolIcons = {
                    'search': '🔍', 'fetch': '🌐', 'read_file': '📄', 'write_file': '✏️',
                    'run_command': '💻', 'browse': '🌍', 'recall': '🧠', 'calendar': '📅',
                    'goals': '🎯', 'reminders': '⏰', 'pc_screenshot': '📸', 'analyze': '🔬',
                    'memory': '🧠', 'browse_open': '🌍', 'browse_click': '👆', 'browse_fill': '⌨️',
                    'browse_screenshot': '📸', 'browse_snapshot': '🔍', 'browse_get': '📥',
                    'search': '🔍', 'fetch': '🌐', 'scrape': '🕷️', 'pc_click': '🖱️',
                    'pc_fill': '⌨️', 'pc_press': '🔘',
                };
                const icon = toolIcons[toolName] || '⚙️';
                this.addNarratorEntry(`Using ${toolName}`, icon);
                this.updateTypingText(`Using ${toolName}...`);
                break;

            case 'observation':
                // Narrator: show tool result summary
                const obsPreview = (data.content || '').substring(0, 80).replace(/\n/g, ' ');
                this.addNarratorEntry(`Got result: ${obsPreview}${obsPreview.length >= 80 ? '...' : ''}`, '📥');
                break;

            case 'error':
                this.hideTypingIndicator();
                this.addMessage('assistant', `Error: ${data.content}`);
                this.addNarratorEntry(`Error occurred: ${data.content.substring(0, 60)}`, '❌');
                this.sendNotification('Zenith-OS - Error', data.content.substring(0, 100), '❌');
                break;

            case 'research_result':
                this.displayResearchResults(data.content);
                this.addNarratorEntry('Research completed', '🔬');
                this.sendNotification('Zenith-OS', 'Research completed!', '🔬');
                break;

            case 'dream_result':
                this.displayDreamResult(data.content);
                this.addNarratorEntry('Dream cycle completed', '🌙');
                break;

            case 'reminder':
                // Reminder notification
                const reminder = data.content || {};
                this.addNarratorEntry(`⏰ Reminder: ${reminder.title || 'Unknown'}`, '⏰');
                this.sendNotification(`⏰ Reminder: ${reminder.title || ''}`, reminder.description || reminder.title || '', '⏰');
                // Show in chat as a system message
                this.addMessage('assistant', `⏰ **Reminder:** ${reminder.title}\n${reminder.description || ''}\n_Scheduled: ${reminder.datetime || 'now'}_`);
                break;

            default:
                console.log('Unknown message type:', data.type);
        }
    }

    updateTypingText(text) {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) {
            const textSpan = indicator.querySelector('.typing-text');
            if (textSpan) {
                textSpan.textContent = text;
            }
        }
    }

    // ===== Research =====
    startResearch() {
        const query = document.getElementById('researchQuery').value.trim();
        const domain = document.getElementById('researchDomain').value;

        if (!query) return;

        const resultsDiv = document.getElementById('researchResults');
        resultsDiv.innerHTML = '<div class="placeholder-text">Researching...</div>';

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'research',
                query,
                domain
            }));
        } else {
            fetch('/api/research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, domain })
            })
            .then(res => res.json())
            .then(data => {
                this.displayResearchResults(data);
            })
            .catch(err => {
                resultsDiv.innerHTML = '<div class="placeholder-text">Error: Research failed.</div>';
            });
        }
    }

    displayResearchResults(data) {
        const resultsDiv = document.getElementById('researchResults');
        if (!data || !data.findings || data.findings.length === 0) {
            resultsDiv.innerHTML = '<div class="placeholder-text">No results found.</div>';
            return;
        }

        let html = '<div class="research-findings">';
        data.findings.forEach(finding => {
            html += `
                <div class="finding-card">
                    <h4>${finding.title || 'Finding'}</h4>
                    <p>${finding.content || finding.abstract || ''}</p>
                    ${finding.source ? `<span class="source">${finding.source}</span>` : ''}
                </div>
            `;
        });
        html += '</div>';

        if (data.rebuttal) {
            html += `
                <div class="rebuttal-section">
                    <h3>Socratic Rebuttal</h3>
                    <p>${data.rebuttal}</p>
                </div>
            `;
        }

        resultsDiv.innerHTML = html;
    }

    // ===== Memory =====
    loadMemoryStats() {
        fetch('/api/memory/stats')
            .then(res => res.json())
            .then(data => {
                this.animateCounter('memoryCount', data.total_memories || 0);
                this.animateCounter('desireCount', data.active_desires || 0);
                this.animateCounter('associationCount', data.total_associations || 0);
            })
            .catch(err => {
                console.error('Failed to load memory stats:', err);
            });

        this.loadMemories();
    }

    // ===== Animated Counter =====
    animateCounter(elementId, target) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const start = parseInt(el.textContent) || 0;
        const duration = 800;
        const startTime = performance.now();

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + (target - start) * eased);

            el.textContent = current;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };

        requestAnimationFrame(update);
    }

    loadMemories() {
        fetch('/api/memory/list')
            .then(res => res.json())
            .then(data => {
                const listDiv = document.getElementById('memoryList');
                if (!data.memories || data.memories.length === 0) {
                    listDiv.innerHTML = '<div class="placeholder-text">No memories stored yet.</div>';
                    return;
                }

                let html = '';
                data.memories.slice(0, 20).forEach(mem => {
                    html += `
                        <div class="memory-item">
                            <div class="memory-content">${mem.content || mem.summary || ''}</div>
                            <div class="memory-time">${new Date(mem.created_at * 1000).toLocaleString()}</div>
                        </div>
                    `;
                });
                listDiv.innerHTML = html;
            })
            .catch(err => {
                console.error('Failed to load memories:', err);
            });
    }

    // ===== Diagnosis =====
    async runDiagnosis() {
        const issuesDiv = document.getElementById('diagnosisIssues');
        const statsDiv = document.getElementById('diagnosisStats');
        const healthCircle = document.querySelector('.health-value');

        issuesDiv.innerHTML = '<div class="placeholder-text">Running diagnostics...</div>';

        try {
            const res = await fetch('/api/diagnosis');
            const data = await res.json();

            // Update health score
            const score = data.health_score || 0;
            healthCircle.textContent = score;
            healthCircle.className = 'health-value';
            if (score >= 80) healthCircle.classList.add('health-good');
            else if (score >= 50) healthCircle.classList.add('health-warning');
            else healthCircle.classList.add('health-critical');

            // Update stats
            let statsHtml = '';
            if (data.stats) {
                Object.entries(data.stats).forEach(([key, value]) => {
                    statsHtml += `<div class="stat-item"><span class="stat-key">${key}</span><span class="stat-val">${value}</span></div>`;
                });
            }
            statsDiv.innerHTML = statsHtml;

            // Update issues
            if (!data.issues || data.issues.length === 0) {
                issuesDiv.innerHTML = '<div class="placeholder-text">✅ No issues detected!</div>';
                return;
            }

            let html = '';
            const icons = { critical: '🔴', error: '🟠', warning: '🟡', info: '🔵' };
            data.issues.forEach(issue => {
                const icon = icons[issue.severity] || '⚪';
                const fixBadge = issue.auto_fixable ? '<span class="fix-badge">auto-fix</span>' : '';
                html += `
                    <div class="issue-card issue-${issue.severity}">
                        <div class="issue-header">
                            <span>${icon} ${issue.title}</span>
                            ${fixBadge}
                        </div>
                        <div class="issue-desc">${issue.description}</div>
                        <div class="issue-category">${issue.category}</div>
                    </div>
                `;
            });
            issuesDiv.innerHTML = html;

        } catch (err) {
            issuesDiv.innerHTML = `<div class="placeholder-text">Error: ${err.message}</div>`;
        }
    }

    async runAutoFix() {
        const issuesDiv = document.getElementById('diagnosisIssues');
        issuesDiv.innerHTML = '<div class="placeholder-text">Running auto-fix...</div>';

        try {
            const res = await fetch('/api/diagnosis/fix', { method: 'POST' });
            const data = await res.json();

            let html = `<div class="fix-result">`;
            html += `<p>Health Score: ${data.health_score}/100</p>`;
            html += `<p>Issues Found: ${data.issues_found}</p>`;

            if (data.fixes_applied && data.fixes_applied.length > 0) {
                html += `<h4>Fixes Applied:</h4><ul>`;
                data.fixes_applied.forEach(fix => {
                    html += `<li>✅ ${fix}</li>`;
                });
                html += `</ul>`;
            } else {
                html += `<p>No auto-fixable issues found.</p>`;
            }

            html += `</div>`;
            issuesDiv.innerHTML = html;

            // Re-run diagnosis to show updated state
            setTimeout(() => this.runDiagnosis(), 1000);

        } catch (err) {
            issuesDiv.innerHTML = `<div class="placeholder-text">Error: ${err.message}</div>`;
        }
    }

    // ===== Tools =====
    loadTools() {
        fetch('/api/tools')
            .then(res => res.json())
            .then(data => {
                const grid = document.getElementById('toolsGrid');
                const toolCategories = {
                    'File Operations': ['read_file', 'write_file', 'edit_file', 'delete_file', 'list_dir', 'glob_search', 'grep_search'],
                    'Shell': ['run_command', 'check_background'],
                    'Web': ['search', 'fetch', 'scrape'],
                    'Browser': ['browse_open', 'browse_snapshot', 'browse_click', 'browse_fill', 'browse_get', 'browse_screenshot', 'browse_scroll', 'browse_hover', 'browse_keypress'],
                    'PC Control': ['pc_get_windows', 'pc_get_ui_tree', 'pc_click', 'pc_fill', 'pc_press', 'pc_screenshot', 'pc_launch', 'pc_focus'],
                    'Memory': ['recall', 'store_memory', 'search_memory'],
                    'Productivity': ['calendar', 'goals', 'reminders', 'spreadsheet', 'parse_document'],
                    'Science': ['science_research', 'analyze_molecule', 'check_battery_claim', 'check_fusion_lawson', 'compute_debye_length'],
                    'Subagent': ['dispatch_agent', 'dispatch_parallel', 'swarm'],
                    'Workflows': ['workflow_create', 'workflow_execute', 'workflow_list'],
                    'Notifications': ['reminders_create', 'reminders_list', 'reminders_dismiss', 'reminders_recurring'],
                    'System': ['get_time', 'get_weather', 'create_tool', 'delete_dynamic_tool', 'load_skill']
                };

                const icons = {
                    'File Operations': '📁',
                    'Shell': '💻',
                    'Web': '🌐',
                    'Browser': '🌍',
                    'PC Control': '🖥️',
                    'Memory': '🧠',
                    'Productivity': '📅',
                    'Science': '🔬',
                    'Subagent': '🤖',
                    'Workflows': '⚡',
                    'Notifications': '🔔',
                    'System': '⚙️'
                };

                let html = '';
                Object.entries(toolCategories).forEach(([category, tools]) => {
                    html += `
                        <div class="tool-card">
                            <div class="tool-icon">${icons[category] || '🔧'}</div>
                            <h4>${category}</h4>
                            <p>${tools.length} tools</p>
                        </div>
                    `;
                });
                grid.innerHTML = html;
            })
            .catch(err => {
                console.error('Failed to load tools:', err);
            });
    }

    // ===== Narrator (Activity Log) =====
    addNarratorEntry(text, icon = '⚙️') {
        const container = document.getElementById('chatMessages');
        const entry = document.createElement('div');
        entry.className = 'narrator-entry';
        entry.innerHTML = `
            <span class="narrator-icon">${icon}</span>
            <span class="narrator-text">${text}</span>
            <span class="narrator-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        `;
        container.appendChild(entry);
        container.scrollTop = container.scrollHeight;

        // Store in activity log
        this.activityLog.push({ text, icon, timestamp: Date.now() });
    }

    // ===== Browser Notifications =====
    requestNotificationPermission() {
        if ('Notification' in window) {
            Notification.requestPermission().then(permission => {
                this.notificationPermission = permission === 'granted';
            });
        }
    }

    sendNotification(title, body, icon = '⚡') {
        if (!this.notificationPermission) return;
        if (document.hasFocus()) return; // Don't notify if user is looking

        try {
            const notif = new Notification(title, {
                body: body.substring(0, 200),
                icon: '/static/favicon.ico',
                badge: '/static/favicon.ico',
                tag: 'zenith-response',
                requireInteraction: false,
                silent: false,
            });

            notif.onclick = () => {
                window.focus();
                notif.close();
            };

            // Auto-close after 5 seconds
            setTimeout(() => notif.close(), 5000);
        } catch (e) {
            console.log('Notification failed:', e);
        }
    }

    // ===== Dream Mode =====
    loadDreamStats() {
        fetch('/api/dream/stats')
            .then(res => res.json())
            .then(data => {
                this.animateCounter('dreamCycles', data.total_dream_cycles || 0);
                this.animateCounter('dreamInsights', data.insights_generated || 0);
            })
            .catch(err => {
                console.error('Failed to load dream stats:', err);
            });
    }

    startDreamCycle() {
        const btn = document.getElementById('dreamBtn');
        const indicator = document.getElementById('dreamIndicator');
        const pulse = indicator.querySelector('.pulse');

        btn.disabled = true;
        btn.textContent = 'Dreaming...';
        pulse.classList.add('active');
        indicator.querySelector('span').textContent = 'Dreaming';

        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'dream' }));
        } else {
            fetch('/api/dream/start', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    this.displayDreamResult(data);
                    btn.disabled = false;
                    btn.textContent = 'Start Dream Cycle';
                    pulse.classList.remove('active');
                    indicator.querySelector('span').textContent = 'Idle';
                })
                .catch(err => {
                    btn.disabled = false;
                    btn.textContent = 'Start Dream Cycle';
                    pulse.classList.remove('active');
                    indicator.querySelector('span').textContent = 'Idle';
                });
        }
    }

    displayDreamResult(data) {
        const logDiv = document.getElementById('dreamLog');
        const entry = document.createElement('div');
        entry.className = 'dream-entry';

        let content = `<div class="dream-time">${new Date().toLocaleTimeString()}</div>`;
        if (data.novel_insights && data.novel_insights.length > 0) {
            content += data.novel_insights.map(insight => `<p>${insight}</p>`).join('');
        } else {
            content += '<p>No new insights this cycle.</p>';
        }

        entry.innerHTML = content;
        logDiv.insertBefore(entry, logDiv.firstChild);

        // Update stats
        this.loadDreamStats();
    }

    // ===== Reminders =====
    async loadReminders() {
        const listDiv = document.getElementById('remindersList');
        try {
            const res = await fetch('/api/reminders');
            const data = await res.json();

            if (!data.reminders || data.reminders.length === 0) {
                listDiv.innerHTML = '<div class="reminder-empty">🔔 No upcoming reminders. Create one above!</div>';
                return;
            }

            let html = '';
            data.reminders.forEach(r => {
                const icon = r.recurrence ? '🔄' : '⏰';
                html += `
                    <div class="reminder-card">
                        <div class="reminder-icon">${icon}</div>
                        <div class="reminder-info">
                            <div class="reminder-title">${r.title || 'Untitled'}</div>
                            ${r.description ? `<div class="reminder-desc">${r.description}</div>` : ''}
                            <div class="reminder-time">📅 ${r.datetime || 'No time set'}${r.recurrence ? ` (${r.recurrence})` : ''}</div>
                        </div>
                        <div class="reminder-actions">
                            <button class="neu-btn" onclick="window.zenithApp.dismissReminder('${r.id}')">Done</button>
                            <button class="neu-btn" onclick="window.zenithApp.deleteReminder('${r.id}')">Delete</button>
                        </div>
                    </div>
                `;
            });
            listDiv.innerHTML = html;
        } catch (err) {
            listDiv.innerHTML = '<div class="reminder-empty">Error loading reminders</div>';
        }
    }

    async createReminder() {
        const title = document.getElementById('reminderTitle').value.trim();
        const desc = document.getElementById('reminderDesc').value.trim();
        const timeInput = document.getElementById('reminderTime').value;

        if (!title) {
            alert('Please enter a reminder title');
            return;
        }

        let datetime = timeInput;
        if (!datetime) {
            // Default to 5 minutes from now
            const d = new Date(Date.now() + 5 * 60000);
            datetime = d.toISOString().slice(0, 16);
        }

        // Convert from datetime-local format to "YYYY-MM-DD HH:MM"
        const formatted = datetime.replace('T', ' ');

        try {
            const res = await fetch('/api/reminders/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, datetime: formatted, description: desc })
            });
            const data = await res.json();

            if (data.success) {
                document.getElementById('reminderTitle').value = '';
                document.getElementById('reminderDesc').value = '';
                document.getElementById('reminderTime').value = '';
                this.addNarratorEntry(`Reminder created: ${title}`, '🔔');
                this.loadReminders();
            } else {
                alert('Failed to create reminder: ' + (data.error || 'Unknown error'));
            }
        } catch (err) {
            alert('Error creating reminder: ' + err.message);
        }
    }

    async dismissReminder(id) {
        try {
            await fetch('/api/reminders/dismiss', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reminder_id: id })
            });
            this.loadReminders();
        } catch (err) {
            console.error('Failed to dismiss reminder:', err);
        }
    }

    async deleteReminder(id) {
        try {
            await fetch('/api/reminders/dismiss', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reminder_id: id })
            });
            this.loadReminders();
        } catch (err) {
            console.error('Failed to delete reminder:', err);
        }
    }

    // ===== Settings =====
    loadSettings() {
        const settings = JSON.parse(localStorage.getItem('zenith-settings') || '{}');

        if (settings.provider) {
            document.getElementById('settingProvider').value = settings.provider;
        }
        if (settings.model) {
            document.getElementById('settingModel').value = settings.model;
        }
        if (settings.maxIterations) {
            document.getElementById('settingMaxIter').value = settings.maxIterations;
        }
        if (settings.tokenBudget) {
            document.getElementById('settingTokenBudget').value = settings.tokenBudget;
        }
        if (settings.dreamMode !== undefined) {
            document.getElementById('settingDream').checked = settings.dreamMode;
        }

        // Load theme
        const theme = localStorage.getItem('zenith-theme') || 'light';
        document.getElementById('settingTheme').value = theme;
        document.documentElement.setAttribute('data-theme', theme);
    }

    saveSettings() {
        const settings = {
            provider: document.getElementById('settingProvider').value,
            apiKey: document.getElementById('settingApiKey').value,
            model: document.getElementById('settingModel').value,
            maxIterations: parseInt(document.getElementById('settingMaxIter').value),
            tokenBudget: parseInt(document.getElementById('settingTokenBudget').value),
            dreamMode: document.getElementById('settingDream').checked
        };

        localStorage.setItem('zenith-settings', JSON.stringify(settings));

        // Send to backend
        fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        })
        .then(res => res.json())
        .then(data => {
            alert('Settings saved!');
        })
        .catch(err => {
            alert('Settings saved locally. Backend update failed.');
        });
    }
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    window.zenithApp = new ZenithApp();
});
