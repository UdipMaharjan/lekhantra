import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile
} from "https://www.gstatic.com/firebasejs/11.0.1/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyD4GXOLThiDKyjIusmgfmAr3NsdP5kGyjE",
  authDomain: "lekhantra.firebaseapp.com",
  projectId: "lekhantra",
  storageBucket: "lekhantra.firebasestorage.app",
  messagingSenderId: "308583945285",
  appId: "1:308583945285:web:0eb7c4c931ba914b643f2c",
  measurementId: "G-VTQWT2Y8LQ"
};

// Initialize Firebase only if not already initialized
let app;
let auth;
let googleProvider;

try {
  if (!firebase.apps.length) {
    app = initializeApp(firebaseConfig);
  } else {
    app = firebase.apps[0];
  }
  auth = getAuth(app);
  googleProvider = new GoogleAuthProvider();
} catch (error) {
  console.error("Firebase initialization error:", error);
}

// Global auth state object
window.lekhantraAuth = {
  currentUser: null,
  idToken: null,
  isAuthenticated: false
};

// DOM Elements - wait for DOM to be ready
let openAuthBtn;
let authModal;
let authCloseBtn;
let authFullName;
let authEmail;
let authPassword;
let emailSignInBtn;
let emailCreateBtn;
let googleContinueBtn;
let authMessage;
let userMenu;
let userAvatar;
let userGreeting;
let profileTrigger;
let profileDropdown;
let manageProfileBtn;
let logoutBtn;
let dropdownAvatar;
let dropdownName;
let dropdownEmail;

// Initialize DOM elements
function initElements() {
  openAuthBtn = document.getElementById("openAuthBtn");
  authModal = document.getElementById("authModal");
  authCloseBtn = document.getElementById("authCloseBtn");
  authFullName = document.getElementById("authFullName");
  authEmail = document.getElementById("authEmail");
  authPassword = document.getElementById("authPassword");
  emailSignInBtn = document.getElementById("emailSignInBtn");
  emailCreateBtn = document.getElementById("emailCreateBtn");
  googleContinueBtn = document.getElementById("googleContinueBtn");
  authMessage = document.getElementById("authMessage");
  userMenu = document.getElementById("userMenu");
  userAvatar = document.getElementById("userAvatar");
  userGreeting = document.getElementById("userGreeting");
  profileTrigger = document.getElementById("profileTrigger");
  profileDropdown = document.getElementById("profileDropdown");
  manageProfileBtn = document.getElementById("manageProfileBtn");
  logoutBtn = document.getElementById("logoutBtn");
  dropdownAvatar = document.getElementById("dropdownAvatar");
  dropdownName = document.getElementById("dropdownName");
  dropdownEmail = document.getElementById("dropdownEmail");
}

// Modal functions
function openAuthModal() {
  if (!authModal) return;
  authModal.classList.remove("hidden");
  if (authMessage) authMessage.textContent = "";
  if (authEmail) authEmail.focus();
}

function closeAuthModal() {
  if (!authModal) return;
  authModal.classList.add("hidden");
  if (authMessage) authMessage.textContent = "";
}

// User helpers
function getFirstName(user) {
  const displayName = user?.displayName || "";
  if (displayName.trim()) {
    return displayName.trim().split(" ")[0];
  }
  return user?.email?.split("@")[0] || "User";
}

function getUserInitials(user) {
  const displayName = user?.displayName || user?.email || "U";
  return displayName.charAt(0).toUpperCase();
}

// Error messages
function getFriendlyError(error) {
  const code = error.code || "";

  if (code.includes("auth/invalid-email")) {
    return "Please enter a valid email address.";
  }
  if (code.includes("auth/missing-password")) {
    return "Please enter your password.";
  }
  if (code.includes("auth/weak-password")) {
    return "Password should be at least 6 characters.";
  }
  if (code.includes("auth/email-already-in-use")) {
    return "This email already has an account. Please sign in.";
  }
  if (code.includes("auth/invalid-credential") || code.includes("auth/wrong-password")) {
    return "Incorrect email or password.";
  }
  if (code.includes("auth/user-not-found")) {
    return "No account found with this email.";
  }
  if (code.includes("auth/popup-closed-by-user")) {
    return "Google sign-in was cancelled.";
  }
  if (code.includes("auth/network-request-failed")) {
    return "Network error. Please check your connection.";
  }

  return "Authentication failed. Please try again.";
}

// Update UI based on auth state
function updateAuthUI(user) {
  if (!user) {
    // Not logged in
    window.lekhantraAuth.currentUser = null;
    window.lekhantraAuth.idToken = null;
    window.lekhantraAuth.isAuthenticated = false;

    if (openAuthBtn) {
      openAuthBtn.classList.remove("hidden");
      openAuthBtn.style.display = "";
    }

    if (userMenu) {
      userMenu.classList.add("hidden");
      userMenu.style.display = "none";
    }
  } else {
    // Logged in
    user.getIdToken().then((token) => {
      window.lekhantraAuth.currentUser = {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        photoURL: user.photoURL
      };
      window.lekhantraAuth.idToken = token;
      window.lekhantraAuth.isAuthenticated = true;

      if (openAuthBtn) {
        openAuthBtn.classList.add("hidden");
        openAuthBtn.style.display = "none";
      }

      if (userMenu) {
        userMenu.classList.remove("hidden");
        userMenu.style.display = "";
      }

      if (userAvatar) {
        if (user.photoURL) {
          userAvatar.src = user.photoURL;
          userAvatar.style.display = "";
        } else {
          userAvatar.style.display = "none";
        }
      }

      if (userGreeting) {
        userGreeting.textContent = `Hey, ${getFirstName(user)}`;
      }

      // Update dropdown
      if (dropdownAvatar) {
        dropdownAvatar.src = user.photoURL || `https://ui-avatars.com/api/?name=${encodeURIComponent(getFirstName(user))}&background=5b1f28&color=fff`;
      }
      if (dropdownName) {
        dropdownName.textContent = user.displayName || getFirstName(user);
      }
      if (dropdownEmail) {
        dropdownEmail.textContent = user.email || "";
      }
    });
  }
}

// Auth functions
async function loginWithGoogle() {
  if (!auth || !googleProvider) {
    if (authMessage) authMessage.textContent = "Authentication not initialized. Please refresh the page.";
    return;
  }

  try {
    if (authMessage) authMessage.textContent = "Opening Google sign-in...";
    await signInWithPopup(auth, googleProvider);
    closeAuthModal();
  } catch (error) {
    console.error("Google sign-in error:", error);
    if (authMessage) authMessage.textContent = getFriendlyError(error);
  }
}

async function signInWithEmail() {
  if (!auth) {
    if (authMessage) authMessage.textContent = "Authentication not initialized. Please refresh the page.";
    return;
  }

  const email = authEmail?.value?.trim();
  const password = authPassword?.value;

  if (!email || !password) {
    if (authMessage) authMessage.textContent = "Please enter both email and password.";
    return;
  }

  try {
    if (authMessage) authMessage.textContent = "Signing in...";
    await signInWithEmailAndPassword(auth, email, password);
    closeAuthModal();
  } catch (error) {
    console.error("Email sign-in error:", error);
    if (authMessage) authMessage.textContent = getFriendlyError(error);
  }
}

async function createAccountWithEmail() {
  if (!auth) {
    if (authMessage) authMessage.textContent = "Authentication not initialized. Please refresh the page.";
    return;
  }

  const fullName = authFullName?.value?.trim();
  const email = authEmail?.value?.trim();
  const password = authPassword?.value;

  if (!fullName || !email || !password) {
    if (authMessage) authMessage.textContent = "Please enter full name, email, and password.";
    return;
  }

  if (password.length < 6) {
    if (authMessage) authMessage.textContent = "Password must be at least 6 characters.";
    return;
  }

  try {
    if (authMessage) authMessage.textContent = "Creating account...";
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
    if (profileDropdown) profileDropdown.classList.add("hidden");
  } catch (error) {
    console.error("Sign-out error:", error);
  }
}

// Event listeners
function setupEventListeners() {
  // Open auth modal
  if (openAuthBtn) {
    openAuthBtn.addEventListener("click", openAuthModal);
  }

  // Close auth modal
  if (authCloseBtn) {
    authCloseBtn.addEventListener("click", closeAuthModal);
  }

  // Close modal on backdrop click
  if (authModal) {
    authModal.addEventListener("click", (event) => {
      if (event.target === authModal) {
        closeAuthModal();
      }
    });
  }

  // Google sign-in
  if (googleContinueBtn) {
    googleContinueBtn.addEventListener("click", loginWithGoogle);
  }

  // Email sign-in
  if (emailSignInBtn) {
    emailSignInBtn.addEventListener("click", signInWithEmail);
  }

  // Create account
  if (emailCreateBtn) {
    emailCreateBtn.addEventListener("click", createAccountWithEmail);
  }

  // Enter key for password
  if (authPassword) {
    authPassword.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        signInWithEmail();
      }
    });
  }

  // Logout
  if (logoutBtn) {
    logoutBtn.addEventListener("click", signOutUser);
  }

  // Profile dropdown toggle
  if (profileTrigger) {
    profileTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      if (profileDropdown) {
        profileDropdown.classList.toggle("hidden");
      }
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

  // Manage profile
  if (manageProfileBtn) {
    manageProfileBtn.addEventListener("click", () => {
      if (profileDropdown) profileDropdown.classList.add("hidden");
      // Could open a profile management modal here
    });
  }
}

// Initialize Firebase Auth
function initializeFirebaseAuth() {
  if (!auth) {
    console.error("Firebase auth not available");
    return;
  }

  // Set up auth state listener
  onAuthStateChanged(auth, (user) => {
    updateAuthUI(user);
  });
}

// Wait for DOM to be ready, then initialize
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initElements();
    setupEventListeners();
    initializeFirebaseAuth();
  });
} else {
  // DOM is already ready
  initElements();
  setupEventListeners();
  initializeFirebaseAuth();
}
