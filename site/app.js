// SPDX-License-Identifier: Apache-2.0
const BANNER = "demo, deterministic offline model, not a production security boundary";

let precomputed = {};
let corpusExpected = {};

async function boot() {
  if (typeof loadPyodide === "undefined") {
    throw new Error("loadPyodide is not defined");
  }
  const pyodide = await loadPyodide({ indexURL: "./pyodide/" });
  const wheelData = await fetch("sqlglot-30.31.0-py3-none-any.whl").then((r) =>
    r.arrayBuffer()
  );
  await pyodide.unpackArchive(wheelData, "wheel");
  for (const file of ["guard.py", "policy.py", "model.py"]) {
    const src = await fetch(`python/${file}`).then((r) => r.text());
    pyodide.FS.writeFile(file, src, { encoding: "utf8" });
  }
  precomputed = await fetch("precomputed.json").then((r) => r.json());
  corpusExpected = await fetch("corpus_expected.json").then((r) => r.json());
  window.pyodide = pyodide;
  window.pyodideBoot = "ready";
}

function render(payload) {
  document.getElementById("out").textContent = JSON.stringify(payload, null, 2);
}

async function runGuard(question, sqlText) {
  const py = window.pyodide;
  if (!py) {
    return { code: "LOADING", detail: "pyodide" };
  }
  if (sqlText) {
    py.globals.set("input_sql", sqlText);
    return py.runPythonAsync(
      "from guard import check\n{'code': check(input_sql).code, 'sql': check(input_sql).sql or ''}"
    );
  }
  py.globals.set("input_q", question);
  return py.runPythonAsync(
    "from model import StubModel\nfrom guard import check\nm=StubModel()\ns=m.to_sql(input_q)\n{'code': 'NO_TEMPLATE' if s is None else check(s).code, 'sql': (check(s).sql if s else '')}"
  );
}

async function runCorpusCheck() {
  await bootPromise;
  const py = window.pyodide;
  const out = {};
  for (const [caseId, entry] of Object.entries(corpusExpected)) {
    py.globals.set("input_sql", entry.sql);
    const code = await py.runPythonAsync("from guard import check\ncheck(input_sql).code");
    out[caseId] = code;
  }
  return out;
}

const bootPromise = boot().catch((err) => {
  window.pyodideBoot = "error";
  render({ code: "BOOT_ERROR", detail: String(err) });
  throw err;
});

window.runCorpusCheck = runCorpusCheck;

document.getElementById("run").addEventListener("click", async () => {
  try {
    await bootPromise;
  } catch {
    return;
  }
  const question = document.getElementById("question").value;
  const sql = document.getElementById("sql").value;
  const result = await runGuard(question, sql);
  const norm = question.trim().toLowerCase().replace(/\s+/g, " ");
  const key = [norm, result.sql || "", precomputed.seed_hash || ""].join("|");
  const rows = precomputed.rows?.[key];
  render({
    banner: BANNER,
    ...result,
    rows: rows || "no precomputed rows for this query",
  });
});

document.querySelectorAll("#examples button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const q = btn.dataset.q;
    if (q.startsWith("SELECT")) {
      document.getElementById("sql").value = q;
      document.getElementById("question").value = "";
    } else {
      document.getElementById("question").value = q;
      document.getElementById("sql").value = "";
    }
  });
});
