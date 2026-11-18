const filterForm = document.querySelector(".filters form");
const result = document.querySelector(".results-meta strong");
const cards = [...document.querySelectorAll(".product-card")];
const grid = document.querySelector(".product-grid");
const params = new URLSearchParams(location.search);
const sorts = {
  newest: (a,b) => Number(b.dataset.id) - Number(a.dataset.id),
  oldest: (a,b) => Number(a.dataset.id) - Number(b.dataset.id),
  low: (a,b) => Number(a.dataset.price) - Number(b.dataset.price),
  high: (a,b) => Number(b.dataset.price) - Number(a.dataset.price),
};
for (const field of filterForm.elements) {
  if (field.name && params.has(field.name)) field.value = params.get(field.name);
}
const data = new FormData(filterForm);
const query = (data.get("q") || "").trim().toLowerCase();
const min = data.get("min_price");
const max = data.get("max_price");
let count = 0;
for (const card of cards.sort(sorts[data.get("sort")] || sorts.newest)) {
  const visible = card.dataset.search.includes(query)
    && ["category", "college", "condition"].every(key => !data.get(key) || data.get(key) === card.dataset[key])
    && (!min || Number(card.dataset.price) >= Number(min))
    && (!max || Number(card.dataset.price) <= Number(max));
  card.hidden = !visible;
  if (visible) count++;
  grid.append(card);
}
result.textContent = count === 1 ? "1 result" : `${count} results`;
if (!count) {
  const empty = document.createElement("p");
  empty.className = "empty panel";
  empty.textContent = "No matching items. Try clearing your filters.";
  grid.append(empty);
}
