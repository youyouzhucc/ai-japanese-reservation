const API = "";

document.addEventListener("DOMContentLoaded", () => {
  const dateInput = document.getElementById("reservation_date");
  dateInput.min = new Date().toISOString().slice(0, 10);
});

function roundTimeToHalfHour(timeStr) {
  if (!timeStr) return timeStr;
  const [h, m] = timeStr.split(":").map(Number);
  const rounded = Math.floor(m / 30) * 30;
  return `${String(h).padStart(2, "0")}:${String(rounded).padStart(2, "0")}`;
}

document.getElementById("reservation_time").addEventListener("change", function () {
  this.value = roundTimeToHalfHour(this.value);
});

document.getElementById("reservationForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.textContent = "提交中...";

  const date = document.getElementById("reservation_date").value;
  const time = roundTimeToHalfHour(document.getElementById("reservation_time").value);
  const reservation_datetime = `${date} ${time}`;

  const payload = {
    restaurant_name: document.getElementById("restaurant_name").value.trim(),
    restaurant_phone: document.getElementById("restaurant_phone").value.trim(),
    guest_name: document.getElementById("guest_name").value.trim(),
    guest_phone: document.getElementById("guest_phone").value.trim(),
    reservation_datetime,
    adults: parseInt(document.getElementById("adults").value) || 1,
    children: parseInt(document.getElementById("children").value) || 0,
    notes: document.getElementById("notes").value.trim(),
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
    // 支付
    const payRes = await fetch(`${API}/api/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_no: order.order_no, amount_cents: 100 }),
    });
    if (!payRes.ok) {
      const err = await payRes.json().catch(() => ({}));
      throw new Error(err.detail || "支付失败");
    }
    document.getElementById("result").classList.remove("hidden");
    document.getElementById("orderInfo").textContent = `订单号：${order.order_no}\n餐厅：${order.restaurant_name}\n预约时间：${reservation_datetime}\n状态：预约中`;
    document.getElementById("statusMsg").textContent = "AI 正在致电餐厅，请稍候。完成后将短信通知您。";
    document.getElementById("statusMsg").className = "status-reserving";
    document.getElementById("checkStatusBtn").onclick = () => checkStatus(order.order_no);
  } catch (err) {
    alert(err.message || "提交失败");
  } finally {
    btn.disabled = false;
    btn.textContent = "提交预约并支付";
  }
});

async function checkStatus(orderNo) {
  try {
    const res = await fetch(`${API}/api/reservations/${orderNo}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();
    const dt = new Date(r.reservation_datetime).toLocaleString("zh-CN");
    document.getElementById("orderInfo").textContent =
      `订单号：${r.order_no}\n餐厅：${r.restaurant_name}\n预约时间：${dt}\n状态：${r.status}`;
    const msg = document.getElementById("statusMsg");
    if (r.status === "success") {
      msg.textContent = "预约成功！已发送短信通知。";
      msg.className = "status-success";
    } else if (r.status === "failed") {
      msg.textContent = "预约未成功：" + (r.ai_call_result || "请稍后重试");
      msg.className = "status-failed";
    } else {
      msg.textContent = "AI 正在致电餐厅，请稍候...";
      msg.className = "status-reserving";
    }
  } catch (e) {
    alert(e.message);
  }
}
