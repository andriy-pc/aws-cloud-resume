document.addEventListener("DOMContentLoaded", async () => {
    try {
        const counterEl = document.querySelector(".counter");
        if (counterEl) {
            counterEl.textContent = "...";
        }
        const response = await fetch("/v1/visitors");
        if (!response.ok) throw new Error("Network response was not ok");
        const data = await response.json();
        if (counterEl) {
            counterEl.textContent = `${data.visitors_count}`;
            counterEl.setAttribute("aria-label", `Total visitors ${data.visitors_count}`);
            counterEl.classList.remove("bump");
            // trigger reflow to restart animation if class existed
            // eslint-disable-next-line no-unused-expressions
            counterEl.offsetHeight;
            counterEl.classList.add("bump");
        }
    } catch (error) {
        console.error("Failed to fetch visitors count:", error);
        const counterEl = document.querySelector(".counter");
        if (counterEl) {
            counterEl.textContent = "N/A";
            counterEl.setAttribute("aria-label", "Visitor count unavailable");
        }
    }
});
