const cities = [
  ["Vancouver", "Canada", "BC Place"],
  ["Toronto", "Canada", "BMO Field"],
  ["Guadalajara", "Mexico", "Estadio Akron"],
  ["Mexico City", "Mexico", "Estadio Azteca"],
  ["Monterrey", "Mexico", "Estadio BBVA"],
  ["Atlanta", "United States", "Mercedes-Benz Stadium"],
  ["Boston", "United States", "Gillette Stadium"],
  ["Dallas", "United States", "AT&T Stadium"],
  ["Houston", "United States", "NRG Stadium"],
  ["Kansas City", "United States", "Arrowhead Stadium"],
  ["Los Angeles", "United States", "SoFi Stadium"],
  ["Miami", "United States", "Hard Rock Stadium"],
  ["New York/New Jersey", "United States", "MetLife Stadium"],
  ["Philadelphia", "United States", "Lincoln Financial Field"],
  ["San Francisco Bay Area", "United States", "Levi's Stadium"],
  ["Seattle", "United States", "Lumen Field"]
];

const grid = document.querySelector("#city-grid");
const buttons = document.querySelectorAll(".filter-button");

function renderCities(filter = "all") {
  grid.innerHTML = "";

  cities
    .filter(([, country]) => filter === "all" || country === filter)
    .forEach(([name, country, stadium]) => {
      const card = document.createElement("article");
      card.className = "city-card";
      card.dataset.country = country;
      card.innerHTML = `
        <strong>${country}</strong>
        <h3>${name}</h3>
        <p>${stadium}</p>
      `;
      grid.appendChild(card);
    });
}

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    buttons.forEach((item) => {
      item.classList.remove("is-active");
      item.setAttribute("aria-selected", "false");
    });
    button.classList.add("is-active");
    button.setAttribute("aria-selected", "true");
    renderCities(button.dataset.filter);
  });
});

function updateCountdown() {
  const now = new Date();
  const kickoff = new Date("2026-06-11T19:00:00-05:00");
  const final = new Date("2026-07-19T15:00:00-04:00");
  const label = document.querySelector("#countdown-label");
  const days = document.querySelector("#countdown-days");
  const detail = document.querySelector("#countdown-detail");

  let target = kickoff;
  let text = "開幕まで";

  if (now >= kickoff && now < final) {
    target = final;
    text = "決勝まで";
  } else if (now >= final) {
    label.textContent = "Tournament";
    days.textContent = "2026";
    detail.textContent = "開催記録";
    return;
  }

  const diff = target - now;
  const remainingDays = Math.max(0, Math.ceil(diff / 86400000));
  label.textContent = text;
  days.textContent = String(remainingDays);
  detail.textContent = remainingDays === 1 ? "day" : "days";
}

renderCities();
updateCountdown();
