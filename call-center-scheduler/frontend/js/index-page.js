import { apiRequest } from "./api.js";
import { saveAuth, clearAuth, isLoggedIn, getCurrentUser } from "./auth.js";
import { clearAlert, showAlert, requireValue } from "./ui.js";

const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const alertBoxId = "authAlerts";

function resolveHomeRoute(user) {
  return user?.role === "admin" ? "/admin" : "/dashboard";
}

if (isLoggedIn()) {
  const existingUser = getCurrentUser();
  window.location.href = resolveHomeRoute(existingUser);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBoxId);

  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;

  try {
    requireValue(email, "Email");
    requireValue(password, "Password");

    const result = await apiRequest("/auth/login", {
      method: "POST",
      auth: false,
      body: { email, password },
    });

    saveAuth(result);
    window.location.href = resolveHomeRoute(result.user);
  } catch (error) {
    showAlert(alertBoxId, error.message, "danger");
  }
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert(alertBoxId);

  const fullName = document.getElementById("registerFullName").value.trim();
  const email = document.getElementById("registerEmail").value.trim();
  const password = document.getElementById("registerPassword").value;
  const confirmPassword = document.getElementById("registerConfirmPassword").value;

  try {
    requireValue(fullName, "Full name");
    requireValue(email, "Email");
    requireValue(password, "Password");

    if (password.length < 8) {
      throw new Error("Password must be at least 8 characters");
    }
    if (password !== confirmPassword) {
      throw new Error("Passwords do not match");
    }

    const payload = {
      full_name: fullName,
      email,
      password,
    };

    const result = await apiRequest("/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    });

    saveAuth(result);
    showAlert(alertBoxId, "Registration successful. Redirecting...", "success");
    setTimeout(() => {
      window.location.href = resolveHomeRoute(result.user);
    }, 700);
  } catch (error) {
    showAlert(alertBoxId, error.message, "danger");
  }
});

const clearButtons = document.querySelectorAll("[data-clear-auth]");
for (const button of clearButtons) {
  button.addEventListener("click", () => {
    clearAuth();
  });
}
