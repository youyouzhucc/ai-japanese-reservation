const API = "";
const AUTH_KEY = "reservation_auth_token";

window.checkAuthNav = function(e, el) {
  e.preventDefault();
  e.stopPropagation();
  if (!localStorage.getItem(AUTH_KEY)) {
    document.getElementById("loginModal")?.classList.remove("hidden");
    return false;
  }
  const href = el?.dataset?.href || el?.getAttribute("data-href");
  if (href) window.location.href = href;
  return false;
};
window.checkAuthSubmit = function(e) {
  if (!localStorage.getItem(AUTH_KEY)) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById("loginModal")?.classList.remove("hidden");
    return false;
  }
  return true;
};

function getToken() {
  return localStorage.getItem(AUTH_KEY);
}
function setToken(token) {
  localStorage.setItem(AUTH_KEY, token);
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

/** 带认证的 fetch：401 时自动清除 token 并弹出登录框，不重复 alert */
async function fetchWithAuth(url, init = {}) {
  const headers = { ...getAuthHeaders(), ...(init.headers || {}) };
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    showLoginModal();
    const err = new Error("登录已过期，请重新登录");
    err.authExpired = true;  // 已处理，caller 无需再 alert
    throw err;
  }
  return res;
}

function applyI18n() {
  document.getElementById("pageTitle").textContent = "🍣 " + t("title");
  document.getElementById("pageSubtitle").textContent = t("subtitle");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key && el.tagName !== "INPUT" && el.tagName !== "TEXTAREA") {
      el.textContent = t(key);
    }
  });
  document.querySelectorAll("[data-placeholder]").forEach((el) => {
    const ph = el.getAttribute("data-placeholder");
    if (ph) el.placeholder = t(ph);
  });
  document.getElementById("submitBtn").textContent = t("submit");
}

function initRestaurantSearch() {
  const searchInput = document.getElementById("restaurant_search");
  const searchBtn = document.getElementById("restaurantSearchBtn");
  const resultsEl = document.getElementById("restaurantSearchResults");
  const nameInput = document.getElementById("restaurant_name");
  const phoneInput = document.getElementById("restaurant_phone");

  async function doSearch() {
    const q = searchInput.value.trim();
    if (!q) {
      resultsEl.classList.add("hidden");
      return;
    }
    resultsEl.innerHTML = '<div class="search-result-item" style="color:#999">搜索中...</div>';
    resultsEl.classList.remove("hidden");
    try {
      const res = await fetchWithAuth(`${API}/api/restaurants/search?q=${encodeURIComponent(q)}`);
      if (!res.ok) {
        resultsEl.innerHTML = '<div class="search-result-item" style="color:#999">搜索失败，请重试</div>';
        return;
      }
      const data = await res.json();
      const list = data.results || [];
      resultsEl.innerHTML = "";
      if (list.length === 0) {
        const empty = document.createElement("div");
        empty.className = "search-result-item";
        empty.textContent = "未找到相关餐厅，请手动填写下方信息";
        empty.style.color = "#999";
        resultsEl.appendChild(empty);
      } else {
        list.forEach((r) => {
          const div = document.createElement("div");
          div.className = "search-result-item";
          div.innerHTML =
            `<span class="name">${escapeHtml(r.name)}</span>` +
            (r.phone ? `<div class="phone">${escapeHtml(r.phone)}</div>` : "") +
            (r.address ? `<div class="address">${escapeHtml(r.address)}</div>` : "");
          div.addEventListener("click", () => {
            nameInput.value = r.name;
            if (r.phone) phoneInput.value = r.phone;
            resultsEl.classList.add("hidden");
            searchInput.value = "";
          });
          resultsEl.appendChild(div);
        });
      }
      resultsEl.classList.remove("hidden");
    } catch {
      resultsEl.classList.add("hidden");
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  searchBtn.addEventListener("click", doSearch);
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      doSearch();
    }
  });
  document.addEventListener("click", (e) => {
    if (!searchInput.contains(e.target) && !searchBtn.contains(e.target) && !resultsEl.contains(e.target)) {
      resultsEl.classList.add("hidden");
    }
  });
}

const COUNTRY_CODES = [
  { code: "+86", name: "中国", flag: "🇨🇳" },
  { code: "+81", name: "日本", flag: "🇯🇵" },
  { code: "+852", name: "中国香港", flag: "🇭🇰" },
  { code: "+853", name: "中国澳门", flag: "🇲🇴" },
  { code: "+886", name: "中国台湾", flag: "🇹🇼" },
  { code: "+1", name: "美国/加拿大", flag: "🇺🇸" },
  { code: "+44", name: "英国", flag: "🇬🇧" },
  { code: "+82", name: "韩国", flag: "🇰🇷" },
  { code: "+65", name: "新加坡", flag: "🇸🇬" },
  { code: "+60", name: "马来西亚", flag: "🇲🇾" },
  { code: "+66", name: "泰国", flag: "🇹🇭" },
  { code: "+84", name: "越南", flag: "🇻🇳" },
  { code: "+62", name: "印尼", flag: "🇮🇩" },
  { code: "+63", name: "菲律宾", flag: "🇵🇭" },
  { code: "+91", name: "印度", flag: "🇮🇳" },
  { code: "+61", name: "澳大利亚", flag: "🇦🇺" },
  { code: "+64", name: "新西兰", flag: "🇳🇿" },
  { code: "+49", name: "德国", flag: "🇩🇪" },
  { code: "+33", name: "法国", flag: "🇫🇷" },
  { code: "+39", name: "意大利", flag: "🇮🇹" },
  { code: "+34", name: "西班牙", flag: "🇪🇸" },
  { code: "+351", name: "葡萄牙", flag: "🇵🇹" },
  { code: "+31", name: "荷兰", flag: "🇳🇱" },
  { code: "+46", name: "瑞典", flag: "🇸🇪" },
  { code: "+41", name: "瑞士", flag: "🇨🇭" },
  { code: "+7", name: "俄罗斯", flag: "🇷🇺" },
  { code: "+971", name: "阿联酋", flag: "🇦🇪" },
  { code: "+55", name: "巴西", flag: "🇧🇷" },
  { code: "+52", name: "墨西哥", flag: "🇲🇽" },
];

function initPhonePrefixSelect() {
  const sel = document.getElementById("guest_phone_prefix");
  if (!sel) return;
  COUNTRY_CODES.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.code;
    opt.textContent = `${c.flag} ${c.name} (${c.code})`;
    if (c.code === "+86") opt.selected = true;
    sel.appendChild(opt);
  });
}

function initReservationForm() {
  applyI18n();
  initRestaurantSearch();
  initPhonePrefixSelect();
  const dateInput = document.getElementById("reservation_date");
  const secondDateInput = document.getElementById("second_date");
  const today = new Date().toISOString().slice(0, 10);

  const hourSelect = document.getElementById("reservation_hour");
  if (hourSelect) {
    for (let h = 0; h < 24; h++) {
      const opt = document.createElement("option");
      opt.value = String(h).padStart(2, "0");
      opt.textContent = String(h).padStart(2, "0");
      hourSelect.appendChild(opt);
    }
  }
  const secondHourSelect = document.getElementById("second_hour");
  if (secondHourSelect) {
    for (let h = 0; h < 24; h++) {
      const opt = document.createElement("option");
      opt.value = String(h).padStart(2, "0");
      opt.textContent = String(h).padStart(2, "0");
      secondHourSelect.appendChild(opt);
    }
  }

  let pickerYear = new Date().getFullYear();
  let pickerMonth = new Date().getMonth();
  let editingDateInput = null;

  function openDatePicker(targetInput) {
    editingDateInput = targetInput;
    const v = targetInput.value || targetInput.dataset.value;
    if (v) {
      const [y, m] = v.split("-").map(Number);
      pickerYear = y;
      pickerMonth = m - 1;
    } else {
      pickerYear = new Date().getFullYear();
      pickerMonth = new Date().getMonth();
    }
    const popup = document.getElementById("datePickerPopup");
    const anchor = targetInput.closest(".date-picker-wrap");
    const rect = anchor.getBoundingClientRect();
    popup.style.top = (rect.bottom + 4) + "px";
    popup.style.left = rect.left + "px";
    renderDatePicker();
    popup.classList.remove("hidden");
  }

  function renderDatePicker() {
    const popup = document.getElementById("datePickerPopup");
    const monthEl = document.getElementById("datePickerMonth");
    const daysEl = document.getElementById("datePickerDays");
    const firstDay = new Date(pickerYear, pickerMonth, 1);
    const lastDay = new Date(pickerYear, pickerMonth + 1, 0);
    const startOffset = (firstDay.getDay() + 6) % 7;
    const daysInMonth = lastDay.getDate();
    const todayStr = new Date().toISOString().slice(0, 10);

    monthEl.textContent = `${pickerYear}年${String(pickerMonth + 1).padStart(2, "0")}月`;
    daysEl.innerHTML = "";

    for (let i = 0; i < startOffset; i++) {
      const prevMonthLast = new Date(pickerYear, pickerMonth, 0).getDate();
      const d = prevMonthLast - startOffset + i + 1;
      const span = document.createElement("span");
      span.className = "day other-month disabled";
      span.textContent = d;
      daysEl.appendChild(span);
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const span = document.createElement("span");
      span.className = "day";
      span.textContent = d;
      const dateStr = `${pickerYear}-${String(pickerMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      if (dateStr < todayStr) span.classList.add("disabled");
      if (dateStr === todayStr) span.classList.add("today");
      const currentVal = editingDateInput?.value || editingDateInput?.dataset?.value;
      if (currentVal === dateStr) span.classList.add("selected");
      span.addEventListener("click", () => {
        if (span.classList.contains("disabled")) return;
        if (editingDateInput) {
          editingDateInput.value = dateStr;
          editingDateInput.dataset.value = dateStr;
        }
        popup.classList.add("hidden");
        document.querySelectorAll("#datePickerDays .day.selected").forEach((s) => s.classList.remove("selected"));
        span.classList.add("selected");
      });
      daysEl.appendChild(span);
    }
    const total = startOffset + daysInMonth;
    const remaining = total % 7 ? 7 - (total % 7) : 0;
    for (let i = 0; i < remaining; i++) {
      const span = document.createElement("span");
      span.className = "day other-month disabled";
      span.textContent = i + 1;
      daysEl.appendChild(span);
    }
  }

  document.getElementById("openDatePicker").addEventListener("click", () => {
    const popup = document.getElementById("datePickerPopup");
    if (popup.classList.contains("hidden")) {
      openDatePicker(dateInput);
    } else if (editingDateInput === dateInput) {
      popup.classList.add("hidden");
    } else {
      openDatePicker(dateInput);
    }
  });

  document.getElementById("openDatePicker2").addEventListener("click", () => {
    const popup = document.getElementById("datePickerPopup");
    if (popup.classList.contains("hidden")) {
      openDatePicker(secondDateInput);
    } else if (editingDateInput === secondDateInput) {
      popup.classList.add("hidden");
    } else {
      openDatePicker(secondDateInput);
    }
  });

  document.getElementById("prevMonth").addEventListener("click", () => {
    pickerMonth--;
    if (pickerMonth < 0) {
      pickerMonth = 11;
      pickerYear--;
    }
    renderDatePicker();
  });

  document.getElementById("nextMonth").addEventListener("click", () => {
    pickerMonth++;
    if (pickerMonth > 11) {
      pickerMonth = 0;
      pickerYear++;
    }
    renderDatePicker();
  });

  document.addEventListener("click", (e) => {
    const popup = document.getElementById("datePickerPopup");
    const opener = document.getElementById("openDatePicker");
    const opener2 = document.getElementById("openDatePicker2");
    if (!popup.contains(e.target) && !opener?.contains(e.target) && !opener2?.contains(e.target)) {
      popup.classList.add("hidden");
    }
  });
}

function updateAuthUI() {
  const nick = localStorage.getItem("reservation_nickname");
  const el = document.getElementById("navNickname");
  if (el && nick) el.textContent = nick;
}

function initHeaderNavLinks() {
  document.querySelectorAll('#myAccountLink, #myReservationsLink').forEach((link) => {
    link.addEventListener("click", (e) => {
      if (!localStorage.getItem(AUTH_KEY)) {
        e.preventDefault();
        e.stopPropagation();
        document.getElementById("loginModal")?.classList.remove("hidden");
        return false;
      }
    }, true);
  });
}

let _pendingFormSubmit = false;

function showLoginModal(fromFormSubmit) {
  _pendingFormSubmit = !!fromFormSubmit;
  const el = document.getElementById("loginModal");
  if (el) el.classList.remove("hidden");
}
function hideLoginModal() {
  document.getElementById("loginModal").classList.add("hidden");
}

function initLoginModal() {
  const modal = document.getElementById("loginModal");
  const sendBtn = document.getElementById("sendCodeBtn");
  const submitBtn = document.getElementById("loginSubmitBtn");
  const closeBtn = document.getElementById("loginModalCloseBtn");
  const phoneInput = document.getElementById("login_phone");
  const codeInput = document.getElementById("login_code");

  modal.querySelector(".modal-backdrop").addEventListener("click", hideLoginModal);
  if (closeBtn) closeBtn.addEventListener("click", hideLoginModal);

  modal.addEventListener("click", async (e) => {
    if (e.target.id !== "sendCodeBtn" && !e.target.closest("#sendCodeBtn")) return;
    e.preventDefault();
    e.stopPropagation();
    const phone = phoneInput.value.trim().replace(/\s/g, "").replace(/-/g, "");
    if (phone.length < 8) {
      alert("请输入正确的手机号（含区号）");
      return;
    }
    sendBtn.disabled = true;
    sendBtn.textContent = "发送中...";
    try {
      const res = await fetch(`${API}/api/auth/send-code`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || "发送失败");
      alert("验证码已发送，请查收短信");
      let sec = 60;
      const t = setInterval(() => {
        sec--;
        sendBtn.textContent = sec > 0 ? `${sec}秒后重发` : "获取验证码";
        if (sec <= 0) {
          clearInterval(t);
          sendBtn.disabled = false;
        }
      }, 1000);
    } catch (e) {
      alert(e.message || "发送失败");
      sendBtn.disabled = false;
      sendBtn.textContent = "获取验证码";
    }
  }, true);

  submitBtn.addEventListener("click", async () => {
    const phone = phoneInput.value.trim().replace(/\s/g, "").replace(/-/g, "");
    const code = codeInput.value.trim();
    if (!phone || phone.length < 8) {
      alert("请输入正确的手机号");
      return;
    }
    if (!code || code.length < 4) {
      alert("请输入验证码");
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "登录中...";
    try {
      const res = await fetch(`${API}/api/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone, code }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || res.statusText || "登录失败");
      setToken(data.token);
      if (data.nickname) localStorage.setItem("reservation_nickname", data.nickname);
      hideLoginModal();
      updateAuthUI();
      phoneInput.value = "";
      codeInput.value = "";
      if (_pendingFormSubmit) {
        _pendingFormSubmit = false;
        document.getElementById("reservationForm")?.requestSubmit();
      }
    } catch (e) {
      alert(e.message || "登录失败");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "登录";
    }
  });

}

function initAuthTriggers() {
  // 已通过 onclick 内联处理
}

function init() {
  initReservationForm();
  initLoginModal();
  initHeaderNavLinks();
  initAuthTriggers();
  updateAuthUI();
  // 清理 URL 中的 ?login=1，不主动弹出登录框（首次进入、刷新均不弹）
  if (new URLSearchParams(location.search).get("login") === "1") {
    history.replaceState(null, "", location.pathname);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

// ============ 步骤页面切换 ============

const STEP_IDS = ["reservationForm", "stepConfirm", "stepPayQr", "stepSuccess"];

function showStep(stepId) {
  STEP_IDS.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("hidden", id !== stepId);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function escapeH(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

let _currentOrder = null;
let _currentDatetime = "";

function buildInfoHtml(order, datetime) {
  return `
    <div class="confirm-row"><span class="confirm-label">订单号</span><span>${escapeH(order.order_no)}</span></div>
    <div class="confirm-row"><span class="confirm-label">餐厅</span><span>${escapeH(order.restaurant_name)}</span></div>
    <div class="confirm-row"><span class="confirm-label">餐厅电话</span><span>${escapeH(order.restaurant_phone)}</span></div>
    <div class="confirm-row"><span class="confirm-label">预约人</span><span>${escapeH(order.guest_name)}</span></div>
    <div class="confirm-row"><span class="confirm-label">预约时间</span><span>${escapeH(datetime)}</span></div>
    <div class="confirm-row"><span class="confirm-label">人数</span><span>${order.adults}成人${order.children ? " + " + order.children + "儿童" : ""}</span></div>
    <div class="confirm-row"><span class="confirm-label">金额</span><span>¥1.00</span></div>
  `;
}

// 表单提交 → 创建订单 → 显示确认页
document.getElementById("reservationForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!getToken()) {
    showLoginModal(true);
    return;
  }
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.textContent = t("submitting");

  const date = document.getElementById("reservation_date").value || document.getElementById("reservation_date").dataset.value;
  const hour = document.getElementById("reservation_hour")?.value || "";
  const minute = document.getElementById("reservation_minute")?.value || "";
  const time = hour && minute ? `${hour}:${minute}` : "";
  if (!date || !time) {
    alert("请选择预约日期和时间");
    btn.disabled = false;
    btn.textContent = t("submit");
    return;
  }
  const reservation_datetime = `${date} ${time}`;

  const prefix = document.getElementById("guest_phone_prefix").value;
  const number = document.getElementById("guest_phone_number").value.trim().replace(/\D/g, "");
  const guest_phone = prefix + number;

  const secondDate = document.getElementById("second_date")?.value || document.getElementById("second_date")?.dataset?.value || "";
  const secondHour = document.getElementById("second_hour")?.value || "";
  const secondMinute = document.getElementById("second_minute")?.value || "";
  const secondTime = secondHour && secondMinute ? `${secondHour}:${secondMinute}` : "";
  const dietaryNotes = document.getElementById("dietary_notes").value.trim();
  const notes = document.getElementById("notes").value.trim();

  let fullNotes = "";
  if (secondDate && secondTime) fullNotes += `第二希望日期时间: ${secondDate} ${secondTime}\n`;
  else if (secondDate) fullNotes += `第二希望日期: ${secondDate}\n`;
  if (dietaryNotes) fullNotes += `饮食忌口: ${dietaryNotes}\n`;
  if (notes) fullNotes += notes;

  const payload = {
    restaurant_name: document.getElementById("restaurant_name").value.trim(),
    restaurant_phone: document.getElementById("restaurant_phone").value.trim(),
    guest_name: document.getElementById("guest_name").value.trim(),
    guest_phone: guest_phone,
    reservation_datetime,
    adults: parseInt(document.getElementById("adults").value) || 1,
    children: parseInt(document.getElementById("children").value) || 0,
    notes: fullNotes.trim(),
  };

  try {
    const res = await fetchWithAuth(`${API}/api/reservations`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const order = await res.json();
    _currentOrder = order;
    _currentDatetime = reservation_datetime;
    document.getElementById("confirmInfo").innerHTML = buildInfoHtml(order, reservation_datetime);
    showStep("stepConfirm");
  } catch (err) {
    if (!err.authExpired) alert(err.message || "提交失败");
  } finally {
    btn.disabled = false;
    btn.textContent = t("submit");
  }
});

// 确认页 → 返回修改
document.getElementById("confirmBackBtn").addEventListener("click", () => {
  showStep("reservationForm");
});

// 确认页 → 支付
document.getElementById("confirmPayBtn").addEventListener("click", async () => {
  const btn = document.getElementById("confirmPayBtn");
  btn.disabled = true;
  btn.textContent = "支付中...";
  try {
    const res = await fetchWithAuth(`${API}/api/pay`, {
      method: "POST",
      body: JSON.stringify({ order_no: _currentOrder.order_no, amount_cents: 100 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const payResult = await res.json();
    if (!payResult.success) throw new Error(payResult.message || "支付失败");

    if (payResult.qr_code) {
      document.getElementById("payQrInfo").innerHTML = buildInfoHtml(_currentOrder, _currentDatetime);
      document.getElementById("payQrArea").innerHTML =
        `<img src="https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(payResult.qr_code)}" alt="支付二维码">`;
      document.getElementById("payQrHint").textContent = "请使用支付宝扫码支付，支付完成后点击下方按钮";
      showStep("stepPayQr");
    } else {
      showSuccessPage("reserving");
    }
  } catch (err) {
    if (!err.authExpired) alert(err.message || "支付失败");
  } finally {
    btn.disabled = false;
    btn.textContent = "去支付（¥1）";
  }
});

// 二维码页 → 返回预约
document.getElementById("payQrBackBtn").addEventListener("click", () => {
  showStep("reservationForm");
});

// 二维码页 → 查看支付结果
document.getElementById("payQrCheckBtn").addEventListener("click", async () => {
  const btn = document.getElementById("payQrCheckBtn");
  btn.disabled = true;
  btn.textContent = "查询中...";
  try {
    const res = await fetchWithAuth(`${API}/api/reservations/${_currentOrder.order_no}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();
    if (r.status === "pending") {
      alert("尚未收到支付结果，请确认已完成支付后重试");
    } else {
      showSuccessPage(r.status, r);
    }
  } catch (err) {
    if (!err.authExpired) alert(err.message || "查询失败");
  } finally {
    btn.disabled = false;
    btn.textContent = "我已支付，查看结果";
  }
});

function showSuccessPage(status, orderData) {
  const STATUS_MAP = {
    reserving: { icon: "📞", title: "支付成功，AI 正在致电餐厅", msg: "AI 将自动致电餐厅完成日语预约，请稍后在「我的预约」中查看结果" },
    success: { icon: "✅", title: "预约成功", msg: "AI 已成功完成餐厅预约，祝用餐愉快！" },
    failed: { icon: "❌", title: "预约失败", msg: orderData?.ai_call_result || "AI 电话未能成功预约，请稍后重试" },
  };
  const info = STATUS_MAP[status] || STATUS_MAP.reserving;
  document.getElementById("successIcon").textContent = info.icon;
  document.getElementById("successTitle").textContent = info.title;
  document.getElementById("successMsg").textContent = info.msg;
  document.getElementById("successInfo").innerHTML = buildInfoHtml(orderData || _currentOrder, _currentDatetime);

  const refreshBtn = document.getElementById("successRefreshBtn");
  if (status === "reserving") {
    refreshBtn.classList.remove("hidden");
    refreshBtn.onclick = () => refreshSuccessStatus();
  } else {
    refreshBtn.classList.add("hidden");
  }
  showStep("stepSuccess");
}

async function refreshSuccessStatus() {
  const btn = document.getElementById("successRefreshBtn");
  btn.disabled = true;
  btn.textContent = "刷新中...";
  try {
    const res = await fetchWithAuth(`${API}/api/reservations/${_currentOrder.order_no}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();
    showSuccessPage(r.status, r);
  } catch (err) {
    if (!err.authExpired) alert(err.message || "刷新失败");
  } finally {
    btn.disabled = false;
    btn.textContent = "刷新状态";
  }
}

// 成功页 → 返回预约
document.getElementById("successBackBtn").addEventListener("click", () => {
  _currentOrder = null;
  _currentDatetime = "";
  showStep("reservationForm");
});
