Api.redirectIfLoggedIn();

const form = document.getElementById("login-form");
const errorEl = document.getElementById("error");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const data = await Api.request("/api/auth/login", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
    Api.setSession(data.access_token, data.user);

    const params = new URLSearchParams(window.location.search);
    const redirect = params.get("redirect");
    window.location.href = redirect ? redirect : "index.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
