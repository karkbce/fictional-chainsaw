async function loadData() {
  const res = await fetch("./data/latest.json", { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load data: ${res.status}`);
  return res.json();
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function setLink(id, href) {
  const el = document.getElementById(id);
  if (el && href) el.href = href;
}

function renderMeta(data) {
  const fetchedAt = new Date(data.fetched_at);
  const rowCount = data.table?.row_count ?? 0;
  const text = `Last updated ${fetchedAt.toLocaleString()} • ${rowCount} rows`;
  setText("meta", text);
  setLink("sourceLink", data.source_url);
}

function renderGraph(data) {
  const img = document.getElementById("graphImage");
  const caption = document.getElementById("graphCaption");
  const remoteLink = document.getElementById("graphRemoteLink");
  const graph = data.graph || {};

  if (graph.local_path) {
    img.src = `./${graph.local_path.replace(/^\.?\//, "")}`;
  } else if (graph.remote_url) {
    img.src = graph.remote_url;
  } else {
    img.remove();
    setText("graphCaption", "Graph image not found in the latest scrape.");
    if (remoteLink) remoteLink.style.display = "none";
    return;
  }

  img.alt = graph.caption || "Wikipedia polling graph";
  caption.textContent = graph.caption || "";
  if (graph.remote_url) {
    remoteLink.href = graph.remote_url;
  } else {
    remoteLink.style.display = "none";
  }
}

function buildTable(columns, rows) {
  const table = document.getElementById("pollTable");
  table.innerHTML = "";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const col of columns) {
    const th = document.createElement("th");
    th.textContent = col;
    headRow.appendChild(th);
  }
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const col of columns) {
      const td = document.createElement("td");
      td.textContent = row[col] ?? "";
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
}

function renderTable(data) {
  const tableData = data.table || {};
  const columns = tableData.columns || [];
  const allRows = tableData.rows || [];
  const summary = document.getElementById("tableSummary");
  const input = document.getElementById("searchInput");

  const updateRows = () => {
    const q = input.value.trim().toLowerCase();
    const rows = q
      ? allRows.filter((row) =>
          columns.some((col) => String(row[col] ?? "").toLowerCase().includes(q)),
        )
      : allRows;
    buildTable(columns, rows);
    summary.textContent = `${rows.length} shown / ${allRows.length} total`;
  };

  input.addEventListener("input", updateRows);
  updateRows();
}

function renderNotes(data) {
  const list = document.getElementById("notesList");
  list.innerHTML = "";
  const notes = (data.notes && data.notes.length ? data.notes : ["No notes"]) || ["No notes"];
  for (const note of notes) {
    const li = document.createElement("li");
    li.textContent = note;
    list.appendChild(li);
  }
}

async function init() {
  try {
    const data = await loadData();
    renderMeta(data);
    renderGraph(data);
    renderTable(data);
    renderNotes(data);
  } catch (err) {
    setText("meta", `Error: ${err.message}`);
    setText("graphCaption", "Could not load latest JSON data.");
  }
}

init();

