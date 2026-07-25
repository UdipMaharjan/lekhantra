// ============================================================================
// Lekhantra - Premium AI Study Assistant
// Complete JavaScript Implementation
// ============================================================================

// API Base URL Configuration
const isLocalhost = window.location.hostname === 'localhost' ||
                    window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocalhost ? 'http://127.0.0.1:8000' : 'https://lekhantra-backend.onrender.com';

// ============================================================================
// Global State
// ============================================================================
let currentTextFile = null;
let currentDocumentName = '';
let isProcessing = false;
let typingInterval = null;
let conversations = [];
let currentConversationId = null;
let pendingDeleteId = null;

// ============================================================================
// DOM Elements
// ============================================================================
const elements = {
  // Form elements
  pdfInput: document.getElementById('pdfInput'),
  pdfQuestion: document.getElementById('pdfQuestion'),
  questionCount: document.getElementById('questionCount'),

  // Display elements
  dropZone: document.getElementById('dropZone'),
  chatMessages: document.getElementById('chatMessages'),
  messagesContainer: document.getElementById('messagesContainer'),
  welcomeState: document.getElementById('welcomeState'),

  // Document info
  currentFileLabel: document.getElementById('currentFileLabel'),
  currentStatusLabel: document.getElementById('currentStatusLabel'),
  headerDocName: document.getElementById('headerDocName'),
  currentDocument: document.getElementById('currentDocument'),

  // Buttons
  uploadBtn: document.getElementById('uploadBtn'),
  sendBtn: document.getElementById('sendBtn'),
  newChatBtn: document.getElementById('newChatBtn'),
  sidebarToggle: document.getElementById('sidebarToggle'),
  sidebar: document.getElementById('sidebar'),

  // Quick actions
  generateVivaBtn: document.getElementById('generateVivaBtn'),
  generateExamBtn: document.getElementById('generateExamBtn'),

  // Input actions
  copyOutputBtn: document.getElementById('copyOutputBtn'),
  downloadOutputBtn: document.getElementById('downloadOutputBtn'),

  // Modals
  authModal: document.getElementById('authModal'),
  generatorModal: document.getElementById('generatorModal'),
  deleteModal: document.getElementById('deleteModal'),
  deleteConfirmBtn: document.getElementById('deleteConfirmBtn'),
  deleteCancelBtn: document.getElementById('deleteCancelBtn'),
  generatorTitle: document.getElementById('generatorTitle'),
  generatorSubtitle: document.getElementById('generatorSubtitle'),
  generatorResult: document.getElementById('generatorResult'),
  generatorActions: document.getElementById('generatorActions'),
  generatorCopyBtn: document.getElementById('generatorCopyBtn'),
  generatorDownloadBtn: document.getElementById('generatorDownloadBtn'),

  // Progress
  uploadProgress: document.getElementById('uploadProgress'),
  progressFilename: document.getElementById('progressFilename'),
  progressPercent: document.getElementById('progressPercent'),
  progressFill: document.getElementById('progressFill'),
  progressStatus: document.getElementById('progressStatus'),

  // User
  userMenu: document.getElementById('userMenu'),
  userProfile: document.getElementById('userProfile'),
  userGreeting: document.getElementById('userGreeting'),
  userAvatar: document.getElementById('userAvatar'),
  openAuthBtn: document.getElementById('openAuthBtn'),
};

// ============================================================================
// Toast Notifications
// ============================================================================
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = message;
  toast.className = `toast show ${type}`;

  setTimeout(() => {
    toast.className = 'toast';
  }, 3000);
}

// ============================================================================
// Markdown Parser (Simple Implementation)
// ============================================================================
function parseMarkdown(text) {
  if (!text) return '';

  let html = text
    // Escape HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

    // Code blocks
    .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')

    // Inline code
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

    // Bold
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')

    // Italic
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/ _([^_]+)_/g, '<em>$1</em>')

    // Headings
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')

    // Horizontal rule
    .replace(/^---$/gm, '<hr>')

    // Unordered lists
    .replace(/^\s*[-*]\s+(.+)$/gm, '<li>$1</li>')

    // Ordered lists
    .replace(/^\s*\d+\.\s+(.+)$/gm, '<li>$1</li>')

    // Blockquotes
    .replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>')

    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')

    // Paragraphs
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');

  // Wrap in paragraph if needed
  if (!html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }

  // Wrap consecutive <li> in <ul>
  html = html.replace(/(<li>.*<\/li>)(?=<li>)/g, '<ul>$&</ul>');
  html = html.replace(/(<li>.*<\/li>)(?!.*<\/ul>)/g, '<ul>$&</ul>');

  return html;
}

// ============================================================================
// Typing Indicator
// ============================================================================
function showTypingIndicator() {
  if (!elements.messagesContainer) return;

  hideTypingIndicator();

  const indicator = document.createElement('div');
  indicator.className = 'message message-ai typing';
  indicator.id = 'typingIndicator';
  indicator.innerHTML = `
    <div class="message-avatar">
      <img src="assets/logo.png" alt="Lekhantra">
    </div>
    <div class="message-content">
      <div class="typing-dots">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>
  `;

  elements.messagesContainer.appendChild(indicator);
  scrollToBottom();
}

function hideTypingIndicator() {
  const existing = document.getElementById('typingIndicator');
  if (existing) existing.remove();
}

// ============================================================================
// Scroll to Bottom
// ============================================================================
function scrollToBottom() {
  if (elements.chatMessages) {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }
}

// ============================================================================
// Chat Interface
// ============================================================================
function addMessage(content, isUser = false, saveToHistory = true) {
  console.log('[DEBUG] addMessage called', { isUser, saveToHistory, contentLength: content.length });

  if (!elements.messagesContainer || !elements.welcomeState) {
    console.log('[DEBUG] Elements not found, returning early');
    return;
  }

  // Hide welcome state when messages are added
  elements.welcomeState.classList.add('hidden');

  // Save to conversation history
  if (saveToHistory) {
    console.log('[DEBUG] Calling saveMessage from addMessage');
    saveMessage(content, isUser);
  } else {
    console.log('[DEBUG] Skipping saveMessage (loading from history)');
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${isUser ? 'message-user' : 'message-ai'}`;

  const time = new Date().toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  });

  if (isUser) {
    messageDiv.innerHTML = `
      <div class="message-content">
        <div class="message-text">${escapeHtml(content)}</div>
        <div class="message-time">${time}</div>
      </div>
      <div class="message-avatar user-avatar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
          <circle cx="12" cy="7" r="4"></circle>
        </svg>
      </div>
    `;
  } else {
    messageDiv.innerHTML = `
      <div class="message-avatar">
        <img src="assets/logo.png" alt="Lekhantra">
      </div>
      <div class="message-content">
        <div class="message-text">${parseMarkdown(content)}</div>
        <div class="message-actions">
          <button class="action-btn" onclick="copyMessageContent(this)" title="Copy">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
          </button>
          <button class="action-btn" onclick="downloadMessageContent(this)" title="Download">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
          </button>
        </div>
        <div class="message-time">${time}</div>
      </div>
    `;
  }

  elements.messagesContainer.appendChild(messageDiv);

  // Animate in
  messageDiv.style.opacity = '0';
  messageDiv.style.transform = 'translateY(10px)';
  requestAnimationFrame(() => {
    messageDiv.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
    messageDiv.style.opacity = '1';
    messageDiv.style.transform = 'translateY(0)';
  });

  scrollToBottom();
  return messageDiv;
}

// ============================================================================
// Conversation Management
// ============================================================================
async function loadConversations() {
  console.log('[DEBUG] loadConversations called');
  const authHeaders = getAuthHeaders();
  if (!authHeaders) {
    console.log('[DEBUG] No auth headers, cannot load conversations');
    return;
  }

  try {
    console.log('[DEBUG] Sending GET to /conversations');
    const response = await fetch(`${API_BASE_URL}/conversations`, {
      method: 'GET',
      headers: authHeaders
    });

    console.log('[DEBUG] loadConversations response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json();
      console.error('[DEBUG] loadConversations failed:', errorData);
      return;
    }

    const data = await response.json();
    console.log('[DEBUG] loadConversations success:', data);

    if (data.status === 'success') {
      conversations = data.conversations || [];
      console.log('[DEBUG] Loaded', conversations.length, 'conversations');
      renderConversationList();
    }
  } catch (error) {
    console.error('[DEBUG] loadConversations error:', error);
  }
}

function renderConversationList() {
  const conversationList = document.getElementById('conversationList');
  if (!conversationList) return;

  if (conversations.length === 0) {
    conversationList.innerHTML = `
      <div class="empty-conversations">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <p>No conversations yet</p>
      </div>
    `;
    return;
  }

  conversationList.innerHTML = conversations.map(conv => `
    <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}"
         data-id="${conv.id}"
         onclick="selectConversation('${conv.id}')">
      <div class="conversation-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </div>
      <div class="conversation-info">
        <span class="conversation-title">${escapeHtml(conv.title || 'New Chat')}</span>
        <span class="conversation-date">${formatDate(conv.updated_at)}</span>
      </div>
      <button class="conversation-delete" onclick="event.stopPropagation(); deleteConversation('${conv.id}')" title="Delete">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    </div>
  `).join('');
}

function formatDate(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diff = now - date;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString();
}

async function selectConversation(conversationId) {
  if (isProcessing) return;

  currentConversationId = conversationId;
  messageCount = 0;  // Reset counter

  // Update UI
  document.querySelectorAll('.conversation-item').forEach(item => {
    item.classList.toggle('active', item.dataset.id === conversationId);
  });

  // Load conversation messages
  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  try {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
      method: 'GET',
      headers: authHeaders
    });

    if (!response.ok) throw new Error('Failed to load conversation');

    const data = await response.json();
    if (data.status === 'success') {
      // Clear current messages
      clearMessages();

      // Load messages
      if (data.messages && data.messages.length > 0) {
        messageCount = data.messages.length;  // Set correct count
        data.messages.forEach(msg => {
          addMessage(msg.content, msg.role === 'user', false);  // Don't re-save
        });
      }

      // Set current document if available
      if (data.conversation.document_id) {
        currentTextFile = data.conversation.document_id;
        currentDocumentName = data.conversation.title || 'Document';
        if (elements.currentFileLabel) elements.currentFileLabel.textContent = currentDocumentName;
        if (elements.currentStatusLabel) elements.currentStatusLabel.textContent = 'Loaded from history';
        if (elements.headerDocName) elements.headerDocName.textContent = currentDocumentName;
        if (elements.currentDocument) elements.currentDocument.classList.remove('hidden');
        if (elements.generateVivaBtn) elements.generateVivaBtn.disabled = false;
        if (elements.generateExamBtn) elements.generateExamBtn.disabled = false;
      }

      showToast('Conversation loaded', 'success');
    }
  } catch (error) {
    showToast('Failed to load conversation', 'error');
  }
}

async function createNewConversation() {
  console.log('[DEBUG] createNewConversation called');
  const authHeaders = getAuthHeaders();
  console.log('[DEBUG] Auth headers in createNewConversation:', authHeaders ? 'present' : 'MISSING');
  if (!authHeaders) return null;

  try {
    console.log('[DEBUG] Sending POST to /conversations');
    const response = await fetch(`${API_BASE_URL}/conversations`, {
      method: 'POST',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        title: 'New Chat',
        document_id: currentTextFile
      })
    });

    console.log('[DEBUG] Create conversation response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json();
      console.error('[DEBUG] Create conversation failed:', errorData);
      throw new Error('Failed to create conversation');
    }

    const data = await response.json();
    console.log('[DEBUG] Create conversation success:', data);

    // Reload all conversations to ensure proper ordering
    await loadConversations();
    currentConversationId = data.conversation.id;
    messageCount = 0;
    console.log('[DEBUG] Set currentConversationId to:', currentConversationId);
    return data.conversation.id;
  } catch (error) {
    console.error('[DEBUG] createNewConversation error:', error);
    showToast('Failed to create conversation', 'error');
  }
  return null;
}

// Auto-rename conversation based on first user question
async function renameConversation(conversationId, firstQuestion) {
  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  // Create a short title from the question (first 30-40 chars)
  let title = firstQuestion.trim();
  if (title.length > 40) {
    title = title.substring(0, 40) + '...';
  }

  try {
    await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
      method: 'PUT',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ title: title })
    });

    // Update local state
    const conv = conversations.find(c => c.id === conversationId);
    if (conv) {
      conv.title = title;
    }

    // Reload conversations list
    await loadConversations();
  } catch (error) {
    console.error('Failed to rename conversation:', error);
  }
}

// Show delete confirmation modal
function showDeleteConfirmation(conversationId) {
  pendingDeleteId = conversationId;
  elements.deleteModal.classList.remove('hidden');
}

// Hide delete confirmation modal
function hideDeleteConfirmation() {
  pendingDeleteId = null;
  elements.deleteModal.classList.add('hidden');
}

// Called when user clicks delete button
function deleteConversation(conversationId) {
  showDeleteConfirmation(conversationId);
}

// Actually perform the deletion (called from modal)
async function confirmDelete() {
  const conversationId = pendingDeleteId;
  if (!conversationId) return;

  hideDeleteConfirmation();

  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  try {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
      method: 'DELETE',
      headers: authHeaders
    });

    if (!response.ok) throw new Error('Failed to delete conversation');

    // Remove from local state
    conversations = conversations.filter(c => c.id !== conversationId);
    renderConversationList();

    // If this was the current conversation, clear it
    if (currentConversationId === conversationId) {
      currentConversationId = null;
      clearMessages();
    }

    showToast('Conversation deleted', 'success');
  } catch (error) {
    showToast('Failed to delete conversation', 'error');
  }
}

let messageCount = 0;  // Track messages in current conversation

async function saveMessage(content, isUser) {
  console.log('[DEBUG] saveMessage called', { isUser, currentConversationId, messageCount });

  if (!currentConversationId) {
    console.log('[DEBUG] No conversation ID, creating new conversation...');
    const newId = await createNewConversation();
    console.log('[DEBUG] createNewConversation returned:', newId);
    if (!newId) {
      console.error('[DEBUG] Failed to create conversation, aborting save');
      return;
    }
    messageCount = 0;
  }

  const authHeaders = getAuthHeaders();
  console.log('[DEBUG] Auth headers:', authHeaders ? 'present' : 'MISSING');
  if (!authHeaders) {
    console.error('[DEBUG] No auth headers, cannot save message');
    return;
  }

  try {
    console.log('[DEBUG] Saving message to conversation:', currentConversationId);
    const response = await fetch(`${API_BASE_URL}/conversations/${currentConversationId}/messages`, {
      method: 'POST',
      headers: {
        ...authHeaders,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        role: isUser ? 'user' : 'assistant',
        content: content
      })
    });

    console.log('[DEBUG] Save message response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json();
      console.error('[DEBUG] Save message failed:', errorData);
      return;
    }

    const result = await response.json();
    console.log('[DEBUG] Save message success:', result);

    messageCount++;
    console.log('[DEBUG] Message count after save:', messageCount);

    // Auto-rename conversation on first user message
    if (isUser && messageCount === 1) {
      console.log('[DEBUG] First user message, renaming conversation...');
      renameConversation(currentConversationId, content);
    }
  } catch (error) {
    console.error('[DEBUG] Save message error:', error);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function clearMessages() {
  if (!elements.messagesContainer) return;
  elements.messagesContainer.innerHTML = '';
  if (elements.welcomeState) {
    elements.welcomeState.classList.remove('hidden');
  }
}

// ============================================================================
// Copy & Download
// ============================================================================
async function copyMessageContent(button) {
  const messageText = button.closest('.message-content')?.querySelector('.message-text');
  if (!messageText) return;

  const text = messageText.textContent;

  try {
    await navigator.clipboard.writeText(text);
    showToast('Copied to clipboard!', 'success');

    // Visual feedback
    button.classList.add('copied');
    setTimeout(() => button.classList.remove('copied'), 1500);
  } catch (err) {
    showToast('Failed to copy', 'error');
  }
}

async function copyOutput() {
  if (!elements.messagesContainer) return;

  const messages = elements.messagesContainer.querySelectorAll('.message-text');
  const text = Array.from(messages).map(m => m.textContent).join('\n\n---\n\n');

  if (!text) {
    showToast('No content to copy', 'error');
    return;
  }

  try {
    await navigator.clipboard.writeText(text);
    showToast('Conversation copied!', 'success');
  } catch (err) {
    showToast('Failed to copy', 'error');
  }
}

function downloadMessageContent(button) {
  const messageText = button.closest('.message-content')?.querySelector('.message-text');
  if (!messageText) return;

  const text = messageText.textContent;
  downloadText(text, 'lekhantra-response.txt');
}

function downloadOutput() {
  if (!elements.messagesContainer) return;

  const messages = elements.messagesContainer.querySelectorAll('.message-text');
  const text = Array.from(messages).map(m => m.textContent).join('\n\n---\n\n');

  if (!text) {
    showToast('No content to download', 'error');
    return;
  }

  downloadText(text, 'lekhantra-conversation.txt');
}

function downloadText(text, filename) {
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Downloaded!', 'success');
}

// ============================================================================
// Sidebar Toggle
// ============================================================================
function initSidebarToggle() {
  if (!elements.sidebarToggle || !elements.sidebar) return;

  elements.sidebarToggle.addEventListener('click', () => {
    elements.sidebar.classList.toggle('collapsed');
    elements.sidebar.classList.toggle('mobile-open');
  });

  // Close sidebar when clicking outside on mobile
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768 &&
        elements.sidebar.classList.contains('mobile-open') &&
        !elements.sidebar.contains(e.target) &&
        !elements.sidebarToggle.contains(e.target)) {
      elements.sidebar.classList.remove('mobile-open');
    }
  });
}

// ============================================================================
// Auto-resize Textarea
// ============================================================================
function initAutoResize() {
  if (!elements.pdfQuestion) return;

  const resize = () => {
    elements.pdfQuestion.style.height = 'auto';
    elements.pdfQuestion.style.height = Math.min(elements.pdfQuestion.scrollHeight, 200) + 'px';
  };

  elements.pdfQuestion.addEventListener('input', resize);
  elements.pdfQuestion.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  });

  resize();
}

// ============================================================================
// Suggested Prompts
// ============================================================================
function initSuggestedPrompts() {
  const prompts = document.querySelectorAll('.prompt-card');
  prompts.forEach(prompt => {
    prompt.addEventListener('click', () => {
      const text = prompt.dataset.prompt;
      if (elements.pdfQuestion) {
        elements.pdfQuestion.value = text;
        handleSend();
      }
    });
  });
}

// ============================================================================
// Auth Headers
// ============================================================================
function getAuthHeaders() {
  const token = window.lekhantraAuth?.idToken;
  console.log('[DEBUG] getAuthHeaders called, token:', token ? 'present' : 'MISSING');

  if (!token) {
    console.error('[DEBUG] No auth token available');
    showToast('Please sign in first', 'error');
    openAuthModal();
    return null;
  }

  return {
    'Authorization': `Bearer ${token}`
  };
}

// ============================================================================
// Error Handling
// ============================================================================
function getErrorMessage(data) {
  if (data.detail?.message) return data.detail.message;
  if (data.message) return data.message;
  return 'Something went wrong. Please try again.';
}

// ============================================================================
// Format Output
// ============================================================================
function formatOutput(data) {
  if (data.output) return data.output;
  if (data.answer) return data.answer;
  if (data.questions) return data.questions.join('\n\n');
  return JSON.stringify(data, null, 2);
}

// ============================================================================
// Upload PDF
// ============================================================================
async function uploadPDF() {
  const file = elements.pdfInput?.files[0];

  if (!file) {
    showToast('Please select a PDF file', 'error');
    return;
  }

  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  // Show progress
  if (elements.uploadProgress) {
    elements.uploadProgress.classList.remove('hidden');
    elements.progressFilename.textContent = file.name;
    elements.progressPercent.textContent = '0%';
    elements.progressFill.style.width = '0%';
    elements.progressStatus.textContent = 'Uploading...';
  }

  const formData = new FormData();
  formData.append('file', file);

  disableUI(true);

  try {
    // Simulate progress for better UX
    let progress = 0;
    const progressInterval = setInterval(() => {
      if (progress < 85) {
        progress += Math.random() * 15;
        if (elements.progressFill) {
          elements.progressFill.style.width = Math.min(progress, 85) + '%';
          elements.progressPercent.textContent = Math.round(Math.min(progress, 85)) + '%';
        }
      }
    }, 300);

    const response = await fetch(`${API_BASE_URL}/upload-pdf`, {
      method: 'POST',
      headers: authHeaders,
      body: formData
    });

    clearInterval(progressInterval);

    const data = await response.json();

    if (!response.ok) {
      throw new Error(getErrorMessage(data));
    }

    if (data.status === 'success') {
      currentTextFile = data.text_file;
      currentDocumentName = data.original_filename;

      // Update UI
      if (elements.currentFileLabel) elements.currentFileLabel.textContent = data.original_filename;
      if (elements.currentStatusLabel) elements.currentStatusLabel.textContent = `${data.total_characters} characters`;
      if (elements.headerDocName) elements.headerDocName.textContent = data.original_filename;
      if (elements.currentDocument) elements.currentDocument.classList.remove('hidden');

      // Enable action buttons
      if (elements.generateVivaBtn) elements.generateVivaBtn.disabled = false;
      if (elements.generateExamBtn) elements.generateExamBtn.disabled = false;

      // Update progress
      if (elements.progressFill) elements.progressFill.style.width = '100%';
      if (elements.progressPercent) elements.progressPercent.textContent = '100%';
      if (elements.progressStatus) elements.progressStatus.textContent = 'Complete!';

      showToast('PDF uploaded successfully!', 'success');

      // Clear previous messages and show success
      clearMessages();
      addMessage(`Document "${data.original_filename}" has been processed successfully. Extracted ${data.total_characters.toLocaleString()} characters. You can now ask questions or generate study materials.`, false);

      // Hide progress after delay
      setTimeout(() => {
        if (elements.uploadProgress) elements.uploadProgress.classList.add('hidden');
      }, 2000);

    } else {
      throw new Error(data.message || 'Upload failed');
    }

  } catch (error) {
    showToast(error.message || 'Upload failed', 'error');
    if (elements.progressStatus) elements.progressStatus.textContent = 'Failed';
  } finally {
    disableUI(false);
  }
}

// ============================================================================
// Ask PDF
// ============================================================================
async function askPDF() {
  if (!currentTextFile) {
    showToast('Please upload a PDF first', 'error');
    return;
  }

  const question = elements.pdfQuestion?.value.trim();
  if (!question) {
    showToast('Please enter a question', 'error');
    return;
  }

  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  disableUI(true);
  addMessage(question, true, true);  // Save user message
  if (elements.pdfQuestion) elements.pdfQuestion.value = '';
  initAutoResize();

  showTypingIndicator();

  try {
    const response = await fetch(`${API_BASE_URL}/ask-pdf`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        question: question
      })
    });

    const data = await response.json();

    hideTypingIndicator();

    if (!response.ok) {
      throw new Error(getErrorMessage(data));
    }

    addMessage(data.answer || 'I could not find an answer in the document.', false, true);  // Save AI response

  } catch (error) {
    hideTypingIndicator();
    showToast(error.message || 'Failed to get answer', 'error');
    addMessage(`Error: ${error.message}`, false);
  } finally {
    disableUI(false);
  }
}

// ============================================================================
// Generate Viva Questions
// ============================================================================
async function generateViva() {
  if (!currentTextFile) {
    showToast('Please upload a PDF first', 'error');
    return;
  }

  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  let count = parseInt(elements.questionCount?.value) || 5;
  count = Math.max(1, Math.min(10, count));

  disableUI(true);
  showTypingIndicator();

  try {
    const response = await fetch(`${API_BASE_URL}/ai-generate-viva`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        number_of_questions: count
      })
    });

    const data = await response.json();

    hideTypingIndicator();

    if (!response.ok) {
      throw new Error(getErrorMessage(data));
    }

    addMessage(`📚 **Viva Questions** (${count} questions)\n\n${data.output || 'Questions generated successfully.'}`, false);
    showToast('Viva questions generated!', 'success');

  } catch (error) {
    hideTypingIndicator();
    showToast(error.message || 'Failed to generate viva questions', 'error');
  } finally {
    disableUI(false);
  }
}

// ============================================================================
// Generate Exam Questions
// ============================================================================
async function generateExam() {
  if (!currentTextFile) {
    showToast('Please upload a PDF first', 'error');
    return;
  }

  const authHeaders = getAuthHeaders();
  if (!authHeaders) return;

  let count = parseInt(elements.questionCount?.value) || 5;
  count = Math.max(1, Math.min(10, count));

  disableUI(true);
  showTypingIndicator();

  try {
    const response = await fetch(`${API_BASE_URL}/ai-generate-exam`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders
      },
      body: JSON.stringify({
        text_file: currentTextFile,
        number_of_questions: count
      })
    });

    const data = await response.json();

    hideTypingIndicator();

    if (!response.ok) {
      throw new Error(getErrorMessage(data));
    }

    addMessage(`📝 **Exam Questions** (${count} questions)\n\n${data.output || 'Questions generated successfully.'}`, false);
    showToast('Exam questions generated!', 'success');

  } catch (error) {
    hideTypingIndicator();
    showToast(error.message || 'Failed to generate exam questions', 'error');
  } finally {
    disableUI(false);
  }
}

// ============================================================================
// UI State Management
// ============================================================================
function disableUI(disabled) {
  isProcessing = disabled;

  const buttons = [
    elements.uploadBtn,
    elements.sendBtn,
    elements.generateVivaBtn,
    elements.generateExamBtn
  ];

  buttons.forEach(btn => {
    if (btn) btn.disabled = disabled;
  });
}

function handleSend() {
  if (!isProcessing && currentTextFile) {
    askPDF();
  } else if (!isProcessing && !currentTextFile) {
    showToast('Please upload a PDF first', 'error');
  }
}

function clearOutput() {
  clearMessages();
}

function clearDocument() {
  currentTextFile = null;
  currentDocumentName = '';

  if (elements.currentFileLabel) elements.currentFileLabel.textContent = 'No document selected';
  if (elements.currentStatusLabel) elements.currentStatusLabel.textContent = 'Waiting';
  if (elements.headerDocName) elements.headerDocName.textContent = 'No document loaded';
  if (elements.currentDocument) elements.currentDocument.classList.add('hidden');
  if (elements.generateVivaBtn) elements.generateVivaBtn.disabled = true;
  if (elements.generateExamBtn) elements.generateExamBtn.disabled = true;

  clearMessages();
  showToast('Document cleared', 'info');
}

// ============================================================================
// Auth Modal
// ============================================================================
function openAuthModal() {
  if (elements.authModal) elements.authModal.classList.remove('hidden');
}

function closeAuthModal() {
  if (elements.authModal) elements.authModal.classList.add('hidden');
}

// ============================================================================
// Event Listeners
// ============================================================================
function initEventListeners() {
  // Upload
  if (elements.uploadBtn) {
    elements.uploadBtn.addEventListener('click', uploadPDF);
  }

  // Send
  if (elements.sendBtn) {
    elements.sendBtn.addEventListener('click', handleSend);
  }

  // Quick actions
  if (elements.generateVivaBtn) {
    elements.generateVivaBtn.addEventListener('click', generateViva);
  }
  if (elements.generateExamBtn) {
    elements.generateExamBtn.addEventListener('click', generateExam);
  }

  // New chat
  if (elements.newChatBtn) {
    elements.newChatBtn.addEventListener('click', async () => {
      // Reload conversations first to get latest
      await loadConversations();
      // Create new conversation
      const conversationId = await createNewConversation();
      if (conversationId) {
        currentConversationId = conversationId;
        messageCount = 0;
        clearMessages();
        renderConversationList();
        showToast('New chat started', 'success');
      }
    });
  }

  // Copy/Download buttons
  if (elements.copyOutputBtn) {
    elements.copyOutputBtn.addEventListener('click', copyOutput);
  }
  if (elements.downloadOutputBtn) {
    elements.downloadOutputBtn.addEventListener('click', downloadOutput);
  }

  // Auth modal
  const openAuthBtn = document.getElementById('openAuthBtn');
  const authCloseBtn = document.getElementById('authCloseBtn');

  if (openAuthBtn) {
    openAuthBtn.addEventListener('click', openAuthModal);
  }
  if (authCloseBtn) {
    authCloseBtn.addEventListener('click', closeAuthModal);
  }
  if (elements.authModal) {
    elements.authModal.addEventListener('click', (e) => {
      if (e.target === elements.authModal) closeAuthModal();
    });
  }

  // Generator modal close
  const generatorCloseBtn = document.getElementById('generatorCloseBtn');
  if (generatorCloseBtn) {
    generatorCloseBtn.addEventListener('click', () => {
      if (elements.generatorModal) elements.generatorModal.classList.add('hidden');
    });
  }

  // Generator copy/download
  if (elements.generatorCopyBtn) {
    elements.generatorCopyBtn.addEventListener('click', () => {
      const text = elements.generatorResult?.textContent;
      if (text) {
        navigator.clipboard.writeText(text);
        showToast('Copied!', 'success');
      }
    });
  }
  if (elements.generatorDownloadBtn) {
    elements.generatorDownloadBtn.addEventListener('click', () => {
      const text = elements.generatorResult?.textContent;
      if (text) downloadText(text, 'questions.txt');
    });
  }

  // Delete confirmation modal
  if (elements.deleteModal) {
    elements.deleteModal.addEventListener('click', (e) => {
      if (e.target === elements.deleteModal) {
        hideDeleteConfirmation();
      }
    });
  }
  if (elements.deleteConfirmBtn) {
    elements.deleteConfirmBtn.addEventListener('click', confirmDelete);
  }
  if (elements.deleteCancelBtn) {
    elements.deleteCancelBtn.addEventListener('click', hideDeleteConfirmation);
  }

  // File input change
  if (elements.pdfInput) {
    elements.pdfInput.addEventListener('change', () => {
      const file = elements.pdfInput.files[0];
      if (file) {
        const uploadText = elements.dropZone?.querySelector('.upload-text');
        if (uploadText) uploadText.textContent = file.name;
      }
    });
  }

  // Browse button - trigger file input
  const browseBtn = document.getElementById('browseBtn');
  if (browseBtn) {
    browseBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (elements.pdfInput) {
        elements.pdfInput.click();
      }
    });
  }

  // Dropzone click - also trigger file input
  if (elements.dropZone) {
    elements.dropZone.addEventListener('click', (e) => {
      // Don't trigger if clicking the browse button
      if (e.target.id !== 'browseBtn' && !e.target.closest('#browseBtn')) {
        if (elements.pdfInput) {
          elements.pdfInput.click();
        }
      }
    });
  }

  // Home brand
  const homeBrand = document.getElementById('homeBrand');
  if (homeBrand) {
    homeBrand.addEventListener('click', (e) => {
      e.preventDefault();
      window.location.reload();
    });
  }
}

// ============================================================================
// Drag and Drop
// ============================================================================
function initDragDrop() {
  const dropZone = elements.dropZone;
  if (!dropZone) return;

  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
      dropZone.classList.add('drag-over');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, () => {
      dropZone.classList.remove('drag-over');
    }, false);
  });

  dropZone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') {
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(file);
      if (elements.pdfInput) elements.pdfInput.files = dataTransfer.files;

      const uploadText = dropZone.querySelector('.upload-text');
      if (uploadText) uploadText.textContent = file.name;

      showToast('PDF selected! Click Upload to continue.', 'info');
    } else {
      showToast('Please select a PDF file', 'error');
    }
  }, false);
}

// ============================================================================
// Keyboard Shortcuts
// ============================================================================
function initKeyboardShortcuts() {
  document.addEventListener('keydown', (e) => {
    // Escape to close modals
    if (e.key === 'Escape') {
      if (elements.authModal && !elements.authModal.classList.contains('hidden')) {
        closeAuthModal();
      }
      if (elements.generatorModal && !elements.generatorModal.classList.contains('hidden')) {
        elements.generatorModal.classList.add('hidden');
      }
      if (window.innerWidth <= 768 && elements.sidebar?.classList.contains('mobile-open')) {
        elements.sidebar.classList.remove('mobile-open');
      }
    }

    // Ctrl/Cmd + Enter to send
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSend();
    }
  });
}

// ============================================================================
// Initialize
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  initSidebarToggle();
  initAutoResize();
  initDragDrop();
  initKeyboardShortcuts();
  initSuggestedPrompts();

  // Set initial state
  if (elements.generateVivaBtn) elements.generateVivaBtn.disabled = true;
  if (elements.generateExamBtn) elements.generateExamBtn.disabled = true;
});

// Expose functions globally for HTML onclick handlers
window.uploadPDF = uploadPDF;
window.askPDF = askPDF;
window.generateViva = generateViva;
window.generateExam = generateExam;
window.clearOutput = clearOutput;
window.copyOutput = copyOutput;
window.downloadOutput = downloadOutput;
window.copyMessageContent = copyMessageContent;
window.downloadMessageContent = downloadMessageContent;
