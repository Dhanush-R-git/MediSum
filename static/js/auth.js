/**
 * If you want to add any client‐side form validation on login or registration,
 * place it here. For example, to prevent empty submits, or to show/hide password.
 */
document.addEventListener('DOMContentLoaded', () => {
  const loginForm = document.getElementById('login_form');
  if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
      // Basic client‐side check
      const user = document.getElementById('username').value.trim();
      const pw = document.getElementById('password').value.trim();
      if (!user || !pw) {
        e.preventDefault();
        alert("Username & password cannot be empty");
      }
    });
  }
});
