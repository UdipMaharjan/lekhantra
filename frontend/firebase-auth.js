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

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

window.lekhantraAuth = {
  currentUser: null,
  idToken: null
};

const openAuthBtn = document.getElementById("openAuthBtn");
const authModal = document.getElementById("authModal");
const authCloseBtn = document.getElementById("authCloseBtn");

const authFullName = document.getElementById("authFullName");
const authEmail = document.getElementById("authEmail");
const authPassword = document.getElementById("authPassword");
const emailSignInBtn = document.getElementById("emailSignInBtn");
const emailCreateBtn = document.getElementById("emailCreateBtn");
const googleContinueBtn = document.getElementById("googleContinueBtn");
const authMessage = document.getElementById("authMessage");

const userMenu = document.getElementById("userMenu");
const userAvatar = document.getElementById("userAvatar");
const userGreeting = document.getElementById("userGreeting");
const logoutBtn = document.getElementById("logoutBtn");

function openAuthModal() {
  authModal.classList.remove("hidden");
  authMessage.textContent = "";
  authEmail.focus();
}

function closeAuthModal() {
  authModal.classList.add("hidden");
  authMessage.textContent = "";
}

function getFirstName(user) {
  const displayName = user.displayName || "";

  if (displayName.trim()) {
    return displayName.trim().split(" ")[0];
  }

  return "User";
}

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

  if (code.includes("auth/invalid-credential")) {
    return "Incorrect email or password.";
  }

  if (code.includes("auth/popup-closed-by-user")) {
    return "Google sign-in was cancelled.";
  }

  return "Authentication failed. Please try again.";
}

async function loginWithGoogle() {
  try {
    authMessage.textContent = "Opening Google sign-in...";
    await signInWithPopup(auth, googleProvider);
    closeAuthModal();
  } catch (error) {
    console.error(error);
    authMessage.textContent = getFriendlyError(error);
  }
}

async function signInWithEmail() {
  const email = authEmail.value.trim();
  const password = authPassword.value;

  if (!email || !password) {
    authMessage.textContent = "Please enter both email and password.";
    return;
  }

  try {
    authMessage.textContent = "Signing in...";
    await signInWithEmailAndPassword(auth, email, password);
    closeAuthModal();
  } catch (error) {
    console.error(error);
    authMessage.textContent = getFriendlyError(error);
  }
}

async function createAccountWithEmail() {
  const fullName = authFullName.value.trim();
  const email = authEmail.value.trim();
  const password = authPassword.value;

  if (!fullName || !email || !password) {
    authMessage.textContent = "Please enter full name, email, and password.";
    return;
  }

  try {
    authMessage.textContent = "Creating account...";

    const userCredential = await createUserWithEmailAndPassword(auth, email, password);

    await updateProfile(userCredential.user, {
      displayName: fullName
    });

    await userCredential.user.reload();

    closeAuthModal();

    if (typeof showToast === "function") {
      showToast("Account created successfully.");
    }
  } catch (error) {
    console.error(error);
    authMessage.textContent = getFriendlyError(error);
  }
}

openAuthBtn.addEventListener("click", openAuthModal);
authCloseBtn.addEventListener("click", closeAuthModal);
googleContinueBtn.addEventListener("click", loginWithGoogle);
emailSignInBtn.addEventListener("click", signInWithEmail);
emailCreateBtn.addEventListener("click", createAccountWithEmail);

authModal.addEventListener("click", (event) => {
  if (event.target === authModal) {
    closeAuthModal();
  }
});

authPassword.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    signInWithEmail();
  }
});

logoutBtn.addEventListener("click", async () => {
  await signOut(auth);
});

onAuthStateChanged(auth, async (user) => {
  if (user) {
    const token = await user.getIdToken();

    window.lekhantraAuth.currentUser = user;
    window.lekhantraAuth.idToken = token;

    openAuthBtn.classList.add("hidden");

    userMenu.classList.remove("hidden");
    userAvatar.src = user.photoURL || "https://ui-avatars.com/api/?name=" + encodeURIComponent(getFirstName(user));
    userGreeting.textContent = `Hey, ${getFirstName(user)}`;

    if (typeof showToast === "function") {
      showToast("Signed in successfully.");
    }
  } else {
    window.lekhantraAuth.currentUser = null;
    window.lekhantraAuth.idToken = null;

    openAuthBtn.classList.remove("hidden");

    userMenu.classList.add("hidden");
    userAvatar.src = "";
    userGreeting.textContent = "Hey, User";
  }
});