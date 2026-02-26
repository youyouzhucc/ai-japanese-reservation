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

function maskPhone(phone) {
  if (!phone || phone.length < 11) return phone || "";
  const p = phone.replace(/\D/g, "");
  if (p.length >= 11) return p.slice(0, 3) + "****" + p.slice(-4);
  return phone;
}

function updateUserInfo() {
  const el = document.getElementById("userInfo");
  fetch(`${API}/api/auth/me`, { headers: getAuthHeaders() })
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (d) el.textContent = maskPhone(d.phone);
      else redirectToLogin();
    })
    .catch(() => redirectToLogin());
}

const STATUS_TEXT = {
  pending: "待支付",
  reserving: "预约中",
  success: "预约成功",
  failed: "预约失败",
  cancelled: "已取消",
};

function formatDate(dt) {
  return new Date(dt).toLocaleString("zh-CN");
}

function loadReservations() {
  const loading = document.getElementById("loading");
  const empty = document.getElementById("empty");
  const list = document.getElementById("list");

  fetch(`${API}/api/reservations?limit=50`, { headers: getAuthHeaders() })
    .then((r) => {
      if (r.status === 401) {
        redirectToLogin();
        return [];
      }
      return r.json();
    })
    .then((data) => {
      loading.classList.add("hidden");
      const items = Array.isArray(data) ? data : [];
      if (items.length === 0) {
        empty.classList.remove("hidden");
        return;
      }
      list.classList.remove("hidden");
      list.innerHTML = items
        .map(
          (r) => `
        <div class="reservation-card" data-order="${r.order_no}">
          <div class="order-no">${escapeHtml(r.order_no)}</div>
          <div class="restaurant">${escapeHtml(r.restaurant_name)}</div>
          <div class="meta">${formatDate(r.reservation_datetime)} · ${r.adults}人${r.children ? " + " + r.children + "儿童" : ""}</div>
          <span class="status status-${r.status}">${STATUS_TEXT[r.status] || r.status}</span>
        </div>
      `
        )
        .join("");
      list.querySelectorAll(".reservation-card").forEach((card) => {
        card.addEventListener("click", () => showDetail(card.dataset.order));
      });
    })
    .catch(() => {
      loading.classList.add("hidden");
      empty.classList.remove("hidden");
      empty.innerHTML = "加载失败，<a href='/'>返回首页</a>";
    });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function showDetail(orderNo) {
  fetch(`${API}/api/reservations/${orderNo}`, { headers: getAuthHeaders() })
    .then((r) => (r.ok ? r.json() : null))
    .then((r) => {
      if (!r) return;
      const body = document.getElementById("detailBody");
      body.innerHTML = `
订单号：${r.order_no}
预约餐厅：${r.restaurant_name}
餐厅电话：${r.restaurant_phone}
预约人：${r.guest_name}
预约电话：${r.guest_phone}
预约时间：${formatDate(r.reservation_datetime)}
预约人数：${r.adults}人${r.children ? " + " + r.children + "儿童" : ""}
预约状态：${STATUS_TEXT[r.status] || r.status}
备注：${r.notes || "无"}
${r.ai_call_result ? "AI通话结果：\n" + r.ai_call_result : ""}
创建时间：${formatDate(r.created_at)}
      `.trim();
      const modal = document.getElementById("detailModal");
      const cancelBtn = document.getElementById("detailCancelBtn");
      if (r.status === "pending" || r.status === "reserving") {
        cancelBtn.classList.remove("hidden");
        cancelBtn.onclick = () => cancelOrder(orderNo, modal);
      } else {
        cancelBtn.classList.add("hidden");
      }
      modal.classList.remove("hidden");
    });
}

function cancelOrder(orderNo, modal) {
  if (!confirm("确定要取消此预约吗？")) return;
  fetch(`${API}/api/reservations/${orderNo}`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify({ status: "cancelled" }),
  })
    .then((r) => (r.ok ? r.json() : null))
    .then(() => {
      modal.classList.add("hidden");
      loadReservations();
    })
    .catch((e) => alert(e.message || "取消失败"));
}

document.getElementById("detailModal").querySelector(".modal-backdrop").addEventListener("click", () => {
  document.getElementById("detailModal").classList.add("hidden");
});
document.getElementById("detailCloseBtn").addEventListener("click", () => {
  document.getElementById("detailModal").classList.add("hidden");
});
document.getElementById("logoutBtn").addEventListener("click", () => {
  clearToken();
  redirectToLogin();
});

if (checkAuth()) {
  updateUserInfo();
  loadReservations();
}
