// Countdown widget for the event page.
document.querySelectorAll(".countdown").forEach((el) => {
  const t = new Date(el.dataset.target);
  setInterval(() => { el.textContent = Math.max(0, Math.round((t - Date.now()) / 1000)) + " s"; }, 1000);
});
