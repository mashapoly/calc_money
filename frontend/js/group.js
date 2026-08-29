const params = new URLSearchParams(window.location.search);
const groupId = params.get("id");

if (!groupId) {
  window.location.href = "index.html";
}

if (!Api.getToken()) {
  const redirect = encodeURIComponent(`group.html?id=${groupId}`);
  window.location.href = `login.html?redirect=${redirect}`;
}

const user = Api.getUser();

let currentGroup = null;
let currentMembers = [];
let currentExpenses = [];

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

function money(amount, opts) {
  return Api.formatMoney(amount, currentGroup ? currentGroup.currency : "RUB", opts);
}

// ---- Tabs ----

const TAB_IDS = ["mybalance", "expenses", "alldebts", "analytics"];

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    TAB_IDS.forEach((id) => {
      document.getElementById(`tab-${id}`).style.display = id === tab ? "block" : "none";
    });
  });
});

// ---- Add-expense modal ----

const modalOverlay = document.getElementById("modal-overlay");

function openModal() {
  modalOverlay.classList.add("open");
}

function closeModal() {
  modalOverlay.classList.remove("open");
}

document.getElementById("open-expense-btn").addEventListener("click", openModal);
document.getElementById("modal-close").addEventListener("click", closeModal);
modalOverlay.addEventListener("click", (e) => {
  if (e.target === modalOverlay) closeModal();
});

// ---- Expense detail modal ----

const detailOverlay = document.getElementById("detail-modal-overlay");

function openDetailModal(exp) {
  document.getElementById("detail-title").textContent = exp.description;

  const date = new Date(exp.created_at).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const schemeRows = exp.shares
    .map((s) => {
      if (s.user_id === exp.paid_by_id) {
        return `
          <div class="scheme-row">
            <span class="scheme-who">${escapeHtml(s.username)} <span class="scheme-payer-tag">оплатил(а)</span></span>
            <span>${money(s.share_amount)}</span>
          </div>`;
      }
      return `
        <div class="scheme-row">
          <span>${escapeHtml(s.username)}<span class="debt-arrow">→</span>${escapeHtml(exp.paid_by_username)}</span>
          <span>${money(s.share_amount)}</span>
        </div>`;
    })
    .join("");

  document.getElementById("detail-body").innerHTML = `
    <div class="scheme-summary"><span class="scheme-amount">${money(exp.amount)}</span></div>
    <div class="scheme-meta">Заплатил(а) ${escapeHtml(exp.paid_by_username)} · ${date}</div>
    ${schemeRows}
  `;

  detailOverlay.classList.add("open");
}

document.getElementById("detail-modal-close").addEventListener("click", () => detailOverlay.classList.remove("open"));
detailOverlay.addEventListener("click", (e) => {
  if (e.target === detailOverlay) detailOverlay.classList.remove("open");
});

// ---- Load group ----

async function loadGroup() {
  currentGroup = await Api.request(`/api/groups/${groupId}`);
  currentMembers = currentGroup.members;

  document.getElementById("group-name").textContent = currentGroup.name;

  const membersEl = document.getElementById("members-list");
  membersEl.innerHTML = currentMembers
    .map((m) => `<span class="member-chip">${escapeHtml(m.username)}</span>`)
    .join("");

  const paidBySelect = document.getElementById("exp-paid-by");
  paidBySelect.innerHTML = currentMembers
    .map((m) => `<option value="${m.user_id}">${escapeHtml(m.username)}</option>`)
    .join("");
  if (user) paidBySelect.value = String(user.id);

  renderParticipants();
}

function renderParticipants() {
  const splitType = document.querySelector('input[name="split-type"]:checked').value;
  const listEl = document.getElementById("participants-list");

  listEl.innerHTML = currentMembers
    .map((m) => {
      const amountInput =
        splitType === "custom"
          ? `<input type="number" step="0.01" min="0" class="participant-amount" data-user="${m.user_id}" placeholder="0.00" />`
          : "";
      return `
        <div class="checkbox-row">
          <input type="checkbox" class="ios-checkbox participant-check" data-user="${m.user_id}" checked />
          <span class="participant-name">${escapeHtml(m.username)}</span>
          ${amountInput}
        </div>`;
    })
    .join("");
}

document.querySelectorAll('input[name="split-type"]').forEach((el) => {
  el.addEventListener("change", renderParticipants);
});

// ---- Expenses ----

function renderExpenses() {
  const listEl = document.getElementById("expenses-list");
  if (!currentExpenses.length) {
    listEl.innerHTML = '<div class="empty">Пока нет трат — добавьте первую кнопкой «+ Добавить трату»</div>';
    return;
  }
  listEl.innerHTML = "";
  currentExpenses.forEach((exp) => {
    const date = new Date(exp.created_at).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
    const row = document.createElement("div");
    row.className = "expense-row";
    row.style.cursor = "pointer";
    row.innerHTML = `
      <div class="expense-head">
        <span class="desc">${escapeHtml(exp.description)}</span>
        <span class="amount">${money(exp.amount)}</span>
      </div>
      <div class="expense-meta">Заплатил(а): ${escapeHtml(exp.paid_by_username)} · ${date}</div>`;
    row.addEventListener("click", () => openDetailModal(exp));
    listEl.appendChild(row);
  });
}

async function loadExpenses() {
  currentExpenses = await Api.request(`/api/groups/${groupId}/expenses`);
  renderExpenses();
}

document.getElementById("expense-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("expense-error");
  errorEl.textContent = "";

  const description = document.getElementById("exp-description").value.trim();
  const amount = parseFloat(document.getElementById("exp-amount").value);
  const paidById = parseInt(document.getElementById("exp-paid-by").value, 10);
  const splitType = document.querySelector('input[name="split-type"]:checked').value;

  const checks = Array.from(document.querySelectorAll(".participant-check"));
  const selected = checks.filter((c) => c.checked).map((c) => parseInt(c.dataset.user, 10));

  if (!selected.length) {
    errorEl.textContent = "Выберите хотя бы одного участника";
    return;
  }

  const participants = selected.map((uid) => {
    if (splitType === "custom") {
      const input = document.querySelector(`.participant-amount[data-user="${uid}"]`);
      return { user_id: uid, share_amount: parseFloat(input.value || "0") };
    }
    return { user_id: uid };
  });

  try {
    await Api.request(`/api/groups/${groupId}/expenses`, {
      method: "POST",
      body: {
        description,
        amount,
        paid_by_id: paidById,
        split_type: splitType,
        participants,
      },
    });
    document.getElementById("expense-form").reset();
    renderParticipants();
    closeModal();
    loadAnalytics();
    // UI updates for this client also arrive via the group's WebSocket broadcast.
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

// ---- Balances (personal + group-wide debts) ----

function renderBalances(data) {
  renderSummary(data);

  const mine = user
    ? data.debts
        .filter((d) => d.to_user_id === user.id || d.from_user_id === user.id)
        .map((d) => {
          const owedToMe = d.to_user_id === user.id;
          return {
            name: owedToMe ? d.from_username : d.to_username,
            amount: owedToMe ? d.amount : -d.amount,
          };
        })
    : [];

  const balanceEl = document.getElementById("mybalance-list");
  balanceEl.innerHTML = mine.length
    ? mine
        .map(
          (b) => `
          <div class="debt-row">
            <span>${escapeHtml(b.name)}</span>
            <span class="badge ${b.amount > 0 ? "positive" : "negative"}">${money(b.amount, { signed: true })}</span>
          </div>`
        )
        .join("")
    : '<div class="empty">Все в расчёте — никто никому не должен</div>';

  const allEl = document.getElementById("all-debts-list");
  allEl.innerHTML = data.debts.length
    ? data.debts
        .map(
          (d) => `
          <div class="debt-row">
            <span><strong>${escapeHtml(d.from_username)}</strong><span class="debt-arrow">→</span><strong>${escapeHtml(d.to_username)}</strong></span>
            <span class="badge neutral">${money(d.amount)}</span>
          </div>`
        )
        .join("")
    : '<div class="empty">Все в расчёте, переводов не требуется</div>';
}

function renderSummary(data) {
  const valueEl = document.getElementById("my-balance");
  const hintEl = document.getElementById("my-balance-hint");
  const mine = user && data.balances.find((b) => b.user_id === user.id);

  if (!mine) {
    valueEl.textContent = "—";
    hintEl.textContent = "Нет данных";
    return;
  }

  valueEl.textContent = money(mine.balance, { signed: true });
  if (mine.balance > 0.004) {
    hintEl.textContent = "вам должны вернуть эту сумму";
  } else if (mine.balance < -0.004) {
    hintEl.textContent = "столько вы должны группе";
  } else {
    hintEl.textContent = "вы в расчёте со всеми";
  }
}

async function loadBalances() {
  const data = await Api.request(`/api/groups/${groupId}/balances`);
  renderBalances(data);
}

// ---- Analytics ----

function monthLabel(monthStr) {
  const [y, m] = monthStr.split("-").map(Number);
  const d = new Date(y, m - 1, 1);
  const label = d.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function renderAnalytics(data) {
  const listEl = document.getElementById("analytics-list");
  if (!data.months.length) {
    listEl.innerHTML = '<div class="empty">Пока нет трат для анализа</div>';
    return;
  }

  const maxTotal = Math.max(...data.months.map((m) => m.group_total), 1);

  listEl.innerHTML = data.months
    .slice()
    .reverse()
    .map((m) => {
      const groupPct = Math.min(100, Math.round((m.group_total / maxTotal) * 100));
      const minePct = Math.min(100, Math.round((m.my_total / maxTotal) * 100));
      return `
        <div class="analytics-row">
          <div class="analytics-month">${escapeHtml(monthLabel(m.month))}</div>
          <div>
            <div class="analytics-bar-label"><span>Потратила группа</span><span>${money(m.group_total)}</span></div>
            <div class="analytics-bar-track"><div class="analytics-bar-fill group" style="width:${groupPct}%"></div></div>
          </div>
          <div>
            <div class="analytics-bar-label"><span>Ваша доля</span><span>${money(m.my_total)}</span></div>
            <div class="analytics-bar-track"><div class="analytics-bar-fill mine" style="width:${minePct}%"></div></div>
          </div>
        </div>`;
    })
    .join("");
}

async function loadAnalytics() {
  const data = await Api.request(`/api/groups/${groupId}/analytics`);
  renderAnalytics(data);
}

// ---- WebSocket (live updates) ----

let wsClosedByUs = false;

function connectWs() {
  const dot = document.getElementById("live-dot");
  const ws = new WebSocket(Api.wsUrl(`/ws/groups/${groupId}?token=${encodeURIComponent(Api.getToken())}`));

  ws.onopen = () => dot.classList.add("on");
  ws.onclose = () => {
    dot.classList.remove("on");
    if (!wsClosedByUs) setTimeout(connectWs, 3000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.event === "expense_added") {
      currentExpenses.unshift(msg.payload);
      renderExpenses();
      loadAnalytics();
    } else if (msg.event === "balances_updated") {
      renderBalances(msg.payload);
    } else if (msg.event === "member_joined" || msg.event === "member_left") {
      loadGroup();
    } else if (msg.event === "member_removed") {
      if (user && msg.payload.user_id === user.id) {
        wsClosedByUs = true;
        ws.close();
        alert("Вас удалили из этой группы.");
        window.location.href = "index.html";
      } else {
        loadGroup();
      }
    } else if (msg.event === "group_updated") {
      currentGroup = msg.payload;
      currentMembers = currentGroup.members;
      document.getElementById("group-name").textContent = currentGroup.name;
      Promise.all([loadExpenses(), loadBalances(), loadAnalytics()]);
    } else if (msg.event === "group_deleted") {
      wsClosedByUs = true;
      ws.close();
      alert("Эта группа была удалена.");
      window.location.href = "index.html";
    }
  };
}

// ---- Init ----

(async function init() {
  try {
    await loadGroup();
    await Promise.all([loadExpenses(), loadBalances(), loadAnalytics()]);
    connectWs();
  } catch (err) {
    document.getElementById("group-name").textContent = "Ошибка загрузки группы";
    console.error(err);
  }
})();
