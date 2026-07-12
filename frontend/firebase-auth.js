import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.1/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged
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

const googleLoginBtn = document.getElementById("googleLoginBtn");
const googleSignupBtn = document.getElementById("googleSignupBtn");
const userMenu = document.getElementById("userMenu");
const userAvatar = document.getElementById("userAvatar");
const userName = document.getElementById("userName");
const logoutBtn = document.getElementById("logoutBtn");

async function loginWithGoogle() {
  try {
    await signInWithPopup(auth, googleProvider);
  } catch (error) {
    console.error(error);
    alert("Google login failed.");
  }
}

googleLoginBtn.addEventListener("click", loginWithGoogle);
googleSignupBtn.addEventListener("click", loginWithGoogle);

logoutBtn.addEventListener("click", async () => {
  await signOut(auth);
});

onAuthStateChanged(auth, async (user) => {
  if (user) {
    const token = await user.getIdToken();

    window.lekhantraAuth.currentUser = user;
    window.lekhantraAuth.idToken = token;

    googleLoginBtn.classList.add("hidden");
    googleSignupBtn.classList.add("hidden");

    userMenu.classList.remove("hidden");
    userAvatar.src = user.photoURL || "";
    userName.textContent = user.displayName || user.email || "User";

    if (typeof showToast === "function") {
      showToast("Logged in successfully.");
    }
  } else {
    window.lekhantraAuth.currentUser = null;
    window.lekhantraAuth.idToken = null;

    googleLoginBtn.classList.remove("hidden");
    googleSignupBtn.classList.remove("hidden");

    userMenu.classList.add("hidden");
    userAvatar.src = "";
    userName.textContent = "";
  }
});