const API = "";

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
  document.getElementById("checkStatusBtn").textContent = t("refreshStatus");
}

function initReservationForm() {
  applyI18n();
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

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initReservationForm);
} else {
  initReservationForm();
}

document.getElementById("reservationForm").addEventListener("submit", async (e) => {
  e.preventDefault();
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

  const prefix = document.getElementById("guest_phone_prefix").value.trim();
  const number = document.getElementById("guest_phone_number").value.trim().replace(/\D/g, "");
  const guest_phone = (prefix.startsWith("+") ? prefix : prefix ? "+" + prefix : "+86") + number;

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
    const res = await fetch(`${API}/api/reservations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const order = await res.json();
    document.getElementById("result").classList.remove("hidden");
    document.getElementById("orderInfo").textContent =
      `订单号：${order.order_no}\n餐厅：${order.restaurant_name}\n预约时间：${reservation_datetime}\n状态：待支付\n金额：1元`;
    document.getElementById("statusMsg").textContent = "请完成支付，支付成功后 AI 将自动致电餐厅完成预约";
    document.getElementById("statusMsg").className = "status-reserving";
    document.getElementById("checkStatusBtn").textContent = "去支付";
    document.getElementById("checkStatusBtn").onclick = () => doPay(order, reservation_datetime);
  } catch (err) {
    alert(err.message || "提交失败");
  } finally {
    btn.disabled = false;
    btn.textContent = t("submit");
  }
});

async function doPay(order, reservationDatetime) {
  const orderNo = order.order_no;
  const btn = document.getElementById("checkStatusBtn");
  btn.disabled = true;
  btn.textContent = "支付中...";
  try {
    const res = await fetch(`${API}/api/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_no: orderNo, amount_cents: 100 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    const payResult = await res.json();
    if (!payResult.success) throw new Error(payResult.message || "支付失败");
    if (payResult.qr_code) {
      document.getElementById("orderInfo").innerHTML =
        `订单号：${orderNo}<br>餐厅：${order.restaurant_name}<br>预约时间：${reservationDatetime}<br>金额：1元<br><br>` +
        `<p style="margin:8px 0">请使用支付宝扫码支付：</p>` +
        `<img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(payResult.qr_code)}" alt="支付二维码" style="display:block;margin:8px auto;border:1px solid #ddd;padding:8px">`;
      document.getElementById("statusMsg").textContent = "扫码支付完成后，AI 将自动致电餐厅，请稍后刷新查看状态";
    } else {
      document.getElementById("orderInfo").textContent =
        `订单号：${orderNo}\n餐厅：${order.restaurant_name}\n预约时间：${reservationDatetime}\n状态：预约中`;
      document.getElementById("statusMsg").textContent = t("statusReserving");
    }
    document.getElementById("statusMsg").className = "status-reserving";
    btn.textContent = t("refreshStatus");
    btn.disabled = false;
    btn.onclick = () => checkStatus(orderNo);
  } catch (err) {
    alert(err.message || "支付失败");
    btn.disabled = false;
    btn.textContent = "去支付";
  }
}

async function checkStatus(orderNo) {
  try {
    const res = await fetch(`${API}/api/reservations/${orderNo}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();
    const dt = new Date(r.reservation_datetime).toLocaleString("zh-CN");
    const statusText = { success: "预约成功", failed: "预约失败", reserving: "预约中", pending: "待支付", cancelled: "已取消" }[r.status] || r.status;
    document.getElementById("orderInfo").textContent =
      `订单号：${r.order_no}\n餐厅：${r.restaurant_name}\n预约时间：${dt}\n状态：${statusText}`;
    const msg = document.getElementById("statusMsg");
    if (r.status === "success") {
      msg.textContent = t("statusSuccess");
      msg.className = "status-success";
    } else if (r.status === "failed") {
      msg.textContent = t("statusFailed") + (r.ai_call_result || "请稍后重试");
      msg.className = "status-failed";
    } else {
      msg.textContent = t("statusReserving");
      msg.className = "status-reserving";
    }
  } catch (e) {
    alert(e.message);
  }
}
