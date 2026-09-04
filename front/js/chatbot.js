/* ==========================================================================
   STEG Facture Platform - AI Admin Chatbot (RAG Engine Client)
   ========================================================================== */

const Chatbot = {
  initialized: false,
  messages: [],
  isSending: false,

  init() {
    if (!this.initialized) {
      this.initialized = true;
      this.addWelcomeMessage();
    }
    this.renderMessages();
    this.checkStatus();
  },

  addWelcomeMessage() {
    this.messages = [
      {
        sender: 'bot',
        text: `Hello **${Auth.currentUser?.name || 'Administrator'}**! 👋<br><br>` +
              `I am your **STEG InvoiceFlow RAG AI Assistant**. I have real-time access to the system database to query **users**, **invoices**, **demands**, and **audit logs**.<br><br>` +
              `How can I assist you with user administration or system analytics today?`,
        sources: ['Database RAG Engine', 'Users DB', 'Invoices DB', 'Demands DB'],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ];
  },

  async checkStatus() {
    const statusBadge = document.getElementById('chatbotEngineStatus');
    if (!statusBadge) return;
    try {
      const res = await Auth.apiFetch('/chatbot/status');
      if (res.ok) {
        const data = await res.json();
        statusBadge.innerHTML = `<i class="fa-solid fa-database"></i> DB RAG Active (${data.indexed_entities} entities)`;
      }
    } catch (e) {
      console.warn('Chatbot status check failed:', e);
    }
  },

  clearChat() {
    this.addWelcomeMessage();
    this.renderMessages();
    if (window.UI) UI.showToast('Chat history cleared.', 'info');
  },

  sendPreset(promptText) {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.value = promptText;
      this.sendMessage(promptText);
    }
  },

  handleSubmit(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('chatInput');
    if (!input) return;
    const text = input.value.trim();
    if (!text || this.isSending) return;
    input.value = '';
    this.sendMessage(text);
  },

  async sendMessage(queryText) {
    if (!queryText || this.isSending) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    // Push User message
    this.messages.push({
      sender: 'user',
      text: this.escapeHtml(queryText),
      timestamp: timeStr
    });

    // Push temporary Thinking message
    const thinkingMsgId = 'thinking_' + Date.now();
    this.messages.push({
      id: thinkingMsgId,
      sender: 'bot',
      isThinking: true,
      text: `<div class="chat-thinking"><i class="fa-solid fa-brain fa-spin text-cyan"></i> <span>AI Assistant is thinking &amp; analyzing database query...</span> <div class="chat-thinking-dots"><span></span><span></span><span></span></div></div>`,
      timestamp: timeStr
    });

    // Render immediately showing thinking message
    this.renderMessages();
    this.isSending = true;
    this.setLoading(true);

    try {
      const response = await Auth.apiFetch('/chatbot/query', {
        method: 'POST',
        body: JSON.stringify({
          message: queryText,
          history: this.messages.filter(m => !m.isThinking).slice(-6).map(m => ({ role: m.sender, content: m.text }))
        })
      });

      // Remove thinking message
      this.messages = this.messages.filter(m => m.id !== thinkingMsgId);

      if (!response.ok) {
        let errDetail = 'API call failed.';
        try {
          const errData = await response.json();
          if (errData.detail) errDetail = errData.detail;
        } catch (_) {}
        throw new Error(errDetail);
      }

      const data = await response.json();

      this.messages.push({
        sender: 'bot',
        text: data.answer || 'No response generated.',
        sql_query: data.sql_query,
        sources: data.sources || ['OpenRouter AI', 'SQL Server DB'],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    } catch (err) {
      console.error('Chatbot API error:', err);
      // Remove thinking message if present
      this.messages = this.messages.filter(m => m.id !== thinkingMsgId);
      
      // Append user-friendly API failure message and reset to normal mode
      this.messages.push({
        sender: 'bot',
        text: `⚠️ <strong>API Call Error</strong><br><br>${this.escapeHtml(err.message || 'Connection to API model failed.')}<br><br><span style="font-size: 0.8rem; color: var(--text-dim);"><i class="fa-solid fa-rotate-left text-cyan"></i> Restored normal chat operation. You can send your next query.</span>`,
        sources: ['API Failure Recovery'],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
    } finally {
      this.isSending = false;
      this.setLoading(false);
      this.renderMessages();
    }
  },

  setLoading(loading) {
    const btn = document.getElementById('btnSendChat');
    const input = document.getElementById('chatInput');
    if (btn) {
      btn.disabled = loading;
      btn.innerHTML = loading ? 
        `<i class="fa-solid fa-circle-notch fa-spin"></i> Processing...` : 
        `<span>Send</span> <i class="fa-solid fa-paper-plane"></i>`;
    }
    if (input) input.disabled = loading;
  },

  renderMessages() {
    const container = document.getElementById('chatMessages');
    if (!container) return;

    // Clear container and build each message as an isolated DOM fragment.
    // This prevents bot-generated <table> HTML from bleeding into outer page
    // tables (e.g. the Audit Log table) due to the browser's HTML adoption
    // algorithm for orphaned table cells.
    container.innerHTML = '';

    this.messages.forEach(msg => {
      const isUser = msg.sender === 'user';
      const userInitials = (Auth.currentUser?.name || 'Admin').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

      // --- Avatar ---
      const avatar = document.createElement('div');
      avatar.className = `chat-avatar ${isUser ? 'user' : 'bot'}`;
      if (isUser) {
        avatar.textContent = userInitials;
      } else {
        avatar.innerHTML = '<i class="fa-solid fa-robot"></i>';
      }

      // --- Chat text ---
      // Bot messages may contain markdown (tables, bold, headers, lists).
      // Run through marked.js to convert to proper HTML before injecting.
      const chatText = document.createElement('div');
      chatText.className = 'chat-text';
      chatText.innerHTML = isUser ? msg.text : this.parseMarkdown(msg.text);

      // --- SQL query collapsible (bot only) ---
      let sqlEl = null;
      if (!isUser && msg.sql_query) {
        sqlEl = document.createElement('details');
        sqlEl.style.cssText = 'margin-top: 0.5rem; font-size: 0.75rem; color: var(--text-dim);';
        const summary = document.createElement('summary');
        summary.style.cssText = 'cursor: pointer; opacity: 0.8; user-select: none;';
        const modelLabel = (msg.sources && msg.sources.length > 0) ? msg.sources[0] : 'AI';
        summary.innerHTML = `<i class="fa-solid fa-code text-cyan"></i> ${modelLabel} — Generated SQL`;
        const pre = document.createElement('pre');
        pre.style.cssText = 'background: rgba(0,0,0,0.4); padding: 0.5rem 0.75rem; border-radius: 6px; margin-top: 0.4rem; overflow-x: auto; color: #a5f3fc; border: 1px solid rgba(0,242,254,0.2);';
        const code = document.createElement('code');
        code.textContent = msg.sql_query;
        pre.appendChild(code);
        sqlEl.appendChild(summary);
        sqlEl.appendChild(pre);
      }

      // --- Source tags (bot only) ---
      let sourcesEl = null;
      if (!isUser && msg.sources && msg.sources.length > 0) {
        sourcesEl = document.createElement('div');
        sourcesEl.style.cssText = 'margin-top: 0.6rem; display: flex; flex-wrap: wrap; gap: 0.4rem;';
        msg.sources.forEach(s => {
          const tag = document.createElement('span');
          tag.className = 'chat-source-tag';
          tag.innerHTML = `<i class="fa-solid fa-database"></i> ${this.escapeHtml(s)}`;
          sourcesEl.appendChild(tag);
        });
      }

      // --- Timestamp ---
      const tsEl = document.createElement('div');
      tsEl.style.cssText = `font-size: 0.68rem; color: var(--text-dim); margin-top: 0.4rem; text-align: ${isUser ? 'right' : 'left'};`;
      tsEl.textContent = msg.timestamp;

      // --- Bubble ---
      const bubble = document.createElement('div');
      bubble.className = 'chat-bubble';
      bubble.appendChild(chatText);
      if (sqlEl) bubble.appendChild(sqlEl);
      if (sourcesEl) bubble.appendChild(sourcesEl);
      bubble.appendChild(tsEl);

      // --- Message row ---
      const row = document.createElement('div');
      row.className = `chat-msg ${msg.sender}`;
      row.appendChild(avatar);
      row.appendChild(bubble);

      container.appendChild(row);
    });

    container.scrollTop = container.scrollHeight;
  },

  parseMarkdown(text) {
    if (!text) return '';
    // If marked.js is available, use it to render markdown → HTML
    if (window.marked) {
      try {
        // Configure marked: safe renderer, break on single newlines
        return window.marked.parse(text, {
          breaks: true,
          gfm: true     // GitHub Flavored Markdown (tables, strikethrough, etc.)
        });
      } catch (e) {
        console.warn('marked.js parse error:', e);
      }
    }
    // Fallback: basic bold/newline conversion if marked isn't loaded
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  },

  escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
};

window.Chatbot = Chatbot;
