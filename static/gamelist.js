document.addEventListener("click", async (e) => {
    const row = e.target.closest("tr");
    if (!row) return;

    const id = row.dataset.id;

    if (e.target.classList.contains("save-btn")) {
        const data = {
            id,
            title: row.querySelector(".input-title").value,
            platform: row.querySelector(".input-platform").value,
            status: row.querySelector(".input-status").value,
            multiplayer: row.querySelector(".input-multiplayer").checked ? 1 : 0,
            coop: row.querySelector(".input-coop").checked ? 1 : 0,
            genre: row.querySelector(".input-genre").value,
            playtime: row.querySelector(".input-playtime").value,
            length: row.querySelector(".input-length").value,
        };

        const res = await fetch("/games/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        const result = await res.json();
        if (result.success) {
            alert("Saved!");
        } else {
            alert("Failed: " + result.error);
        }
    }

    if (e.target.classList.contains("delete-btn")) {
        const res = await fetch("/games/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id }),
        });

        const result = await res.json();
        if (result.success) {
            row.remove(); // remove row from DOM
        } else {
            alert("Failed to delete: " + result.error);
        }
    }
});

document.getElementById("add-game-btn").addEventListener("click", () => {
    const tbody = document.querySelector("table tbody");

    const newRow = document.createElement("tr");
    newRow.classList.add("new-game-row");

    newRow.innerHTML = `
        <td></td>
        <td><input type="text" class="input-title" placeholder="Game Name" required></td>
        <td><input type="text" class="input-platform" placeholder="Platform" required></td>
        <td><input type="text" class="input-status"></td>
        <td><input type="checkbox" class="input-multiplayer"></td>
        <td><input type="checkbox" class="input-coop"></td>
        <td><input type="text" class="input-genre"></td>
        <td><input type="number" class="input-playtime" value="0"></td>
        <td><input type="number" class="input-length" value="0"></td>
        <td>
            <button class="save-new-btn">Save</button>
            <button class="cancel-new-btn">Cancel</button>
        </td>
    `;

    tbody.prepend(newRow);
});

// Save new game
document.addEventListener("click", async (e) => {
    if (e.target.classList.contains("save-new-btn")) {
        const row = e.target.closest("tr");

        const title = row.querySelector(".input-title").value.trim();
        const platform = row.querySelector(".input-platform").value.trim();

        if (!title || !platform) {
            alert("Game name and platform are required.");
            return;
        }

        const data = {
            title,
            platform,
            status: row.querySelector(".input-status").value,
            multiplayer: row.querySelector(".input-multiplayer").checked ? 1 : 0,
            coop: row.querySelector(".input-coop").checked ? 1 : 0,
            genre: row.querySelector(".input-genre").value,
            playtime: row.querySelector(".input-playtime").value || 0,
            length: row.querySelector(".input-length").value || 0
        };

        const res = await fetch("/games/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        });

        const result = await res.json();
        if (result.success) {
            // Optional: reload page or fetch new data
            location.reload(); // easiest option
        } else {
            alert("Failed to add game: " + result.error);
        }
    }

    if (e.target.classList.contains("cancel-new-btn")) {
        e.target.closest("tr").remove();
    }
});

document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.querySelector("table tbody");
    const headers = document.querySelectorAll(".sortable");
    let currentSortKey = "title";  // default column
    let sortAsc = true;

    function getCellValue(row, key) {
        const inputMap = {
            title: ".input-title",
            platform: ".input-platform",
            status: ".input-status",
            multiplayer: ".input-multiplayer",
            coop: ".input-coop",
            genre: ".input-genre",
            playtime: ".input-playtime",
            length: ".input-length"
        };

        const cell = row.querySelector(inputMap[key]);
        if (!cell) return "";

        if (cell.type === "checkbox") {
            return cell.checked ? 1 : 0;
        } else if (cell.type === "number") {
            return parseFloat(cell.value) || 0;
        } else {
            return cell.value.toLowerCase();
        }
    }

    function sortTable(key) {
        const rows = Array.from(tbody.querySelectorAll("tr"));
        rows.sort((a, b) => {
            const aVal = getCellValue(a, key);
            const bVal = getCellValue(b, key);

            if (aVal < bVal) return sortAsc ? -1 : 1;
            if (aVal > bVal) return sortAsc ? 1 : -1;
            return 0;
        });

        // Remove old rows and append sorted
        rows.forEach(row => tbody.appendChild(row));
    }

    headers.forEach(header => {
        header.addEventListener("click", () => {
            const key = header.dataset.key;
            if (currentSortKey === key) {
                sortAsc = !sortAsc;  // toggle direction
            } else {
                currentSortKey = key;
                sortAsc = true;
            }
            sortTable(currentSortKey);
        });
    });

    // Initial sort on load
    sortTable(currentSortKey);
});

