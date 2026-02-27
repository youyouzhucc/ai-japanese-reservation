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

async function fetchWithAuth(url, init = {}) {
  const headers = { ...getAuthHeaders(), ...(init.headers || {}) };
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    redirectToLogin();
    throw new Error("登录已过期，请重新登录");
  }
  return res;
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
    .then((r) => {
      if (r.status === 401) {
        clearToken();
        redirectToLogin();
        return null;
      }
      return r.ok ? r.json() : null;
    })
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
        clearToken();
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
    .then((r) => {
      if (r.status === 401) {
        clearToken();
        redirectToLogin();
        return null;
      }
      return r.ok ? r.json() : null;
    })
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
      const payBtn = document.getElementById("detailPayBtn");
      const cancelBtn = document.getElementById("detailCancelBtn");
      if (r.status === "pending") {
        payBtn.classList.remove("hidden");
        payBtn.textContent = "去支付";
        payBtn.disabled = false;
        payBtn.onclick = () => doPayFromDetail(r, body, payBtn);
      } else if (r.status === "reserving") {
        payBtn.classList.remove("hidden");
        payBtn.textContent = "刷新状态";
        payBtn.disabled = false;
        payBtn.onclick = () => refreshDetailStatus(orderNo, body, payBtn);
      } else {
        payBtn.classList.add("hidden");
      }
      if (r.status === "pending" || r.status === "reserving") {
        cancelBtn.classList.remove("hidden");
        cancelBtn.onclick = () => cancelOrder(orderNo, modal);
      } else {
        cancelBtn.classList.add("hidden");
      }
      modal.classList.remove("hidden");
    });
}

async function doPayFromDetail(r, bodyEl, payBtn) {
  const orderNo = r.order_no;
  payBtn.disabled = true;
  payBtn.textContent = "支付中...";
  try {
    const res = await fetchWithAuth(`${API}/api/pay`, {
      method: "POST",
      body: JSON.stringify({ order_no: orderNo, amount_cents: 100 }),
    });
    const payResult = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(payResult.detail || res.statusText || "支付失败");
    if (!payResult.success) throw new Error(payResult.message || "支付失败");
    const dt = formatDate(r.reservation_datetime);
    if (payResult.qr_code) {
      bodyEl.innerHTML =
        `订单号：${orderNo}\n餐厅：${r.restaurant_name}\n预约时间：${dt}\n金额：1元\n\n` +
        `<p style="margin:8px 0">请使用支付宝扫码支付：</p>` +
        `<img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(payResult.qr_code)}" alt="支付二维码" style="display:block;margin:8px auto;border:1px solid #ddd;padding:8px">` +
        `\n扫码支付完成后，AI 将自动致电餐厅，请稍后刷新查看状态`;
    } else {
      bodyEl.innerHTML =
        `订单号：${orderNo}\n餐厅：${r.restaurant_name}\n预约时间：${dt}\n状态：预约中\n\n模拟支付成功，AI 将自动致电餐厅`;
    }
    payBtn.textContent = "刷新状态";
    payBtn.disabled = false;
    payBtn.onclick = () => refreshDetailStatus(orderNo, bodyEl, payBtn);
  } catch (err) {
    alert(err.message || "支付失败");
    payBtn.disabled = false;
    payBtn.textContent = "去支付";
  }
}

async function refreshDetailStatus(orderNo, bodyEl, payBtn) {
  payBtn.disabled = true;
  payBtn.textContent = "刷新中...";
  try {
    const res = await fetchWithAuth(`${API}/api/reservations/${orderNo}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();
    const dt = formatDate(r.reservation_datetime);
    bodyEl.innerHTML =
      `订单号：${r.order_no}\n预约餐厅：${r.restaurant_name}\n餐厅电话：${r.restaurant_phone}\n预约人：${r.guest_name}\n预约电话：${r.guest_phone}\n预约时间：${dt}\n预约人数：${r.adults}人${r.children ? " + " + r.children + "儿童" : ""}\n预约状态：${STATUS_TEXT[r.status] || r.status}\n备注：${r.notes || "无"}\n${r.ai_call_result ? "AI通话结果：\n" + r.ai_call_result : ""}\n创建时间：${formatDate(r.created_at)}`.trim();
    if (r.status === "pending") {
      payBtn.classList.remove("hidden");
      payBtn.textContent = "去支付";
      payBtn.onclick = () => doPayFromDetail(r, bodyEl, payBtn);
    } else if (r.status === "reserving") {
      payBtn.classList.remove("hidden");
      payBtn.textContent = "刷新状态";
      payBtn.onclick = () => refreshDetailStatus(orderNo, bodyEl, payBtn);
    } else {
      payBtn.classList.add("hidden");
    }
    loadReservations();
  } catch (err) {
    alert(err.message || "刷新失败");
  } finally {
    payBtn.disabled = false;
  }
}

function cancelOrder(orderNo, modal) {
  if (!confirm("确定要取消此预约吗？")) return;
  fetch(`${API}/api/reservations/${orderNo}`, {
    method: "PATCH",
    headers: getAuthHeaders(),
    body: JSON.stringify({ status: "cancelled" }),
  })
    .then((r) => {
      if (r.status === 401) {
        clearToken();
        redirectToLogin();
        return null;
      }
      return r.ok ? r.json() : null;
    })
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
