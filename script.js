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
const header = document.querySelector(".site-header");
const menuToggle = document.querySelector(".menu-toggle");
const navLinks = document.querySelectorAll(".nav a");
const articleSearch = document.querySelector("#article-search");
const articleCards = document.querySelectorAll(".article-card");
const articleFilters = document.querySelectorAll(".content-filter");
const articleCount = document.querySelector("#article-count");
const guideSearch = document.querySelector("#guide-search");
const guideCards = document.querySelectorAll(".guide-card");
const guideCount = document.querySelector("#guide-count");
const backToTop = document.querySelector(".back-to-top");

let activeArticleCategory = "all";

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
      item.setAttribute("aria-pressed", "false");
    });
    button.classList.add("is-active");
    button.setAttribute("aria-pressed", "true");
    renderCities(button.dataset.filter);
  });

  button.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      button.click();
    }
  });
});

function normalize(value) {
  return value.toLowerCase().trim();
}

function cardMatchesSearch(card, query) {
  if (!query) {
    return true;
  }

  const text = `${card.textContent} ${card.dataset.keywords || ""} ${card.dataset.guideKeywords || ""}`;
  return normalize(text).includes(query);
}

function updateArticleCards() {
  const query = normalize(articleSearch?.value || "");
  let visible = 0;

  articleCards.forEach((card) => {
    const categoryMatch = activeArticleCategory === "all" || card.dataset.category === activeArticleCategory;
    const searchMatch = cardMatchesSearch(card, query);
    const isVisible = categoryMatch && searchMatch;
    card.classList.toggle("is-hidden", !isVisible);
    if (isVisible) {
      visible += 1;
    }
  });

  if (articleCount) {
    articleCount.textContent = `${visible} topic${visible === 1 ? "" : "s"} shown`;
  }
}

function updateGuideCards() {
  const query = normalize(guideSearch?.value || "");
  let visible = 0;

  guideCards.forEach((card) => {
    const isVisible = cardMatchesSearch(card, query);
    card.classList.toggle("is-hidden", !isVisible);
    if (isVisible) {
      visible += 1;
    }
  });

  if (guideCount) {
    guideCount.textContent = `${visible} guide${visible === 1 ? "" : "s"} shown`;
  }
}

articleFilters.forEach((button) => {
  button.addEventListener("click", () => {
    articleFilters.forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    activeArticleCategory = button.dataset.category;
    updateArticleCards();
  });
});

articleSearch?.addEventListener("input", updateArticleCards);
guideSearch?.addEventListener("input", updateGuideCards);

menuToggle?.addEventListener("click", () => {
  const isOpen = header.classList.toggle("nav-open");
  menuToggle.setAttribute("aria-expanded", String(isOpen));
  menuToggle.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
});

navLinks.forEach((link) => {
  link.addEventListener("click", () => {
    header.classList.remove("nav-open");
    menuToggle?.setAttribute("aria-expanded", "false");
    menuToggle?.setAttribute("aria-label", "Open navigation menu");
  });
});

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener("click", (event) => {
    const target = document.querySelector(link.getAttribute("href"));
    if (!target) {
      return;
    }
    event.preventDefault();
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

function updateBackToTop() {
  backToTop?.classList.toggle("is-visible", window.scrollY > 520);
}

backToTop?.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
});

window.addEventListener("scroll", updateBackToTop, { passive: true });

const revealTargets = document.querySelectorAll(
  ".topic-card, .article-card, .utility-card, .spotlight-card, .history-card, .club-grid article, .guide-list article, .city-card, .info-grid article"
);

if ("IntersectionObserver" in window) {
  const revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );

  revealTargets.forEach((target) => {
    target.classList.add("reveal-on-scroll");
    revealObserver.observe(target);
  });
} else {
  revealTargets.forEach((target) => target.classList.add("is-visible"));
}

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
updateArticleCards();
updateGuideCards();
updateBackToTop();
