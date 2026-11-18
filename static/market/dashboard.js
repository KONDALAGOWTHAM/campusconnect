const chartData = document.querySelector("#listing-breakdown");
if (chartData && window.Chart) {
  const { labels, values } = JSON.parse(chartData.textContent);
  const palette = ["#8178fa", "#10a78d", "#e8a93a", "#6751df", "#e16580"];
  new Chart(document.querySelector("#status-chart"), {
    type: "doughnut",
    data: {labels, datasets: [{data: values, backgroundColor: palette, borderWidth: 0}]},
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: !matchMedia("(prefers-reduced-motion: reduce)").matches,
      plugins: {legend: {display: false}},
    },
  });
}
