/**
 * SafeGaze Chat Widget
 * Hybrid FAQ + Gemini AI chatbot — self-contained, injected on load.
 */
(function () {
    'use strict';

    // ─── State ─────────────────────────────────────────────────────────────────
    let isOpen = false;
    let isWaiting = false;
    let unreadCount = 0;
    let conversationHistory = [];

    // ─── Quick chip questions ───────────────────────────────────────────────────
    const QUICK_CHIPS = [
        { label: '🛡️ What is SafeGaze?',      msg: 'What is SafeGaze?' },
        { label: '🦴 How detection works',      msg: 'How does fall detection work?' },
        { label: '🔔 How are alerts sent?',     msg: 'How are alerts sent?' },
        { label: '📊 System status',            msg: 'System status' },
        { label: '🆘 Emergency steps',          msg: 'What to do if someone falls?' },
        { label: '🧪 Test the alert',           msg: 'How to test alert?' },
        { label: '⚙️ Configuration',           msg: 'How to configure settings?' },
        { label: '📸 Where are snapshots?',     msg: 'Where are snapshots saved?' },
    ];

    // ─── Markdown renderer ──────────────────────────────────────────────────────
    function renderMarkdown(text) {
        // Escape HTML first
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks (```...```)
        html = html.replace(/```(?:\w+)?\n?([\s\S]*?)```/g, (_, code) =>
            `<pre><code>${code.trim()}</code></pre>`
        );

        // Inline code (`code`)
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold (**text**)
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic (*text*)
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Unordered lists (lines starting with • or -)
        html = html.replace(/^[•\-] (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/gs, match =>
            `<ul>${match}</ul>`
        );

        // Numbered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

        // Inline links [text](url)
        html = html.replace(
            /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
            '<a href="$2" target="_blank" rel="noopener">$1</a>'
        );

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        // Clean up double-br inside pre tags
        html = html.replace(/<pre>(.*?)<\/pre>/gs, (m, inner) =>
            `<pre>${inner.replace(/<br>/g, '\n')}</pre>`
        );

        return html;
    }

    // ─── Time helper ───────────────────────────────────────────────────────────
    function nowTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // ─── Build widget DOM ───────────────────────────────────────────────────────
    function buildWidget() {
        // Toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'sg-chat-toggle';
        toggleBtn.id = 'sg-chat-toggle';
        toggleBtn.setAttribute('aria-label', 'Open SafeGaze Assistant');
        toggleBtn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
                 fill="none" stroke="currentColor" stroke-width="2.2" id="sg-toggle-icon">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
        `;

        const unreadBadge = document.createElement('span');
        unreadBadge.className = 'sg-unread-badge';
        unreadBadge.id = 'sg-unread-badge';
        unreadBadge.style.display = 'none';
        toggleBtn.appendChild(unreadBadge);

        // Panel
        const panel = document.createElement('div');
        panel.className = 'sg-chat-panel';
        panel.id = 'sg-chat-panel';
        panel.innerHTML = `
            <!-- Header -->
            <div class="sg-chat-header">
                <div class="sg-chat-avatar">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
                         fill="none" stroke="currentColor" stroke-width="2.2">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                </div>
                <div class="sg-chat-header-info">
                    <div class="sg-chat-title">SafeGaze Assistant</div>
                    <div class="sg-chat-subtitle">
                        <span class="sg-online-dot"></span>
                        Online · AI + FAQ powered
                    </div>
                </div>
                <button class="sg-chat-close" id="sg-chat-close" aria-label="Close chat">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
                         fill="none" stroke="currentColor" stroke-width="2.5">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                </button>
            </div>

            <!-- Live Status Bar -->
            <div class="sg-status-bar" id="sg-status-bar">
                <div class="sg-status-chip">
                    <span class="sg-status-dot-green" id="sg-sys-dot"></span>
                    <span id="sg-sys-status" class="sg-status-normal">NORMAL</span>
                </div>
                <div class="sg-status-chip">🔔 <span id="sg-alert-count">0</span> alerts</div>
                <div class="sg-status-chip">🤖 YOLOv8n-Pose</div>
            </div>

            <!-- Quick chips -->
            <div class="sg-quick-chips" id="sg-quick-chips"></div>

            <!-- Messages -->
            <div class="sg-messages" id="sg-messages"></div>

            <!-- Input area -->
            <div class="sg-input-area">
                <textarea
                    class="sg-input"
                    id="sg-input"
                    placeholder="Ask anything about SafeGaze…"
                    rows="1"
                    maxlength="500"
                ></textarea>
                <button class="sg-send-btn" id="sg-send-btn" aria-label="Send message">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
                         fill="none" stroke="currentColor" stroke-width="2.5">
                        <line x1="22" y1="2" x2="11" y2="13"/>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                </button>
            </div>
            <div class="sg-input-footer">
                <span>Powered by FAQ engine + Google Gemini AI · SafeGaze v2.0</span>
            </div>
        `;

        document.body.appendChild(toggleBtn);
        document.body.appendChild(panel);
        return { toggleBtn, panel };
    }

    // ─── Render quick chips ─────────────────────────────────────────────────────
    function renderChips() {
        const container = document.getElementById('sg-quick-chips');
        QUICK_CHIPS.forEach(chip => {
            const btn = document.createElement('button');
            btn.className = 'sg-chip';
            btn.textContent = chip.label;
            btn.addEventListener('click', () => sendMessage(chip.msg));
            container.appendChild(btn);
        });
    }

    // ─── Append message to chat ─────────────────────────────────────────────────
    function appendMessage(text, role, source) {
        const container = document.getElementById('sg-messages');

        // Remove welcome state if present
        const welcome = container.querySelector('.sg-welcome');
        if (welcome) welcome.remove();

        const wrapper = document.createElement('div');
        wrapper.className = `sg-msg sg-msg-${role}`;

        let sourceLabel = '';
        let sourceCls = '';
        if (role === 'bot') {
            if (source === 'faq')       { sourceLabel = 'FAQ'; sourceCls = 'sg-source-faq'; }
            else if (source === 'ai')   { sourceLabel = 'AI'; sourceCls = 'sg-source-ai'; }
            else if (source === 'fallback') { sourceLabel = 'FAQ'; sourceCls = 'sg-source-fallback'; }
            else if (source === 'error'){ sourceLabel = 'Error'; sourceCls = 'sg-source-error'; }
        }

        const iconSvg = role === 'bot'
            ? `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2.2">
                   <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
               </svg>`
            : `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2">
                   <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                   <circle cx="12" cy="7" r="4"/>
               </svg>`;

        const bubbleContent = role === 'bot'
            ? renderMarkdown(text)
            : escapeHtml(text);

        wrapper.innerHTML = `
            <div class="sg-msg-icon">${iconSvg}</div>
            <div class="sg-msg-content">
                <div class="sg-bubble">${bubbleContent}</div>
                <div class="sg-msg-meta">
                    <span>${nowTime()}</span>
                    ${sourceLabel ? `<span class="sg-source-badge ${sourceCls}">${sourceLabel}</span>` : ''}
                </div>
            </div>
        `;

        container.appendChild(wrapper);
        scrollToBottom();

        if (role === 'bot' && !isOpen) {
            unreadCount++;
            updateUnreadBadge();
        }
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    // ─── Typing indicator ───────────────────────────────────────────────────────
    function showTyping() {
        const container = document.getElementById('sg-messages');
        const indicator = document.createElement('div');
        indicator.className = 'sg-typing-indicator';
        indicator.id = 'sg-typing';
        indicator.innerHTML = `
            <div class="sg-msg-icon" style="background:linear-gradient(135deg,#1d4ed8,#4338ca);border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24"
                     fill="none" stroke="white" stroke-width="2.2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
            </div>
            <div class="sg-typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        container.appendChild(indicator);
        scrollToBottom();
    }

    function hideTyping() {
        const el = document.getElementById('sg-typing');
        if (el) el.remove();
    }

    function scrollToBottom() {
        const el = document.getElementById('sg-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }

    // ─── Unread badge ───────────────────────────────────────────────────────────
    function updateUnreadBadge() {
        const badge = document.getElementById('sg-unread-badge');
        if (!badge) return;
        if (unreadCount > 0 && !isOpen) {
            badge.textContent = unreadCount > 9 ? '9+' : unreadCount;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }

    // ─── Live status polling ────────────────────────────────────────────────────
    async function pollLiveStatus() {
        try {
            const res = await fetch('/status');
            if (!res.ok) return;
            const data = await res.json();

            const dot = document.getElementById('sg-sys-dot');
            const statusEl = document.getElementById('sg-sys-status');
            if (!dot || !statusEl) return;

            if (data.status === 'FALL DETECTED') {
                dot.className = 'sg-status-dot-red';
                statusEl.textContent = '⚠ FALL';
                statusEl.className = 'sg-status-danger';
            } else {
                dot.className = 'sg-status-dot-green';
                statusEl.textContent = 'NORMAL';
                statusEl.className = 'sg-status-normal';
            }
        } catch (_) {}

        try {
            const res = await fetch('/alerts');
            if (!res.ok) return;
            const data = await res.json();
            const el = document.getElementById('sg-alert-count');
            if (el) el.textContent = data.length;
        } catch (_) {}
    }

    // ─── Send message ───────────────────────────────────────────────────────────
    async function sendMessage(text) {
        text = (text || '').trim();
        if (!text || isWaiting) return;

        const input = document.getElementById('sg-input');
        const sendBtn = document.getElementById('sg-send-btn');
        if (input) input.value = '';
        if (input) input.style.height = 'auto';

        appendMessage(text, 'user', null);
        conversationHistory.push({ role: 'user', content: text });

        isWaiting = true;
        if (sendBtn) sendBtn.disabled = true;
        showTyping();

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: conversationHistory.slice(-10),
                }),
            });

            hideTyping();

            if (res.status === 401 || res.status === 302) {
                appendMessage(
                    '⚠️ Session expired. Please [login again](/) to continue.',
                    'bot', 'error'
                );
                return;
            }

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            const reply = data.response || 'Sorry, I couldn\'t generate a response.';
            const source = data.source || 'faq';

            appendMessage(reply, 'bot', source);
            conversationHistory.push({ role: 'bot', content: reply });

            // Keep history manageable
            if (conversationHistory.length > 20) {
                conversationHistory = conversationHistory.slice(-16);
            }

        } catch (err) {
            hideTyping();
            appendMessage(
                '⚠️ Connection error. Make sure the server is running and try again.',
                'bot', 'error'
            );
            console.error('[SafeGaze Chat] Error:', err);
        } finally {
            isWaiting = false;
            if (sendBtn) sendBtn.disabled = false;
            if (input) input.focus();
        }
    }

    // ─── Toggle open/close ──────────────────────────────────────────────────────
    function toggleChat() {
        isOpen = !isOpen;
        const panel = document.getElementById('sg-chat-panel');
        const toggleBtn = document.getElementById('sg-chat-toggle');

        if (isOpen) {
            panel.classList.add('visible');
            toggleBtn.classList.add('open');
            unreadCount = 0;
            updateUnreadBadge();
            setTimeout(() => {
                const input = document.getElementById('sg-input');
                if (input) input.focus();
                scrollToBottom();
            }, 320);
        } else {
            panel.classList.remove('visible');
            toggleBtn.classList.remove('open');
        }
    }

    // ─── Welcome message ────────────────────────────────────────────────────────
    function showWelcome() {
        appendMessage(
            "👋 **Hi! I'm SafeGaze Assistant.**\n\n" +
            "I can answer questions about the fall detection system, " +
            "help with configuration, explain how alerts work, and guide " +
            "you through emergency procedures.\n\n" +
            "Click a quick option below or type your question! 💬",
            'bot', 'faq'
        );
    }

    // ─── Initialize ─────────────────────────────────────────────────────────────
    function init() {
        buildWidget();
        renderChips();
        showWelcome();

        // Event: toggle button
        document.getElementById('sg-chat-toggle').addEventListener('click', toggleChat);
        document.getElementById('sg-chat-close').addEventListener('click', toggleChat);

        // Event: send button
        document.getElementById('sg-send-btn').addEventListener('click', () => {
            const input = document.getElementById('sg-input');
            sendMessage(input.value);
        });

        // Event: Enter to send (Shift+Enter = newline)
        document.getElementById('sg-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const input = document.getElementById('sg-input');
                sendMessage(input.value);
            }
        });

        // Auto-resize textarea
        document.getElementById('sg-input').addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        // Click outside to close
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('sg-chat-panel');
            const toggle = document.getElementById('sg-chat-toggle');
            if (isOpen && panel && !panel.contains(e.target) && !toggle.contains(e.target)) {
                toggleChat();
            }
        });

        // Live status polling
        pollLiveStatus();
        setInterval(pollLiveStatus, 5000);

        // Show a subtle notification dot after 3 seconds to attract attention
        setTimeout(() => {
            if (!isOpen) {
                unreadCount = 1;
                updateUnreadBadge();
            }
        }, 3000);
    }

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
