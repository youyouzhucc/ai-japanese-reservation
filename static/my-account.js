const API = "";
const AUTH_KEY = "reservation_auth_token";

function getToken() {
  return localStorage.getItem(AUTH_KEY);
}
function clearToken() {
  localStorage.removeItem(AUTH_KEY);
}
function getAuthHeaders() {
  const token = getToken();
  const h = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = "Bearer " + token;
  return h;
}

function maskPhone(phone) {
  if (!phone || phone.length < 11) return phone || "--";
  const p = phone.replace(/\D/g, "");
  if (p.length >= 11) {
    return p.slice(0, 3) + "****" + p.slice(-4);
  }
  return phone;
}

function redirectToLogin() {
  window.location.href = "/?login=1";
}

function checkAuth() {
  if (!getToken()) {
    redirectToLogin();
    return false;
  }
  return true;
}

function loadAccount() {
  fetch(`${API}/api/auth/me`, { headers: getAuthHeaders() })
    .then((r) => {
      if (r.status === 401) {
        clearToken();
        redirectToLogin();
        return null;
      }
      return r.ok ? r.json() : null;
    })
    .then((d) => {
      if (d && d.phone) {
        document.getElementById("phoneDisplay").textContent = maskPhone(d.phone);
        if (d.nickname) {
          document.getElementById("nicknameDisplay").textContent = d.nickname;
        }
      } else {
        redirectToLogin();
      }
    })
    .catch(() => redirectToLogin());
}

document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  localStorage.removeItem("reservation_nickname");
  redirectToLogin();
});

if (checkAuth()) {
  loadAccount();
}
