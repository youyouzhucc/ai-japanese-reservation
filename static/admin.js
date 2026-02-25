const API = "";

const STATUS_TEXT = {
  pending: "待支付",
  reserving: "预约中",
  success: "预约成功",
  failed: "预约失败",
  cancelled: "已取消",
};

function formatStatus(status) {
  return STATUS_TEXT[status] || status;
}

function formatDate(d) {
  return new Date(d).toLocaleString("zh-CN");
}

async function loadReservations() {
  const tbody = document.getElementById("tableBody");
  const filter = document.getElementById("statusFilter").value;

  tbody.innerHTML = '<tr><td colspan="8" class="loading">加载中...</td></tr>';

  try {
    const res = await fetch(`${API}/api/reservations?limit=100`);
    if (!res.ok) throw new Error("加载失败");
    let list = await res.json();

    if (filter) {
      list = list.filter((r) => r.status === filter);
    }

    if (list.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty">暂无预约单</td></tr>';
      return;
    }

    tbody.innerHTML = list
      .map(
        (r) => `
      <tr>
        <td><code>${r.order_no}</code></td>
        <td>${r.restaurant_name}</td>
        <td>${r.guest_name}<br><small>${r.guest_phone}</small></td>
        <td>${formatDate(r.reservation_datetime)}</td>
        <td>${r.adults}大${r.children ? r.children + "小" : ""}</td>
        <td><span class="status-badge status-${r.status}">${formatStatus(r.status)}</span></td>
        <td>${formatDate(r.created_at)}</td>
        <td>
          <button class="btn-action btn-view" data-order="${r.order_no}">详情</button>
          ${r.status === "pending" || r.status === "reserving" ? `<button class="btn-action btn-cancel" data-order="${r.order_no}">取消</button>` : ""}
        </td>
      </tr>
    `
      )
      .join("");

    tbody.querySelectorAll(".btn-view").forEach((btn) => {
      btn.onclick = () => showDetail(btn.dataset.order);
    });
    tbody.querySelectorAll(".btn-cancel").forEach((btn) => {
      btn.onclick = () => cancelOrder(btn.dataset.order);
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty">加载失败: ${e.message}</td></tr>`;
  }
}

async function showDetail(orderNo) {
  try {
    const res = await fetch(`${API}/api/reservations/${orderNo}`);
    if (!res.ok) throw new Error("查询失败");
    const r = await res.json();

    const content = document.getElementById("detailContent");
    content.innerHTML = `
      <div class="detail-row"><span class="detail-label">订单号</span><span class="detail-value">${r.order_no}</span></div>
      <div class="detail-row"><span class="detail-label">餐厅名称</span><span class="detail-value">${r.restaurant_name}</span></div>
      <div class="detail-row"><span class="detail-label">餐厅电话</span><span class="detail-value">${r.restaurant_phone}</span></div>
      <div class="detail-row"><span class="detail-label">预约人</span><span class="detail-value">${r.guest_name}<br>${r.guest_phone}</span></div>
      <div class="detail-row"><span class="detail-label">预约时间</span><span class="detail-value">${formatDate(r.reservation_datetime)}</span></div>
      <div class="detail-row"><span class="detail-label">人数</span><span class="detail-value">成人 ${r.adults}，儿童 ${r.children}</span></div>
      <div class="detail-row"><span class="detail-label">备注</span><span class="detail-value">${r.notes || "-"}</span></div>
      <div class="detail-row"><span class="detail-label">状态</span><span class="detail-value"><span class="status-badge status-${r.status}">${formatStatus(r.status)}</span></span></div>
      <div class="detail-row"><span class="detail-label">AI 通话结果</span><span class="detail-value">${r.ai_call_result || "-"}</span></div>
      <div class="detail-row"><span class="detail-label">短信通知</span><span class="detail-value">${r.sms_sent ? "已发送" : "未发送"}</span></div>
      <div class="detail-row"><span class="detail-label">创建时间</span><span class="detail-value">${formatDate(r.created_at)}</span></div>
    `;

    document.getElementById("detailModal").classList.remove("hidden");
  } catch (e) {
    alert(e.message);
  }
}

async function cancelOrder(orderNo) {
  if (!confirm("确定要取消该预约单吗？")) return;
  try {
    const res = await fetch(`${API}/api/reservations/${orderNo}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "cancelled" }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "取消失败");
    }
    loadReservations();
    document.getElementById("detailModal").classList.add("hidden");
  } catch (e) {
    alert(e.message);
  }
}

document.getElementById("refreshBtn").onclick = loadReservations;
document.getElementById("statusFilter").onchange = loadReservations;
document.getElementById("closeModal").onclick = () => {
  document.getElementById("detailModal").classList.add("hidden");
};
document.getElementById("detailModal").onclick = (e) => {
  if (e.target.id === "detailModal") {
    document.getElementById("detailModal").classList.add("hidden");
  }
};

loadReservations();
