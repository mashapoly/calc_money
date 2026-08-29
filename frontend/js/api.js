// Тонкая обёртка над fetch: подставляет токен авторизации и разбирает ошибки API.

const Api = (() => {
  function getToken() {
    return localStorage.getItem("token");
  }

  function getUser() {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  }

  function setSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
  }

  function clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }

  async function request(path, { method = "GET", body, auth = true } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth) {
      const token = getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (res.status === 204) return null;

    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }

    if (!res.ok) {
      const message = (data && (data.detail || data.message)) || `Ошибка запроса (${res.status})`;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }

    return data;
  }

  function requireAuth() {
    if (!getToken()) {
      window.location.href = "login.html";
    }
  }

  function redirectIfLoggedIn() {
    if (getToken()) {
      window.location.href = "index.html";
    }
  }

  function wsUrl(path) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}${path}`;
  }

  const CURRENCIES = [
    { code: "RUB", symbol: "₽", label: "Рубль (₽)" },
    { code: "USD", symbol: "$", label: "Доллар ($)" },
    { code: "EUR", symbol: "€", label: "Евро (€)" },
    { code: "GBP", symbol: "£", label: "Фунт (£)" },
    { code: "KZT", symbol: "₸", label: "Тенге (₸)" },
  ];

  function currencySymbol(code) {
    const found = CURRENCIES.find((c) => c.code === code);
    return found ? found.symbol : code || "";
  }

  function formatMoney(amount, currency, { signed = false } = {}) {
    const sign = signed && amount > 0 ? "+" : "";
    return `${sign}${amount.toFixed(2)} ${currencySymbol(currency)}`.trim();
  }

  const AVATAR_COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#16a34a", "#0891b2"];

  function avatarColor(name) {
    let hash = 0;
    for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) % AVATAR_COLORS.length;
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
  }

  return {
    request,
    getToken,
    getUser,
    setSession,
    clearSession,
    requireAuth,
    redirectIfLoggedIn,
    wsUrl,
    CURRENCIES,
    currencySymbol,
    formatMoney,
    avatarColor,
  };
})();
