/**
 * Lekhantra Profile Page
 * Complete settings and profile management
 */

// API Base URL Configuration
const isLocalhost = window.location.hostname === 'localhost' ||
                    window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocalhost ? 'http://127.0.0.1:8000' : 'https://lekhantra-backend.onrender.com';

// Auth state
let currentUser = null;
let idToken = null;

// DOM Elements
const elements = {
  profileName: document.getElementById('profileName'),
  profileEmail: document.getElementById('profileEmail'),
  profileAvatarImg: document.getElementById('profileAvatarImg'),
  avatarPlaceholder: document.getElementById('avatarPlaceholder'),
  memberSince: document.getElementById('memberSince'),
  lastLogin: document.getElementById('lastLogin'),
  profileProvider: document.getElementById('profileProvider'),
  displayName: document.getElementById('displayName'),
  emailDisplay: document.getElementById('emailDisplay'),
  saveNameBtn: document.getElementById('saveNameBtn'),
  documentsList: document.getElementById('documentsList'),
  showSourcesToggle: document.getElementById('showSourcesToggle'),
  confirmModal: document.getElementById('confirmModal'),
  confirmTitle: document.getElementById('confirmTitle'),
  confirmMessage: document.getElementById('confirmMessage'),
  confirmAction: document.getElementById('confirmAction'),
  confirmCancel: document.getElementById('confirmCancel'),
};

// Quick stats
const quickStats = {
  docs: document.getElementById('quickDocs'),
  chats: document.getElementById('quickChats'),
  questions: document.getElementById('quickQuestions'),
};

// Statistics
const stats = {
  documents: document.getElementById('statDocuments'),
  conversations: document.getElementById('statConversations'),
  questions: document.getElementById('statQuestions'),
  responses: document.getElementById('statResponses'),
  storage: document.getElementById('statStorage'),
  lastUpload: document.getElementById('statLastUpload'),
};

// Pending confirm action
let pendingConfirmAction = null;

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
// Authentication
// ============================================================================
async function checkAuth() {
  return new Promise((resolve) => {
    if (typeof firebase !== 'undefined' && firebase.auth()) {
      firebase.auth().onAuthStateChanged(async (user) => {
        if (user) {
          try {
            idToken = await user.getIdToken();
            currentUser = {
              uid: user.uid,
              email: user.email,
              displayName: user.displayName || user.email?.split('@')[0],
              photoURL: user.photoURL,
              provider: user.providerData[0]?.providerId || 'email',
              metadata: user.metadata,
            };
            resolve(true);
          } catch (error) {
            console.error('Auth error:', error);
            resolve(false);
          }
        } else {
          // Redirect to main page if not logged in
          window.location.href = '/';
          resolve(false);
        }
      });
    } else {
      console.error('Firebase not loaded');
      resolve(false);
    }
  });
}

function getAuthHeaders() {
  if (!idToken) return null;
  return {
    'Authorization': `Bearer ${idToken}`,
  };
}

// ============================================================================
// API Helpers
// ============================================================================
async function apiGet(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    headers: getAuthHeaders(),
  });
  return response.json();
}

async function apiPost(endpoint, body = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(body),
  });
  return response.json();
}

async function apiPut(endpoint, body = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(body),
  });
  return response.json();
}

async function apiDelete(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  return response.json();
}

// ============================================================================
// Profile Data
// ============================================================================
async function loadProfileData() {
  try {
    const data = await apiGet('/profile');

    if (data.status !== 'success') {
      throw new Error('Failed to load profile');
    }

    // Update profile header
    const profile = data.profile;
    const statistics = data.statistics;
    const preferences = data.preferences;

    // Profile info
    if (elements.profileName) {
      elements.profileName.textContent = profile.display_name || 'User';
    }
    if (elements.profileEmail) {
      elements.profileEmail.textContent = profile.email || '';
    }
    if (elements.displayName) {
      elements.displayName.value = profile.display_name || '';
    }
    if (elements.emailDisplay) {
      elements.emailDisplay.value = profile.email || '';
    }
    if (elements.profileProvider) {
      elements.profileProvider.textContent = formatProvider(profile.provider);
    }

    // Avatar
    if (profile.photo_url && elements.profileAvatarImg) {
      elements.profileAvatarImg.src = profile.photo_url;
      elements.profileAvatarImg.style.display = 'block';
      elements.avatarPlaceholder.style.display = 'none';
    } else if (profile.display_name) {
      elements.avatarPlaceholder.innerHTML = getInitialsHTML(profile.display_name);
    }

    // Member since
    if (profile.member_since && elements.memberSince) {
      elements.memberSince.textContent = formatDate(profile.member_since);
    }

    // Last login (simulated with current time)
    if (elements.lastLogin) {
      elements.lastLogin.textContent = 'Just now';
    }

    // Update statistics
    updateStatistics(statistics);

    // Update preferences
    updatePreferencesUI(preferences);

  } catch (error) {
    console.error('Error loading profile:', error);
    showToast('Failed to load profile data', 'error');
  }
}

function updateStatistics(statsData) {
  // Quick stats
  if (quickStats.docs) quickStats.docs.textContent = statsData.documents_uploaded || 0;
  if (quickStats.chats) quickStats.chats.textContent = statsData.conversations_created || 0;
  if (quickStats.questions) quickStats.questions.textContent = statsData.questions_asked || 0;

  // Full stats
  if (stats.documents) stats.documents.textContent = statsData.documents_uploaded || 0;
  if (stats.conversations) stats.conversations.textContent = statsData.conversations_created || 0;
  if (stats.questions) stats.questions.textContent = statsData.questions_asked || 0;
  if (stats.responses) stats.responses.textContent = statsData.ai_responses || 0;
  if (stats.storage) stats.storage.textContent = `${statsData.storage_used_mb || 0} MB`;

  if (stats.lastUpload) {
    stats.lastUpload.textContent = statsData.last_upload_date
      ? formatDate(statsData.last_upload_date)
      : 'Never';
  }
}

function updatePreferencesUI(prefs) {
  // Response style
  document.querySelectorAll('[data-pref="response_style"]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.value === (prefs.response_style || 'balanced'));
  });

  // Retrieval depth
  document.querySelectorAll('[data-pref="retrieval_depth"]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.value === String(prefs.retrieval_depth || 5));
  });

  // Show sources
  if (elements.showSourcesToggle) {
    elements.showSourcesToggle.checked = prefs.show_sources !== false;
  }
}

function formatProvider(provider) {
  const providers = {
    'google.com': 'Google',
    'password': 'Email',
    'email': 'Email',
    'github.com': 'GitHub',
  };
  return providers[provider] || provider;
}

function formatDate(dateStr) {
  if (!dateStr) return '--';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function getInitialsHTML(name) {
  const initials = name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
  return `<span style="font-size: 24px; font-weight: 600; color: var(--color-primary);">${initials}</span>`;
}

// ============================================================================
// Documents
// ============================================================================
async function loadDocuments() {
  try {
    const data = await apiGet('/profile/documents');

    if (data.status !== 'success') {
      throw new Error('Failed to load documents');
    }

    renderDocuments(data.documents || []);

  } catch (error) {
    console.error('Error loading documents:', error);
    showToast('Failed to load documents', 'error');
    renderDocuments([]);
  }
}

function renderDocuments(documents) {
  if (!elements.documentsList) return;

  if (documents.length === 0) {
    elements.documentsList.innerHTML = `
      <div class="empty-documents">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
        <p>No documents uploaded yet</p>
      </div>
    `;
    return;
  }

  elements.documentsList.innerHTML = documents.map(doc => `
    <div class="document-card" data-doc-id="${escapeHtml(doc.document_id || '')}">
      <div class="document-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
        </svg>
      </div>
      <div class="document-info">
        <span class="document-name">${escapeHtml(doc.filename || 'Unknown')}</span>
        <div class="document-meta">
          <span>${doc.chunk_count || 0} chunks</span>
          <span class="document-status indexed">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
            Indexed
          </span>
        </div>
      </div>
      <div class="document-actions">
        <button class="document-action reindex" title="Re-index" onclick="reindexDocument('${escapeHtml(doc.document_id || '')}')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6"></path>
            <path d="M1 20v-6h6"></path>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
        </button>
        <button class="document-action delete" title="Delete" onclick="confirmDeleteDocument('${escapeHtml(doc.document_id || '')}', '${escapeHtml(doc.filename || 'this document')}')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>
  `).join('');
}

// ============================================================================
// Actions
// ============================================================================
async function saveDisplayName() {
  const name = elements.displayName?.value.trim();
  if (!name) {
    showToast('Please enter a name', 'error');
    return;
  }

  elements.saveNameBtn.disabled = true;
  elements.saveNameBtn.textContent = 'Saving...';

  try {
    const data = await apiPut('/profile', { display_name: name });

    if (data.status === 'success') {
      elements.profileName.textContent = name;
      showToast('Name updated successfully', 'success');
    } else {
      throw new Error(data.message || 'Failed to save');
    }
  } catch (error) {
    console.error('Error saving name:', error);
    showToast('Failed to save name', 'error');
  } finally {
    elements.saveNameBtn.disabled = false;
    elements.saveNameBtn.textContent = 'Save';
  }
}

async function savePreference(prefType, value) {
  try {
    const body = {};
    if (prefType === 'response_style') {
      body.response_style = value;
    } else if (prefType === 'retrieval_depth') {
      body.retrieval_depth = parseInt(value);
    } else if (prefType === 'show_sources') {
      body.show_sources = value;
    }

    const data = await apiPut('/profile/preferences', body);

    if (data.status === 'success') {
      showToast('Preference saved', 'success');
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error saving preference:', error);
    showToast('Failed to save preference', 'error');
  }
}

async function reindexDocument(docId) {
  showToast('Re-indexing document...', 'info');
  try {
    const data = await apiPost(`/documents/${docId}/reindex`);

    if (data.status === 'success') {
      showToast('Document re-indexed successfully', 'success');
      await loadDocuments();
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error re-indexing:', error);
    showToast('Failed to re-index document', 'error');
  }
}

async function deleteDocument(docId) {
  try {
    const data = await apiDelete(`/profile/documents/${docId}`);

    if (data.status === 'success') {
      showToast('Document deleted', 'success');
      await loadDocuments();
      await loadProfileData();
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error deleting document:', error);
    showToast('Failed to delete document', 'error');
  }
}

async function exportData() {
  showToast('Preparing export...', 'info');

  try {
    const data = await apiGet('/profile/export');

    if (data.status === 'success') {
      const blob = new Blob([JSON.stringify(data.export, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `lekhantra-export-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Data exported successfully', 'success');
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error exporting:', error);
    showToast('Failed to export data', 'error');
  }
}

async function deleteAllConversations() {
  try {
    const data = await apiDelete('/profile/conversations');

    if (data.status === 'success') {
      showToast('All conversations deleted', 'success');
      await loadProfileData();
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error deleting conversations:', error);
    showToast('Failed to delete conversations', 'error');
  }
}

async function deleteAllDocuments() {
  try {
    const data = await apiDelete('/profile/documents');

    if (data.status === 'success') {
      showToast('All documents deleted', 'success');
      await loadDocuments();
      await loadProfileData();
    } else {
      throw new Error(data.message);
    }
  } catch (error) {
    console.error('Error deleting documents:', error);
    showToast('Failed to delete documents', 'error');
  }
}

// ============================================================================
// Confirmation Modal
// ============================================================================
function showConfirmModal(title, message, onConfirm) {
  elements.confirmTitle.textContent = title;
  elements.confirmMessage.textContent = message;
  pendingConfirmAction = onConfirm;
  elements.confirmModal.classList.remove('hidden');
}

function hideConfirmModal() {
  elements.confirmModal.classList.add('hidden');
  pendingConfirmAction = null;
}

function confirmDeleteDocument(docId, filename) {
  showConfirmModal(
    'Delete Document',
    `Are you sure you want to delete "${filename}"? This action cannot be undone.`,
    () => deleteDocument(docId)
  );
}

function confirmDeleteAllConversations() {
  showConfirmModal(
    'Delete All Conversations',
    'Are you sure you want to delete all conversations? This action cannot be undone.',
    deleteAllConversations
  );
}

function confirmDeleteAllDocuments() {
  showConfirmModal(
    'Delete All Documents',
    'Are you sure you want to delete all documents? This will remove all PDFs and embeddings. This action cannot be undone.',
    deleteAllDocuments
  );
}

// ============================================================================
// Utility
// ============================================================================
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================================
// Event Listeners
// ============================================================================
function initEventListeners() {
  // Save name
  elements.saveNameBtn?.addEventListener('click', saveDisplayName);

  // Preference buttons
  document.querySelectorAll('.option-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const pref = btn.dataset.pref;
      const value = btn.dataset.value;

      // Update UI
      document.querySelectorAll(`[data-pref="${pref}"]`).forEach(b => {
        b.classList.remove('active');
      });
      btn.classList.add('active');

      // Save
      savePreference(pref, value);
    });
  });

  // Show sources toggle
  elements.showSourcesToggle?.addEventListener('change', (e) => {
    savePreference('show_sources', e.target.checked);
  });

  // Privacy buttons
  document.getElementById('exportDataBtn')?.addEventListener('click', exportData);
  document.getElementById('deleteAllConversationsBtn')?.addEventListener('click', confirmDeleteAllConversations);
  document.getElementById('deleteAllDocsBtn')?.addEventListener('click', confirmDeleteAllDocuments);
  document.getElementById('deleteAccountBtn')?.addEventListener('click', () => {
    showToast('Please contact support to delete your account', 'info');
  });

  // Confirm modal
  elements.confirmCancel?.addEventListener('click', hideConfirmModal);
  elements.confirmAction?.addEventListener('click', () => {
    if (pendingConfirmAction) {
      pendingConfirmAction();
    }
    hideConfirmModal();
  });
  elements.confirmModal?.addEventListener('click', (e) => {
    if (e.target === elements.confirmModal) {
      hideConfirmModal();
    }
  });
}

// ============================================================================
// Initialize
// ============================================================================
async function init() {
  const isAuthenticated = await checkAuth();
  if (!isAuthenticated) return;

  initEventListeners();

  // Load all data in parallel
  await Promise.all([
    loadProfileData(),
    loadDocuments(),
  ]);
}

// Start
init();

// Expose functions globally
window.reindexDocument = reindexDocument;
window.confirmDeleteDocument = confirmDeleteDocument;
