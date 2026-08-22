import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
  EmailAuthProvider,
  reauthenticateWithCredential,
  updatePassword
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

// Firebase Configuration
const firebaseConfig = {
  apiKey: "AIzaSyD4GXOLThiDKyjIusmgfmAr3NsdP5kGyjE",
  authDomain: "lekhantra.firebaseapp.com",
  projectId: "lekhantra",
  storageBucket: "lekhantra.firebasestorage.app",
  messagingSenderId: "308583945285",
  appId: "1:308583945285:web:0eb7c4c931ba914b643f2c",
  measurementId: "G-VTQWT2Y8LQ"
};

// Initialize Firebase
let app;
let auth;
let googleProvider;
let firebaseReady = false;

try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  googleProvider = new GoogleAuthProvider();
  firebaseReady = true;
  console.log("Firebase initialized successfully");
} catch (error) {
  console.error("Firebase initialization error:", error);
}

// Global auth state
window.lekhantraAuth = {
  currentUser: null,
  idToken: null,
  isAuthenticated: false
};

// Helper functions
function getFirstName(user) {
  const displayName = user?.displayName || "";
  if (displayName.trim()) {
    return displayName.trim().split(" ")[0];
  }
  return user?.email?.split("@")[0] || "User";
}

function getFriendlyError(error) {
  const code = error.code || "";
  if (code.includes("auth/invalid-email")) return "Please enter a valid email address.";
  if (code.includes("auth/missing-password")) return "Please enter your password.";
  if (code.includes("auth/weak-password")) return "Password should be at least 6 characters.";
  if (code.includes("auth/email-already-in-use")) return "This email already has an account. Please sign in.";
  if (code.includes("auth/invalid-credential") || code.includes("auth/wrong-password")) return "Incorrect email or password.";
  if (code.includes("auth/user-not-found")) return "No account found with this email.";
  if (code.includes("auth/popup-closed-by-user")) return "Google sign-in was cancelled.";
  if (code.includes("auth/network-request-failed")) return "Network error. Please check your connection.";
  return "Authentication failed. Please try again.";
}

// Update UI based on auth state
function updateAuthUI(user) {
  console.log('[FIREBASE] updateAuthUI called', { user: user ? 'present' : 'null' });

  const openAuthBtn = document.getElementById("openAuthBtn");
  const userMenu = document.getElementById("userMenu");
  const userAvatar = document.getElementById("userAvatar");
  const userGreeting = document.getElementById("userGreeting");
  const dropdownAvatar = document.getElementById("dropdownAvatar");
  const dropdownName = document.getElementById("dropdownName");
  const dropdownEmail = document.getElementById("dropdownEmail");

  if (!user) {
    window.lekhantraAuth.currentUser = null;
    window.lekhantraAuth.idToken = null;
    window.lekhantraAuth.isAuthenticated = false;

    console.log('[FIREBASE] User logged out');

    if (openAuthBtn) {
      openAuthBtn.classList.remove("hidden");
      openAuthBtn.style.display = "";
    }
    if (userMenu) userMenu.classList.add("hidden");
  } else {
    user.getIdToken().then((token) => {
      console.log('[FIREBASE] Got ID token, length:', token?.length);
      window.lekhantraAuth.currentUser = {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        photoURL: user.photoURL
      };
      window.lekhantraAuth.idToken = token;
      window.lekhantraAuth.isAuthenticated = true;

      console.log('[FIREBASE] User logged in:', { uid: user.uid, email: user.email });

      if (openAuthBtn) {
        openAuthBtn.classList.add("hidden");
        openAuthBtn.style.display = "none";
      }
      if (userMenu) {
        userMenu.classList.remove("hidden");
      }

      if (userAvatar) {
        userAvatar.src = user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(getFirstName(user))}&background=5b1f28&color=fff&size=64`;
      }
      if (userGreeting) {
        userGreeting.textContent = `Hey, ${getFirstName(user)}`;
      }
      if (dropdownAvatar) {
        dropdownAvatar.src = user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(getFirstName(user))}&background=5b1f28&color=fff&size=64`;
      }
      if (dropdownName) dropdownName.textContent = user.displayName || getFirstName(user);
      if (dropdownEmail) dropdownEmail.textContent = user.email || "";
    });
  }
}

// Auth functions
async function loginWithGoogle() {
  if (!firebaseReady || !auth) {
    alert("Authentication not initialized. Please refresh the page.");
    return;
  }

  const authMessage = document.getElementById("authMessage");
  if (authMessage) authMessage.textContent = "Opening Google sign-in...";

  try {
    await signInWithPopup(auth, googleProvider);
    closeAuthModal();
  } catch (error) {
    console.error("Google sign-in error:", error);
    if (authMessage) authMessage.textContent = getFriendlyError(error);
  }
}

async function signInWithEmail() {
  if (!firebaseReady || !auth) {
    alert("Authentication not initialized. Please refresh the page.");
    return;
  }

  const emailInput = document.getElementById("authEmail");
  const passwordInput = document.getElementById("authPassword");
  const authMessage = document.getElementById("authMessage");

  const email = emailInput?.value?.trim();
  const password = passwordInput?.value;

  if (!email || !password) {
    if (authMessage) authMessage.textContent = "Please enter both email and password.";
    return;
  }

  if (authMessage) authMessage.textContent = "Signing in...";

  try {
    await signInWithEmailAndPassword(auth, email, password);
    closeAuthModal();
  } catch (error) {
    console.error("Email sign-in error:", error);
    if (authMessage) authMessage.textContent = getFriendlyError(error);
  }
}

async function createAccountWithEmail() {
  if (!firebaseReady || !auth) {
    alert("Authentication not initialized. Please refresh the page.");
    return;
  }

  const nameInput = document.getElementById("authFullName");
  const emailInput = document.getElementById("authEmail");
  const passwordInput = document.getElementById("authPassword");
  const authMessage = document.getElementById("authMessage");

  const fullName = nameInput?.value?.trim();
  const email = emailInput?.value?.trim();
  const password = passwordInput?.value;

  if (!fullName || !email || !password) {
    if (authMessage) authMessage.textContent = "Please enter full name, email, and password.";
    return;
  }

  if (password.length < 6) {
    if (authMessage) authMessage.textContent = "Password must be at least 6 characters.";
    return;
  }

  if (authMessage) authMessage.textContent = "Creating account...";

  try {
    const userCredential = await createUserWithEmailAndPassword(auth, email, password);
    await updateProfile(userCredential.user, { displayName: fullName });
    await userCredential.user.reload();
    closeAuthModal();
  } catch (error) {
    console.error("Account creation error:", error);
    if (authMessage) authMessage.textContent = getFriendlyError(error);
  }
}

async function signOutUser() {
  if (!auth) return;
  try {
    await signOut(auth);
    const profileDropdown = document.getElementById("profileDropdown");
    if (profileDropdown) profileDropdown.classList.add("hidden");

    // Refresh the page after sign out
    window.location.reload();
  } catch (error) {
    console.error("Sign-out error:", error);
  }
}

// Update user profile (name and photo)
async function updateUserProfile(displayName, photoFile) {
  if (!firebaseReady || !auth) {
    throw new Error("Authentication not initialized");
  }

  const user = auth.currentUser;
  if (!user) {
    throw new Error("No user logged in");
  }

  try {
    const updates = {};

    // Update display name
    if (displayName) {
      updates.displayName = displayName;
    }

    // Update photo URL if a new file was selected
    if (photoFile) {
      // For photo upload, we'd typically upload to Firebase Storage
      // For now, we'll use a data URL approach for simplicity
      updates.photoURL = await fileToDataUrl(photoFile);
    }

    if (Object.keys(updates).length > 0) {
      await updateProfile(user, updates);
    }

    // Refresh the user token
    await user.reload();

    // Update global auth state
    window.lekhantraAuth.currentUser = {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      photoURL: user.photoURL
    };

    // Get fresh token
    const token = await user.getIdToken();
    window.lekhantraAuth.idToken = token;

    return true;
  } catch (error) {
    console.error("Profile update error:", error);
    throw error;
  }
}

// Change user password
async function changeUserPassword(currentPassword, newPassword) {
  if (!firebaseReady || !auth) {
    throw new Error("Authentication not initialized");
  }

  const user = auth.currentUser;
  if (!user) {
    throw new Error("No user logged in");
  }

  // Check if user signed in with email/password
  if (user.providerData.length === 0 || user.providerData[0].providerId !== 'password') {
    throw new Error("Password can only be changed for email/password accounts");
  }

  try {
    // Re-authenticate user first
    const credential = EmailAuthProvider.credential(user.email, currentPassword);
    await reauthenticateWithCredential(user, credential);

    // Update password
    await updatePassword(user, newPassword);

    return true;
  } catch (error) {
    console.error("Password change error:", error);
    if (error.code === 'auth/wrong-password') {
      throw new Error("Current password is incorrect");
    }
    throw error;
  }
}

// Helper function to convert file to data URL
function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function openAuthModal() {
  const authModal = document.getElementById("authModal");
  const authMessage = document.getElementById("authMessage");
  if (authModal) {
    authModal.classList.remove("hidden");
  }
  if (authMessage) authMessage.textContent = "";
  setTimeout(() => document.getElementById("authEmail")?.focus(), 100);
}

function closeAuthModal() {
  const authModal = document.getElementById("authModal");
  if (authModal) {
    authModal.classList.add("hidden");
  }
}

// Event listeners
function setupEventListeners() {
  // Open auth modal
  const openAuthBtn = document.getElementById("openAuthBtn");
  if (openAuthBtn) {
    openAuthBtn.addEventListener("click", openAuthModal);
  }

  // Close auth modal
  const authCloseBtn = document.getElementById("authCloseBtn");
  if (authCloseBtn) {
    authCloseBtn.addEventListener("click", closeAuthModal);
  }

  // Close modal on backdrop click
  const authModal = document.getElementById("authModal");
  if (authModal) {
    authModal.addEventListener("click", (event) => {
      if (event.target === authModal) {
        closeAuthModal();
      }
    });
  }

  // Google sign-in
  const googleContinueBtn = document.getElementById("googleContinueBtn");
  if (googleContinueBtn) {
    googleContinueBtn.addEventListener("click", loginWithGoogle);
  }

  // Email sign-in
  const emailSignInBtn = document.getElementById("emailSignInBtn");
  if (emailSignInBtn) {
    emailSignInBtn.addEventListener("click", signInWithEmail);
  }

  // Create account
  const emailCreateBtn = document.getElementById("emailCreateBtn");
  if (emailCreateBtn) {
    emailCreateBtn.addEventListener("click", createAccountWithEmail);
  }

  // Enter key for password
  const authPassword = document.getElementById("authPassword");
  if (authPassword) {
    authPassword.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        signInWithEmail();
      }
    });
  }

  // Logout
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", signOutUser);
  }

  // Profile dropdown
  const profileTrigger = document.getElementById("profileTrigger");
  const profileDropdown = document.getElementById("profileDropdown");
  if (profileTrigger && profileDropdown) {
    profileTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      profileDropdown.classList.toggle("hidden");
    });
  }

  // Close dropdown on outside click
  document.addEventListener("click", () => {
    if (profileDropdown) {
      profileDropdown.classList.add("hidden");
    }
  });

  // Prevent dropdown click from closing
  if (profileDropdown) {
    profileDropdown.addEventListener("click", (event) => {
      event.stopPropagation();
    });
  }

  // Escape key to close modal
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAuthModal();
    }
  });
}

// Initialize when DOM is ready
function init() {
  console.log('[FIREBASE] init called');

  if (!firebaseReady) {
    console.error('[FIREBASE] Firebase not ready, will retry...');
    setTimeout(init, 500);
    return;
  }

  setupEventListeners();

  // Listen for auth state changes
  onAuthStateChanged(auth, (user) => {
    console.log('[FIREBASE] Auth state changed:', user ? 'logged in' : 'logged out');
    updateAuthUI(user);
    // Load conversations when user logs in
    if (user && typeof loadConversations === 'function') {
      console.log('[FIREBASE] Calling loadConversations after login');
      loadConversations();
    }
  });

  console.log('[FIREBASE] Firebase Auth initialized');
}

// Start initialization
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

// Expose functions globally for profile management
window.updateUserProfile = updateUserProfile;
window.changeUserPassword = changeUserPassword;
