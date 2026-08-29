Api.redirectIfLoggedIn();

const form = document.getElementById("register-form");
const errorEl = document.getElementById("error");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorEl.textContent = "";

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

  try {
    const data = await Api.request("/api/auth/register", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
    Api.setSession(data.access_token, data.user);
    window.location.href = "index.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
