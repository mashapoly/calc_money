Api.requireAuth();

const user = Api.getUser();
document.getElementById("whoami").textContent = user ? user.username : "";

document.getElementById("logout-btn").addEventListener("click", () => {
  Api.clearSession();
  window.location.href = "login.html";
});

function buildCurrencyPicker(name, selected) {
  return Api.CURRENCIES.map(
    (c) => `
      <input type="radio" name="${name}" id="${name}-${c.code}" value="${c.code}" ${c.code === selected ? "checked" : ""} />
      <label for="${name}-${c.code}"><span class="currency-symbol">${c.symbol}</span>${c.code}</label>`
  ).join("");
}

document.getElementById("group-currency-picker").innerHTML = buildCurrencyPicker("create-currency", "RUB");

function extractInviteCode(raw) {
  const value = raw.trim();
  try {
    const url = new URL(value);
    const fromParam = url.searchParams.get("join");
    if (fromParam) return fromParam;
  } catch (e) {
    // not a URL, treat as raw code
  }
  return value;
}

async function loadGroups() {
  const listEl = document.getElementById("groups-list");
  try {
    const groups = await Api.request("/api/groups");
    if (!groups.length) {
      listEl.innerHTML = '<div class="empty">Пока нет групп. Создайте первую или войдите по ссылке.</div>';
      return;
    }
    listEl.innerHTML = "";
    listEl.className = "groups-grid";
    groups.forEach((g) => {
      const card = document.createElement("div");
      card.className = "group-card";
      const letter = (g.name.trim()[0] || "?").toUpperCase();
      card.innerHTML = `
        <a class="group-card-link" href="group.html?id=${g.id}">
          <div class="group-card-icon" style="background:${Api.avatarColor(g.name)}">${escapeHtml(letter)}</div>
          <div class="group-card-name">${escapeHtml(g.name)}</div>
          <div class="group-card-hint">Открыть →</div>
        </a>
        <div class="group-card-actions">
          <button class="group-card-icon-btn group-card-copy-btn" data-invite="${g.invite_code}" title="Скопировать ссылку-приглашение">🔗</button>
          <button class="group-card-icon-btn group-card-gear-btn" data-group-id="${g.id}" title="Настройки группы">⚙</button>
        </div>`;
      listEl.appendChild(card);
    });
  } catch (err) {
    listEl.innerHTML = `<div class="empty">Ошибка загрузки: ${escapeHtml(err.message)}</div>`;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.getElementById("groups-list").addEventListener("click", async (e) => {
  const copyBtn = e.target.closest(".group-card-copy-btn");
  if (copyBtn) {
    const url = `${window.location.origin}/index.html?join=${copyBtn.dataset.invite}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch (err) {
      const tmp = document.createElement("textarea");
      tmp.value = url;
      document.body.appendChild(tmp);
      tmp.select();
      document.execCommand("copy");
      document.body.removeChild(tmp);
    }
    const original = copyBtn.textContent;
    copyBtn.textContent = "✓";
    setTimeout(() => (copyBtn.textContent = original), 1200);
    return;
  }

  const gearBtn = e.target.closest(".group-card-gear-btn");
  if (gearBtn) openSettingsModal(gearBtn.dataset.groupId);
});

// ---- Group settings modal (edit / delete / leave / remove member) ----

let selectedGroup = null;
let selectedGroupId = null;

const settingsOverlay = document.getElementById("settings-modal-overlay");

async function openSettingsModal(groupId) {
  selectedGroupId = groupId;
  document.getElementById("settings-error").textContent = "";
  try {
    selectedGroup = await Api.request(`/api/groups/${groupId}`);
  } catch (err) {
    alert(`Не удалось загрузить группу: ${err.message}`);
    return;
  }

  document.getElementById("settings-name").value = selectedGroup.name;
  document.getElementById("settings-currency-picker").innerHTML = buildCurrencyPicker(
    "settings-currency",
    selectedGroup.currency
  );
  renderSettingsMembers();

  const isOwner = user && selectedGroup.owner_id === user.id;
  document.getElementById("delete-group-btn").style.display = isOwner ? "block" : "none";
  document.getElementById("leave-group-btn").style.display = isOwner ? "none" : "block";

  settingsOverlay.classList.add("open");
}

function closeSettingsModal() {
  settingsOverlay.classList.remove("open");
}

function renderSettingsMembers() {
  const isOwner = user && selectedGroup.owner_id === user.id;
  const listEl = document.getElementById("settings-members-list");

  listEl.innerHTML = selectedGroup.members
    .map((m) => {
      const isMemberOwner = m.user_id === selectedGroup.owner_id;
      const removeBtn =
        isOwner && !isMemberOwner
          ? `<button class="member-remove-btn" data-user="${m.user_id}" data-username="${escapeHtml(m.username)}">Удалить</button>`
          : "";
      return `
        <div class="member-row">
          <span class="member-row-name">${escapeHtml(m.username)}</span>
          ${isMemberOwner ? '<span class="member-row-tag">создатель</span>' : ""}
          ${removeBtn}
        </div>`;
    })
    .join("");
}

document.getElementById("settings-modal-close").addEventListener("click", closeSettingsModal);
settingsOverlay.addEventListener("click", (e) => {
  if (e.target === settingsOverlay) closeSettingsModal();
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("settings-error");
  errorEl.textContent = "";
  try {
    selectedGroup = await Api.request(`/api/groups/${selectedGroupId}`, {
      method: "PATCH",
      body: {
        name: document.getElementById("settings-name").value.trim(),
        currency: document.querySelector('input[name="settings-currency"]:checked').value,
      },
    });
    closeSettingsModal();
    loadGroups();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("delete-group-btn").addEventListener("click", async () => {
  if (!confirm(`Удалить группу «${selectedGroup.name}» вместе со всеми тратами? Это необратимо.`)) return;
  try {
    await Api.request(`/api/groups/${selectedGroupId}`, { method: "DELETE" });
    closeSettingsModal();
    loadGroups();
  } catch (err) {
    document.getElementById("settings-error").textContent = err.message;
  }
});

document.getElementById("leave-group-btn").addEventListener("click", async () => {
  if (!confirm(`Покинуть группу «${selectedGroup.name}»?`)) return;
  try {
    await Api.request(`/api/groups/${selectedGroupId}/leave`, { method: "POST" });
    closeSettingsModal();
    loadGroups();
  } catch (err) {
    document.getElementById("settings-error").textContent = err.message;
  }
});

document.getElementById("settings-members-list").addEventListener("click", async (e) => {
  const btn = e.target.closest(".member-remove-btn");
  if (!btn) return;

  const uid = btn.dataset.user;
  const uname = btn.dataset.username;
  if (!confirm(`Удалить «${uname}» из группы?`)) return;

  try {
    await Api.request(`/api/groups/${selectedGroupId}/members/${uid}`, { method: "DELETE" });
    selectedGroup = await Api.request(`/api/groups/${selectedGroupId}`);
    renderSettingsMembers();
  } catch (err) {
    document.getElementById("settings-error").textContent = err.message;
  }
});

document.getElementById("create-group-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("create-error");
  errorEl.textContent = "";
  const nameInput = document.getElementById("group-name");
  try {
    const group = await Api.request("/api/groups", {
      method: "POST",
      body: {
        name: nameInput.value.trim(),
        currency: document.querySelector('input[name="create-currency"]:checked').value,
      },
    });
    window.location.href = `group.html?id=${group.id}`;
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("join-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errorEl = document.getElementById("join-error");
  errorEl.textContent = "";
  const codeInput = document.getElementById("invite-code");
  const code = extractInviteCode(codeInput.value);
  try {
    const group = await Api.request("/api/groups/join", { method: "POST", body: { invite_code: code } });
    window.location.href = `group.html?id=${group.id}`;
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

async function handleAutoJoin() {
  const params = new URLSearchParams(window.location.search);
  const joinCode = params.get("join");
  if (!joinCode) return;

  const joinCard = document.getElementById("join-card");
  const statusEl = document.getElementById("join-status");
  joinCard.style.display = "block";

  try {
    const group = await Api.request("/api/groups/join", { method: "POST", body: { invite_code: joinCode } });
    statusEl.textContent = `Вы присоединились к группе «${group.name}». Переходим…`;
    setTimeout(() => (window.location.href = `group.html?id=${group.id}`), 600);
  } catch (err) {
    statusEl.textContent = `Не удалось присоединиться: ${err.message}`;
  }
}

handleAutoJoin();
loadGroups();
