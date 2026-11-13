"""Hermetic integrity tests for the gcp-data-medallion Dataform repository."""

import hashlib
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
THIS_FILE = Path(__file__).resolve()

REQUIRED_VARS = (
    "bronze_project",
    "bronze_dataset",
    "silver_project",
    "silver_dataset",
    "gold_project",
    "gold_dataset",
    "gold_retail_project",
    "gold_retail_dataset",
    "pii_policy_tag",
    "pii_restricted_policy_tag",
    "pii_masked_policy_tag",
    "allow_untagged_pii",
    "filter_cdc_deletes",
    "cdc_lookback_days",
    "include_stream_orders",
    "include_batch_orders",
)

REQUIRED_FILES = (
    "workflow_settings.yaml",
    "LICENSE",
    ".gitignore",
    "CODEOWNERS",
    "Makefile",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "QUESTIONNAIRE.md",
    ".github/workflows/ci.yml",
    ".github/workflows/dataform-dryrun.yml",
    ".github/workflows/dataform-promote.yml",
    "envs/dev.compilation.json.example",
    "envs/staging.compilation.json.example",
    "envs/prod.compilation.json.example",
    "includes/audit_columns.js",
    "includes/policy_tags.js",
    "includes/scd_type2.js",
    "includes/cdc_helpers.js",
    "quality/silver_orders_quality.yaml",
    ".agents/skills/add-medallion-model/SKILL.md",
    ".agents/skills/setup-data-medallion/SKILL.md",
    ".agents/skills/split-domain-mesh/SKILL.md",
    "definitions/01_bronze/pos_orders_cdc.sqlx",
    "definitions/01_bronze/pos_orders_stream_cdc.sqlx",
    "definitions/01_bronze/pos_orders_batch_cdc.sqlx",
    "definitions/01_bronze/crm_customers_cdc.sqlx",
    "definitions/02_silver/fct_orders.sqlx",
    "definitions/02_silver/assert_fct_orders_quality.sqlx",
    "definitions/02_silver/dim_customers.sqlx",
    "definitions/03_gold/finance/mart_daily_revenue.sqlx",
    "definitions/03_gold/retail/mart_store_performance.sqlx",
)

MARKDOWN_DOC_FILES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    "QUESTIONNAIRE.md",
    ".agents/skills/add-medallion-model/SKILL.md",
    ".agents/skills/setup-data-medallion/SKILL.md",
    ".agents/skills/split-domain-mesh/SKILL.md",
)

# SHA-256 digests of forbidden internal identifiers so plaintext secrets stay out of the repo.
FORBIDDEN_TOKEN_SHA256 = {
    "4e41237f5f263ce5dc9566a6ba831e3b732297c006415ec51c16b440d4e7c962",
    "a1ff4908fbe5168909d20652cd786c91f25e62668cb7704e00b76b48bbd77061",
    "bf2e17a1a6bc6728a531b1f29fc3e9344836b4ee2dbc4826d52e7fad1ab903b4",
    "28a6c9ad99acc2abeef4831da37cf37001345f05fa7327562ee4a9b167019b04",
    "9df5c2af39fc3666ac0676a762ef08a86c0f0f7451976f7d290e329b07a5241e",
    "d43e610ed1d8b1bdf2fc1d636d5db802e331d6c3e8467e65f26b1ed874f5ad55",
    "bcaeb7aaf13db3381e1c0c07ca7d7c9e0b58bb1a77aa177c420d9ddc1f42b72f",
}
FORBIDDEN_TOKEN_LENGTHS = (6, 9, 12, 17)

FORBIDDEN_REGEXES = (
    (re.compile(r"@google\.com\b", re.IGNORECASE), "corporate email domain"),
    (re.compile(r"\.c\.googlers\.com\b", re.IGNORECASE), "corp hostname"),
    (re.compile(r"(?<![0-9a-fA-F])\d{12}(?![0-9a-fA-F])"), "12-digit GCP org or folder ID"),
    (re.compile(r"\b[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}\b"), "GCP billing account ID"),
)

# BEGIN_AI_BLACKLIST
AI_BLACKLIST = (
    "delve",
    "navigate",
    "foster",
    "champion",
    "streamline",
    "elevate",
    "harness",
    "orchestrate",
    "illuminate",
    "transcend",
    "demystify",
    "embrace",
    "unlock",
    "tapestry",
    "testament",
    "beacon",
    "realm",
    "landscape",
    "paradigm",
    "synergy",
    "facet",
    "nuance",
    "cornerstone",
    "journey",
    "blueprint",
    "paramount",
    "multifaceted",
    "vibrant",
    "pivotal",
    "holistic",
    "crucial",
    "comprehensive",
    "meticulous",
    "dynamic",
    "profound",
    "intricate",
    "furthermore",
    "moreover",
    "in conclusion",
    "at its core",
    "it is worth noting",
    "importantly",
    "in summary",
    "ultimately",
)
# END_AI_BLACKLIST

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\u200d"
    "\ufe0f"
    "]"
)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"}


def iter_repo_files():
    """Yield all tracked or working text files inside the repository."""
    for path in sorted(REPO_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        yield path


def parse_workflow_settings(yaml_text):
    """Parse top-level scalar settings and nested vars map using Python stdlib."""
    top_level = {}
    vars_map = {}
    in_vars = False

    for raw_line in yaml_text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            in_vars = False
            if ":" not in stripped:
                raise AssertionError(f"Invalid YAML line in workflow_settings.yaml: {raw_line}")
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            if key == "vars" and val == "":
                in_vars = True
                continue
            top_level[key] = _unquote_yaml(val)
        elif in_vars and indent >= 2:
            if ":" not in stripped:
                raise AssertionError(f"Invalid vars entry in workflow_settings.yaml: {raw_line}")
            key, val = stripped.split(":", 1)
            vars_map[key.strip()] = _unquote_yaml(val.strip())
        else:
            raise AssertionError(f"Unsupported YAML nesting in workflow_settings.yaml: {raw_line}")

    top_level["vars"] = vars_map
    return top_level


def _unquote_yaml(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def extract_config_block(sqlx_text, file_label):
    """Extract the config { ... } block while respecting strings and comments."""
    match = re.search(r"(?<![A-Za-z0-9_])config\s*\{", sqlx_text)
    if not match:
        raise AssertionError(f"{file_label}: missing config {{ ... }} block.")

    open_brace_idx = sqlx_text.index("{", match.start())
    depth = 0
    idx = open_brace_idx
    n = len(sqlx_text)
    in_quote = None
    in_line_comment = False
    in_block_comment = False

    while idx < n:
        ch = sqlx_text[idx]
        nxt = sqlx_text[idx + 1] if idx + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            idx += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                idx += 2
                continue
            idx += 1
            continue

        if in_quote:
            if ch == "\\" and idx + 1 < n:
                idx += 2
                continue
            if ch == in_quote:
                in_quote = None
            idx += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            idx += 2
            continue
        if ch == "-" and nxt == "-":
            in_line_comment = True
            idx += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            idx += 2
            continue
        if ch in ("'", '"', "`"):
            in_quote = ch
            idx += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return sqlx_text[open_brace_idx + 1 : idx]
        idx += 1

    raise AssertionError(f"{file_label}: unbalanced braces in config {{ ... }} block.")


def strip_comments(text):
    """Remove SQL and JS comments from text without altering quoted strings."""
    out = []
    idx = 0
    n = len(text)
    in_quote = None

    while idx < n:
        ch = text[idx]
        nxt = text[idx + 1] if idx + 1 < n else ""

        if in_quote:
            out.append(ch)
            if ch == "\\" and idx + 1 < n:
                out.append(nxt)
                idx += 2
                continue
            if ch == in_quote:
                in_quote = None
            idx += 1
            continue

        if ch == "/" and nxt == "/":
            idx += 2
            while idx < n and text[idx] != "\n":
                idx += 1
            continue
        if ch == "-" and nxt == "-":
            idx += 2
            while idx < n and text[idx] != "\n":
                idx += 1
            continue
        if ch == "/" and nxt == "*":
            idx += 2
            while idx + 1 < n and not (text[idx] == "*" and text[idx + 1] == "/"):
                idx += 1
            idx += 2
            continue
        if ch in ("'", '"', "`"):
            in_quote = ch
        out.append(ch)
        idx += 1

    return "".join(out)


def extract_markdown_prose_lines(markdown_text):
    """Extract prose lines from markdown, excluding frontmatter, code blocks, tables, and headings."""
    lines = markdown_text.splitlines()
    prose = []
    in_code = False
    idx = 0

    if lines and lines[0].strip() == "---":
        idx = 1
        while idx < len(lines) and lines[idx].strip() != "---":
            idx += 1
        idx += 1

    while idx < len(lines):
        line = lines[idx].strip()
        idx += 1
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith("#") or line.startswith("|") or line.startswith("> [!"):
            continue
        if line.startswith(">"):
            line = line.lstrip("> ").strip()
            if not line:
                continue
        if line.startswith("**") and line.endswith("**"):
            continue
        line = re.sub(r"^(?:[-*]|\d+\.)\s+", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
        prose.append(line)

    return prose


def run_node_script(script, label):
    """Execute a Node.js verification script inside REPO_ROOT and assert zero exit code."""
    node_bin = shutil.which("node")
    if node_bin is None:
        raise AssertionError("node CLI must be installed to execute JS helper tests.")
    proc = subprocess.run(
        [node_bin, "-e", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"{label} failed:\n{proc.stderr or proc.stdout}")
    return proc.stdout


class MedallionIntegrityTest(unittest.TestCase):
    """Validate Dataform config, SQLX medallion contracts, CI/CD, docs, and hygiene."""

    def test_required_repository_files_exist(self):
        for rel_path in REQUIRED_FILES:
            self.assertTrue(
                (REPO_ROOT / rel_path).is_file(),
                f"Missing required repository file: {rel_path}",
            )

    def test_root_configs_and_contract_vars(self):
        workflow_path = REPO_ROOT / "workflow_settings.yaml"
        package_path = REPO_ROOT / "package.json"

        workflow = parse_workflow_settings(workflow_path.read_text(encoding="utf-8"))
        for key in (
            "defaultProject",
            "defaultLocation",
            "defaultDataset",
            "defaultAssertionDataset",
            "dataformCoreVersion",
        ):
            self.assertIn(key, workflow, f"Missing {key} in workflow_settings.yaml.")
            self.assertTrue(workflow[key], f"Empty {key} in workflow_settings.yaml.")

        self.assertEqual(workflow["dataformCoreVersion"], "3.1.5")
        self.assertFalse(
            package_path.exists(),
            "package.json must not exist when dataformCoreVersion is defined in workflow_settings.yaml.",
        )

        vars_map = workflow["vars"]
        for var_name in REQUIRED_VARS:
            self.assertIn(var_name, vars_map, f"Missing contract var '{var_name}'.")
        self.assertEqual(vars_map["bronze_project"], "your-bronze-project-id")
        self.assertEqual(vars_map["bronze_dataset"], "bronze")
        self.assertEqual(vars_map["silver_dataset"], "silver")
        self.assertEqual(vars_map["gold_dataset"], "gold")
        self.assertEqual(vars_map["pii_policy_tag"], "")
        self.assertEqual(vars_map["pii_restricted_policy_tag"], "")
        self.assertEqual(vars_map["pii_masked_policy_tag"], "")
        self.assertEqual(vars_map["allow_untagged_pii"], "true")
        self.assertEqual(vars_map["filter_cdc_deletes"], "true")
        self.assertEqual(vars_map["cdc_lookback_days"], "30")
        self.assertEqual(vars_map["include_stream_orders"], "false")
        self.assertEqual(vars_map["include_batch_orders"], "false")

    def test_includes_helpers_present(self):
        node_bin = shutil.which("node")
        self.assertIsNotNone(node_bin, "node CLI must be installed to syntax-check includes/*.js.")

        expected_exports = {
            "includes/audit_columns.js": ("ingestedAtSql", "recordHashSql"),
            "includes/policy_tags.js": (
                "allowUntaggedPii",
                "piiRestrictedPolicyTag",
                "piiMaskedPolicyTag",
                "piiPolicyTag",
                "piiColumnConfig",
            ),
            "includes/scd_type2.js": (
                "scd2PreviousHashSql",
                "scd2WindowColumnsSql",
                "buildScd2Query",
            ),
            "includes/cdc_helpers.js": (
                "filterCdcDeletes",
                "activeCdcFilter",
                "parseLookbackDays",
                "lookbackDays",
                "deduplicateCdc",
            ),
        }
        for rel_path, symbols in expected_exports.items():
            full_path = REPO_ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"Missing helper file: {rel_path}")
            content = full_path.read_text(encoding="utf-8")
            for symbol in symbols:
                self.assertIn(symbol, content, f"{rel_path} must define {symbol}.")
            proc = subprocess.run(
                [node_bin, "--check", str(full_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                proc.returncode,
                0,
                f"node --check failed for {rel_path}: {proc.stderr or proc.stdout}",
            )

        for helper_path in (
            "includes/cdc_helpers.js",
            "includes/scd_type2.js",
            "includes/audit_columns.js",
        ):
            helper_text = (REPO_ROOT / helper_path).read_text(encoding="utf-8")
            self.assertIn("/^[A-Za-z_][A-Za-z0-9_]*$/", helper_text)

    def test_cdc_helpers_runtime_behavior(self):
        script = """
const assert = require("assert");
const cdc = require("./includes/cdc_helpers");

global.dataform = { projectConfig: { vars: {} } };
assert.strictEqual(cdc.filterCdcDeletes(), true);
assert.strictEqual(cdc.lookbackDays(), 30);
assert.strictEqual(cdc.activeCdcFilter(), "COALESCE(_metadata_deleted, FALSE) = FALSE");
assert.strictEqual(cdc.activeCdcFilter(""), "COALESCE(_metadata_deleted, FALSE) = FALSE");
assert.strictEqual(cdc.activeCdcFilter("src"), "COALESCE(src._metadata_deleted, FALSE) = FALSE");

global.dataform = { projectConfig: { vars: { filter_cdc_deletes: "true", cdc_lookback_days: "14" } } };
assert.strictEqual(cdc.filterCdcDeletes(), true);
assert.strictEqual(cdc.lookbackDays(), 14);
assert.strictEqual(cdc.activeCdcFilter("orders"), "COALESCE(orders._metadata_deleted, FALSE) = FALSE");

assert.strictEqual(cdc.parseLookbackDays("1"), 1);
assert.strictEqual(cdc.parseLookbackDays("30"), 30);
assert.strictEqual(cdc.parseLookbackDays("3650"), 3650);
assert.strictEqual(cdc.parseLookbackDays(7), 7);

for (const badDays of ["0", "-1", "3651", "9999", "07", "30; DROP TABLE x", "30 DAY", "", null, undefined, {}, []]) {
  assert.throws(() => cdc.parseLookbackDays(badDays), /cdc_lookback_days/);
}
global.dataform = { projectConfig: { vars: { cdc_lookback_days: "30 OR 1=1" } } };
assert.throws(() => cdc.lookbackDays(), /cdc_lookback_days/);

for (const badAlias of ["src; DROP TABLE x", "1bad", "a.b", " ", "src--comment"]) {
  assert.throws(() => cdc.activeCdcFilter(badAlias), /Invalid SQL table alias/);
}
assert.throws(() => cdc.activeCdcFilter(123), /must be a string/);

global.dataform = { projectConfig: { vars: { filter_cdc_deletes: "true" } } };
const dedupSql = cdc.deduplicateCdc(["order_id"], ["_ingested_at", "_cdc_sequence_num"]);
assert(dedupSql.includes("PARTITION BY order_id"));
assert(dedupSql.includes("ORDER BY _ingested_at DESC, _cdc_sequence_num DESC, COALESCE(_metadata_deleted, FALSE) DESC"));
assert.throws(() => cdc.deduplicateCdc(["order_id; DROP TABLE x"]), /Invalid SQL keyColumn/);
assert.throws(() => cdc.deduplicateCdc(["order_id"], ["_ingested_at DESC; --"]), /Invalid SQL orderColumn/);

for (const offValue of ["false", "FALSE", false]) {
  global.dataform = { projectConfig: { vars: { filter_cdc_deletes: offValue } } };
  assert.strictEqual(cdc.filterCdcDeletes(), false);
  assert.strictEqual(cdc.activeCdcFilter(), "TRUE");
  assert.strictEqual(cdc.activeCdcFilter("src"), "TRUE");
  const dedupNoDelete = cdc.deduplicateCdc("order_id");
  assert.strictEqual(dedupNoDelete.includes("_metadata_deleted"), false);
  assert.throws(() => cdc.activeCdcFilter("src; DROP TABLE x"), /Invalid SQL table alias/);
}
"""
        run_node_script(script, "cdc_helpers runtime check")

    def test_policy_tags_runtime_behavior(self):
        script = """
const assert = require("assert");
const policyTags = require("./includes/policy_tags");

const restrictedTag = "projects/example-gov/locations/asia-southeast1/taxonomies/1001/policyTags/2002";
const maskedTag = "projects/example-gov/locations/asia-southeast1/taxonomies/1001/policyTags/2001";
const legacyTag = "projects/example-gov/locations/asia-southeast1/taxonomies/1001/policyTags/2000";

assert.deepStrictEqual(
  policyTags.piiRestrictedPolicyTag({
    pii_restricted_policy_tag: restrictedTag,
    pii_masked_policy_tag: maskedTag,
    allow_untagged_pii: "false"
  }),
  [restrictedTag]
);
assert.deepStrictEqual(
  policyTags.piiMaskedPolicyTag({
    pii_restricted_policy_tag: restrictedTag,
    pii_masked_policy_tag: maskedTag,
    allow_untagged_pii: "false"
  }),
  [maskedTag]
);
assert.deepStrictEqual(
  policyTags.piiPolicyTag({
    pii_masked_policy_tag: maskedTag,
    allow_untagged_pii: "false"
  }),
  [maskedTag]
);

// Fallback to legacy pii_policy_tag when tier-specific variables are unset.
assert.deepStrictEqual(
  policyTags.piiRestrictedPolicyTag({ pii_policy_tag: legacyTag, allow_untagged_pii: "false" }),
  [legacyTag]
);
assert.deepStrictEqual(
  policyTags.piiMaskedPolicyTag({ pii_policy_tag: legacyTag, allow_untagged_pii: "false" }),
  [legacyTag]
);

// Empty allowed when allow_untagged_pii is true.
assert.deepStrictEqual(
  policyTags.piiRestrictedPolicyTag({ pii_restricted_policy_tag: "", allow_untagged_pii: "true" }),
  []
);
assert.deepStrictEqual(
  policyTags.piiMaskedPolicyTag({ pii_masked_policy_tag: "", allow_untagged_pii: "true" }),
  []
);

// Must throw when empty and allow_untagged_pii is false.
assert.throws(
  () => policyTags.piiRestrictedPolicyTag({ pii_restricted_policy_tag: "", pii_policy_tag: "", allow_untagged_pii: "false" }),
  /pii_policy_tag is required/
);
assert.throws(
  () => policyTags.piiMaskedPolicyTag({ pii_masked_policy_tag: "", pii_policy_tag: "", allow_untagged_pii: "false" }),
  /pii_policy_tag is required/
);

// Reject invalid or injected policyTag resource paths even when allow_untagged_pii is true.
for (const badTag of [
  "invalid-tag",
  "projects/bad_proj/locations/us/taxonomies/1/policyTags/2",
  "projects/example-gov/locations/asia-southeast1/taxonomies/abc/policyTags/1",
  restrictedTag + "'; DROP TABLE x; --"
]) {
  assert.throws(
    () => policyTags.piiRestrictedPolicyTag({ pii_restricted_policy_tag: badTag, allow_untagged_pii: "true" }),
    /Invalid pii_restricted_policy_tag/
  );
  assert.throws(
    () => policyTags.piiMaskedPolicyTag({ pii_masked_policy_tag: badTag, allow_untagged_pii: "true" }),
    /Invalid pii_masked_policy_tag/
  );
}

// Globals fallback for Dataform config blocks.
global.dataform = {
  projectConfig: {
    vars: {
      pii_restricted_policy_tag: restrictedTag,
      pii_masked_policy_tag: maskedTag,
      allow_untagged_pii: "false"
    }
  }
};
assert.deepStrictEqual(policyTags.piiRestrictedPolicyTag(), [restrictedTag]);
assert.deepStrictEqual(policyTags.piiMaskedPolicyTag(), [maskedTag]);
assert.deepStrictEqual(policyTags.piiColumnConfig("Customer ID", "restricted"), {
  description: "Customer ID",
  bigqueryPolicyTags: [restrictedTag]
});
"""
        run_node_script(script, "policy_tags runtime check")

    def test_scd_type2_and_audit_columns_runtime_behavior(self):
        script = """
const assert = require("assert");
const scd2 = require("./includes/scd_type2");
const audit = require("./includes/audit_columns");

assert.strictEqual(audit.ingestedAtSql(), "CURRENT_TIMESTAMP()");
assert.strictEqual(
  audit.recordHashSql(["customer_id", "customer_ic_number"]),
  "TO_HEX(SHA256(TO_JSON_STRING(STRUCT(customer_id, customer_ic_number))))"
);
assert.throws(() => audit.recordHashSql([]), /non-empty column list/);
assert.throws(() => audit.recordHashSql(["customer_id; DROP TABLE x"]), /Invalid SQL identifier/);

const lagExpr = scd2.scd2PreviousHashSql("customer_id", ["_ingested_at", "_cdc_sequence_num"], "record_hash");
assert.strictEqual(
  lagExpr,
  "LAG(record_hash) OVER (PARTITION BY customer_id ORDER BY _ingested_at ASC, _cdc_sequence_num ASC)"
);
assert.throws(
  () => scd2.scd2PreviousHashSql("customer_id; --", ["_ingested_at"]),
  /Invalid SQL identifier/
);
assert.throws(
  () => scd2.scd2PreviousHashSql("customer_id", ["_ingested_at; --"]),
  /Invalid SQL identifier/
);

const winCols = scd2.scd2WindowColumnsSql(
  "customer_id",
  ["_ingested_at", "_cdc_sequence_num"],
  "TIMESTAMP('9999-12-31 23:59:59 UTC')"
);
assert(winCols.includes("_ingested_at AS valid_from"));
assert(winCols.includes("LEAD(_ingested_at) OVER (PARTITION BY customer_id ORDER BY _ingested_at ASC, _cdc_sequence_num ASC)"));
assert(winCols.includes("AS valid_to"));
assert(winCols.includes("AS is_current"));

const query = scd2.buildScd2Query({
  sourceSql: "changed_snapshots",
  naturalKey: "customer_id",
  orderByColumn: ["_ingested_at", "_cdc_sequence_num"],
  columns: ["customer_id", "customer_ic_number", "_ingested_at"],
  excludeDeletedColumn: "_metadata_deleted"
});
assert(query.includes("FROM changed_snapshots"));
assert(query.includes("WHERE COALESCE(_metadata_deleted, FALSE) = FALSE"));
assert.throws(() => scd2.buildScd2Query({ sourceSql: "x; DROP TABLE y", naturalKey: "id", orderByColumn: "ts", columns: ["id"] }), /valid CTE/);
"""
        run_node_script(script, "scd_type2 and audit_columns runtime check")

    def test_sqlx_template_evaluation_with_node(self):
        script = r"""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const audit_columns = require("./includes/audit_columns");
const cdc_helpers = require("./includes/cdc_helpers");
const policy_tags = require("./includes/policy_tags");
const scd_type2 = require("./includes/scd_type2");

function splitSqlx(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  const cfgStart = raw.indexOf("config {");
  let depth = 0;
  let cfgEnd = -1;
  for (let i = raw.indexOf("{", cfgStart); i < raw.length; i++) {
    if (raw[i] === "{") depth++;
    else if (raw[i] === "}") {
      depth--;
      if (depth === 0) { cfgEnd = i + 1; break; }
    }
  }
  const cfgExpr = "(" + raw.slice(raw.indexOf("{", cfgStart), cfgEnd) + ")";
  let body = raw.slice(cfgEnd).trim();
  let jsSetup = "";
  if (body.startsWith("js {")) {
    let jdepth = 0;
    let jEnd = -1;
    for (let i = body.indexOf("{"); i < body.length; i++) {
      if (body[i] === "{") jdepth++;
      else if (body[i] === "}") {
        jdepth--;
        if (jdepth === 0) { jEnd = i + 1; break; }
      }
    }
    jsSetup = body.slice(body.indexOf("{") + 1, jEnd - 1);
    body = body.slice(jEnd).trim();
  }
  return { cfgExpr, jsSetup, body };
}

function evalSqlx(filePath, vars, isIncremental) {
  global.dataform = { projectConfig: { vars } };
  const { cfgExpr, jsSetup, body } = splitSqlx(filePath);
  const ctx = vm.createContext({
    dataform: global.dataform,
    audit_columns,
    cdc_helpers,
    policy_tags,
    scd_type2,
    ref: (name) => "`proj.ds." + name + "`",
    self: () => "`proj.ds.self`",
    when: (cond, a, b = "") => (cond ? a : b),
    incremental: () => isIncremental
  });
  const cfg = vm.runInContext(cfgExpr, ctx);
  if (jsSetup) {
    vm.runInContext(jsSetup, ctx);
  }
  const escaped = body.replace(/\\/g, "\\\\").replace(/`/g, "\\`");
  const sql = vm.runInContext("`" + escaped + "`", ctx);
  return { cfg, sql };
}

const restrictedTag = "projects/p/locations/asia-southeast1/taxonomies/1/policyTags/2";
const maskedTag = "projects/p/locations/asia-southeast1/taxonomies/1/policyTags/3";

// 1. Default CDC-only fct_orders (include_stream_orders=false, include_batch_orders=false)
const fctDefault = evalSqlx("definitions/02_silver/fct_orders.sqlx", {
  silver_project: "p",
  silver_dataset: "silver",
  pii_restricted_policy_tag: restrictedTag,
  pii_masked_policy_tag: maskedTag,
  allow_untagged_pii: "false",
  filter_cdc_deletes: "true",
  cdc_lookback_days: "30",
  include_stream_orders: "false",
  include_batch_orders: "false"
}, true);
assert.strictEqual(fctDefault.cfg.bigquery.updatePartitionFilter, "order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)");
assert(fctDefault.sql.includes("WHERE DATE(order_date) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)"));
assert(!fctDefault.sql.includes("pos_orders_stream_cdc"));
assert(!fctDefault.sql.includes("pos_orders_batch_cdc"));
assert.deepStrictEqual(Array.from(fctDefault.cfg.columns.customer_ic_number.bigqueryPolicyTags), [restrictedTag]);
assert.deepStrictEqual(Array.from(fctDefault.cfg.columns.customer_email.bigqueryPolicyTags), [maskedTag]);

// 2. Unified CDC + Stream + Batch fct_orders with 14-day lookback
const fctUnified = evalSqlx("definitions/02_silver/fct_orders.sqlx", {
  silver_project: "p",
  silver_dataset: "silver",
  pii_restricted_policy_tag: restrictedTag,
  pii_masked_policy_tag: maskedTag,
  allow_untagged_pii: "false",
  filter_cdc_deletes: "true",
  cdc_lookback_days: "14",
  include_stream_orders: "true",
  include_batch_orders: "true"
}, true);
assert.strictEqual(fctUnified.cfg.bigquery.updatePartitionFilter, "order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)");
const matches = fctUnified.sql.match(/WHERE DATE\(order_date\) >= DATE_SUB\(CURRENT_DATE\(\), INTERVAL 14 DAY\)/g) || [];
assert.strictEqual(matches.length, 3);
assert(fctUnified.sql.includes("pos_orders_stream_cdc"));
assert(fctUnified.sql.includes("pos_orders_batch_cdc"));
const batchIdx = fctUnified.sql.indexOf("pos_orders_batch_cdc");
const qualifyIdx = fctUnified.sql.indexOf("QUALIFY ROW_NUMBER()");
assert(batchIdx > -1 && qualifyIdx > -1 && batchIdx < qualifyIdx);

// 3. Invalid lookback days must fail compilation
assert.throws(() => evalSqlx("definitions/02_silver/fct_orders.sqlx", {
  cdc_lookback_days: "7; DROP TABLE x",
  allow_untagged_pii: "true"
}, true), /cdc_lookback_days/);

// 4. dim_customers SCD2 change-only hash deduplication + IC tracking + dual PII tags
const dimRes = evalSqlx("definitions/02_silver/dim_customers.sqlx", {
  silver_project: "p",
  silver_dataset: "silver",
  pii_restricted_policy_tag: restrictedTag,
  pii_masked_policy_tag: maskedTag,
  allow_untagged_pii: "false",
  filter_cdc_deletes: "true"
}, false);
assert.deepStrictEqual(Array.from(dimRes.cfg.columns.customer_ic_number.bigqueryPolicyTags), [restrictedTag]);
assert.deepStrictEqual(Array.from(dimRes.cfg.columns.customer_email.bigqueryPolicyTags), [maskedTag]);
assert.deepStrictEqual(Array.from(dimRes.cfg.columns.customer_name.bigqueryPolicyTags), [maskedTag]);
assert(dimRes.sql.includes("STRUCT(customer_id, customer_name, customer_email, customer_ic_number, segment, country_code, _metadata_deleted)"));
assert(dimRes.sql.includes("LAG(record_hash) OVER (PARTITION BY customer_id ORDER BY _ingested_at ASC, _cdc_sequence_num ASC)"));
const filterIdx = dimRes.sql.indexOf("prev_record_hash != record_hash");
const leadIdx = dimRes.sql.indexOf("LEAD(_ingested_at)");
assert(filterIdx > -1 && leadIdx > -1 && filterIdx < leadIdx);

// 5. Gold marts and Silver assertion
const revRes = evalSqlx("definitions/03_gold/finance/mart_daily_revenue.sqlx", {
  gold_project: "p",
  gold_dataset: "gold",
  cdc_lookback_days: "14"
}, true);
assert.strictEqual(revRes.cfg.type, "incremental");
assert.deepStrictEqual(Array.from(revRes.cfg.uniqueKey), ["order_date", "currency_code"]);
assert.strictEqual(revRes.cfg.bigquery.updatePartitionFilter, "order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)");
assert(revRes.sql.includes("order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)"));

const storeRes = evalSqlx("definitions/03_gold/retail/mart_store_performance.sqlx", {
  gold_project: "p",
  gold_dataset: "gold",
  gold_retail_project: "",
  gold_retail_dataset: "",
  cdc_lookback_days: "14"
}, true);
assert.strictEqual(storeRes.cfg.type, "incremental");
assert.deepStrictEqual(Array.from(storeRes.cfg.uniqueKey), ["order_date", "store_id", "currency_code"]);
assert.strictEqual(storeRes.cfg.bigquery.updatePartitionFilter, "order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)");
assert(storeRes.sql.includes("order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)"));

const assertRes = evalSqlx("definitions/02_silver/assert_fct_orders_quality.sqlx", {
  silver_project: "p",
  cdc_lookback_days: "14"
}, false);
assert(assertRes.sql.includes("WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY)"));
"""
        run_node_script(script, "SQLX template evaluation check")

    def test_sqlx_definitions_and_layer_contracts(self):
        definitions_dir = REPO_ROOT / "definitions"
        sqlx_files = sorted(definitions_dir.rglob("*.sqlx"))
        self.assertEqual(
            len(sqlx_files),
            9,
            "Expected 4 Bronze, 2 Silver tables, 1 Silver assertion, and 2 Gold SQLX files.",
        )

        for sqlx_path in sqlx_files:
            rel = sqlx_path.relative_to(REPO_ROOT).as_posix()
            raw_text = sqlx_path.read_text(encoding="utf-8")
            config_body = extract_config_block(raw_text, rel)
            clean_sql = strip_comments(raw_text)

            self.assertIsNone(
                re.search(r"\bSELECT\s+\*", clean_sql, re.IGNORECASE),
                f"{rel}: wildcard 'SELECT *' is forbidden.",
            )

            type_match = re.search(r'\btype\s*:\s*["\']([a-zA-Z_]+)["\']', config_body)
            self.assertIsNotNone(type_match, f"{rel}: config block must declare a model type.")
            model_type = type_match.group(1)

            if rel.startswith("definitions/01_bronze/"):
                self.assertEqual(
                    model_type,
                    "declaration",
                    f"{rel}: Bronze definitions must only use type 'declaration'.",
                )
            elif rel.startswith("definitions/02_silver/"):
                if model_type in ("table", "incremental"):
                    requires_partition_filter = bool(
                        re.search(r"\brequirePartitionFilter\s*:\s*true\b", config_body)
                    )
                    if requires_partition_filter:
                        self.assertNotRegex(
                            config_body,
                            r"\bassertions\s*:\s*\{",
                            f"{rel}: tables with requirePartitionFilter must not use inline assertions.",
                        )
                        part_match = re.search(
                            r'\bpartitionBy\s*:\s*["\']([A-Za-z0-9_]+)["\']',
                            config_body,
                        )
                        self.assertIsNotNone(part_match, f"{rel}: missing partitionBy column.")
                        part_col = part_match.group(1)
                        table_name = sqlx_path.stem
                        custom_assertions = sorted(
                            (REPO_ROOT / "definitions/02_silver").glob(f"assert_{table_name}_*.sqlx")
                        )
                        self.assertGreaterEqual(
                            len(custom_assertions),
                            1,
                            f"{rel}: missing standalone assert_{table_name}_*.sqlx assertion.",
                        )
                        for assertion_path in custom_assertions:
                            a_rel = assertion_path.relative_to(REPO_ROOT).as_posix()
                            a_text = assertion_path.read_text(encoding="utf-8")
                            a_cfg = extract_config_block(a_text, a_rel)
                            self.assertRegex(
                                a_cfg,
                                r'\btype\s*:\s*["\']assertion["\']',
                                f"{a_rel}: must use type 'assertion'.",
                            )
                            self.assertIn(f'${{ref("{table_name}")}}', a_text)
                            self.assertRegex(
                                strip_comments(a_text),
                                rf"\bWHERE\b[\s\S]*\b{re.escape(part_col)}\b",
                                f"{a_rel}: must filter on partition column '{part_col}'.",
                            )
                    else:
                        self.assertRegex(
                            config_body,
                            r"\bassertions\s*:\s*\{",
                            f"{rel}: Silver tables without requirePartitionFilter must define assertions.",
                        )
            elif rel.startswith("definitions/03_gold/"):
                self.assertEqual(
                    model_type,
                    "incremental",
                    f"{rel}: Gold marts must use type 'incremental' for partition-pruned merges.",
                )
                self.assertRegex(
                    config_body,
                    r"\bassertions\s*:\s*\{",
                    f"{rel}: Gold marts must define assertions.",
                )
                self.assertRegex(
                    config_body,
                    r"\bupdatePartitionFilter\s*:",
                    f"{rel}: Gold marts must define updatePartitionFilter.",
                )

            if rel.startswith("definitions/03_gold/") and '${ref("fct_orders")}' in raw_text:
                self.assertRegex(
                    clean_sql,
                    r"\bWHERE\b[\s\S]*\border_date\b",
                    f"{rel}: queries over fct_orders must filter on order_date.",
                )

        pos_orders_bronze = (REPO_ROOT / "definitions/01_bronze/pos_orders_cdc.sqlx").read_text(
            encoding="utf-8"
        )
        self.assertIn("_metadata_deleted", pos_orders_bronze)
        self.assertIn("_cdc_sequence_num", pos_orders_bronze)

        pos_stream_bronze = (
            REPO_ROOT / "definitions/01_bronze/pos_orders_stream_cdc.sqlx"
        ).read_text(encoding="utf-8")
        self.assertIn("subscription_name", pos_stream_bronze)
        self.assertIn("publish_time", pos_stream_bronze)

        pos_batch_bronze = (
            REPO_ROOT / "definitions/01_bronze/pos_orders_batch_cdc.sqlx"
        ).read_text(encoding="utf-8")
        self.assertIn("_metadata_deleted", pos_batch_bronze)
        self.assertIn("_cdc_sequence_num", pos_batch_bronze)

        crm_customers_bronze = (
            REPO_ROOT / "definitions/01_bronze/crm_customers_cdc.sqlx"
        ).read_text(encoding="utf-8")
        self.assertIn("_metadata_deleted", crm_customers_bronze)
        self.assertIn("customer_email", crm_customers_bronze)

        fct_orders = (REPO_ROOT / "definitions/02_silver/fct_orders.sqlx").read_text(encoding="utf-8")
        self.assertIn("store_id", fct_orders)
        self.assertIn("policy_tags.piiRestrictedPolicyTag", fct_orders)
        self.assertIn("policy_tags.piiMaskedPolicyTag", fct_orders)
        self.assertIn("cdc_helpers.activeCdcFilter(", fct_orders)
        self.assertIn("cdc_helpers.filterCdcDeletes()", fct_orders)
        self.assertIn("cdc_helpers.lookbackDays()", fct_orders)
        self.assertIn("cdc_helpers.deduplicateCdc(", fct_orders)
        self.assertIn("include_stream_orders", fct_orders)
        self.assertIn("include_batch_orders", fct_orders)

        dim_customers = (REPO_ROOT / "definitions/02_silver/dim_customers.sqlx").read_text(
            encoding="utf-8"
        )
        self.assertIn("scd_type2.scd2PreviousHashSql", dim_customers)
        self.assertIn("scd_type2.scd2WindowColumnsSql", dim_customers)
        self.assertIn("cdc_helpers.activeCdcFilter(", dim_customers)
        self.assertIn("cdc_helpers.filterCdcDeletes()", dim_customers)
        self.assertIn("policy_tags.piiRestrictedPolicyTag()", dim_customers)
        self.assertIn("policy_tags.piiMaskedPolicyTag()", dim_customers)
        self.assertIn('"customer_ic_number"', dim_customers)

        assert_orders = (
            REPO_ROOT / "definitions/02_silver/assert_fct_orders_quality.sqlx"
        ).read_text(encoding="utf-8")
        self.assertIn("cdc_helpers.lookbackDays()", assert_orders)
        self.assertNotIn("DATE('1970-01-01')", assert_orders)

        for silver_model in ("fct_orders.sqlx", "dim_customers.sqlx"):
            silver_text = (REPO_ROOT / "definitions/02_silver" / silver_model).read_text(
                encoding="utf-8"
            )
            for line_no, line in enumerate(silver_text.splitlines(), start=1):
                if "_metadata_deleted" in line:
                    self.assertIn(
                        "cdc_helpers.filterCdcDeletes()",
                        line,
                        f"{silver_model}:{line_no}: _metadata_deleted reference must be gated by cdc_helpers.filterCdcDeletes().",
                    )

        retail_mart = (
            REPO_ROOT / "definitions/03_gold/retail/mart_store_performance.sqlx"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "dataform.projectConfig.vars.gold_retail_project || dataform.projectConfig.vars.gold_project",
            retail_mart,
        )
        self.assertIn(
            "dataform.projectConfig.vars.gold_retail_dataset || dataform.projectConfig.vars.gold_dataset",
            retail_mart,
        )

    def test_env_compilation_examples_valid(self):
        tag_pattern = re.compile(
            r"^projects/[a-z0-9-]+/locations/[a-z0-9-]+/taxonomies/[0-9]+/policyTags/[0-9]+$"
        )
        for env_name in ("dev", "staging", "prod"):
            env_path = REPO_ROOT / "envs" / f"{env_name}.compilation.json.example"
            data = json.loads(env_path.read_text(encoding="utf-8"))
            self.assertIn("defaultDatabase", data)
            self.assertIn("defaultSchema", data)
            self.assertIn("defaultLocation", data)
            self.assertIn("vars", data)
            env_vars = data["vars"]
            for var_name in REQUIRED_VARS:
                self.assertIn(var_name, env_vars, f"{env_path.name}: missing var {var_name}")
            if env_name in ("staging", "prod"):
                self.assertEqual(env_vars["allow_untagged_pii"], "false")
                self.assertRegex(env_vars["pii_restricted_policy_tag"], tag_pattern)
                self.assertRegex(env_vars["pii_masked_policy_tag"], tag_pattern)

    def test_quality_rules_and_governance_files(self):
        quality_text = (REPO_ROOT / "quality/silver_orders_quality.yaml").read_text(encoding="utf-8")
        self.assertRegex(quality_text, r"(?m)^rules:\s*$", "Missing top-level rules key in quality YAML.")
        for expected in (
            "nonNullExpectation",
            "order_id",
            "order_date",
            "rangeExpectation",
            "net_amount",
            'minValue: "0"',
            "strictMinEnabled: false",
        ):
            self.assertIn(expected, quality_text)

        codeowners = (REPO_ROOT / "CODEOWNERS").read_text(encoding="utf-8")
        self.assertIn("/definitions/03_gold/finance/", codeowners)
        self.assertIn("/definitions/03_gold/retail/", codeowners)

        ci_text = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertRegex(ci_text, r"(?m)^permissions:\s*\n\s+contents:\s*read\b")
        self.assertRegex(ci_text, r"actions/checkout@[0-9a-f]{40}")
        self.assertRegex(ci_text, r"actions/setup-python@[0-9a-f]{40}")
        self.assertIn("python3 -m unittest discover -s tests -v", ci_text)
        self.assertIn("workflow_settings.yaml", ci_text)
        self.assertIn('not Path("package.json").exists()', ci_text)
        self.assertIn("allow_untagged_pii", ci_text)

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://github.com/choo737/gcp-foundation", readme)
        self.assertIn("https://github.com/choo737/gcp-data-ingestion", readme)
        self.assertIn("https://github.com/choo737/gcp-data-medallion", readme)
        self.assertIn("3-Repository Accelerator Suite", readme)
        self.assertIn("workflow_settings.yaml", readme)
        self.assertIn("3.1.5", readme)
        self.assertIn("> [!NOTE]", readme)
        self.assertIn("google_bigquery_reservation", readme)
        self.assertIn("modules/data/bigquery-reservations/", readme)
        self.assertIn("Who Creates Bronze Tables", readme)
        self.assertIn("Why Dataform Over dbt", readme)
        self.assertIn("filter_cdc_deletes", readme)
        self.assertIn("includes/cdc_helpers.js", readme)
        self.assertIn("dataform-dryrun.yml", readme)
        self.assertIn("dataform-promote.yml", readme)
        self.assertIn("GCP_WIF_PROVIDER", readme)
        self.assertIn("GCP_WIF_SERVICE_ACCOUNT", readme)
        self.assertIn("DATAFORM_REPO_PATH", readme)
        self.assertNotIn("25 data engineers", readme)
        for var_name in REQUIRED_VARS:
            self.assertIn(var_name, readme)

        split_skill = (REPO_ROOT / ".agents/skills/split-domain-mesh/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("25 data engineers", split_skill)

    def test_onboarding_docs_skills_and_gitignore(self):
        gitignore_lines = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        }
        for ignored_entry in (
            "platform-context.json",
            "envs/*.compilation.json",
            ".cm_project",
            ".codemender/",
        ):
            self.assertIn(ignored_entry, gitignore_lines)

        git_bin = shutil.which("git")
        if git_bin is not None:
            for should_ignore in (
                "platform-context.json",
                "envs/dev.compilation.json",
                "envs/staging.compilation.json",
                "envs/prod.compilation.json",
            ):
                proc = subprocess.run(
                    [git_bin, "check-ignore", "-q", should_ignore],
                    cwd=REPO_ROOT,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, f"{should_ignore} must be gitignored.")

            for must_stay_tracked in (
                "envs/dev.compilation.json.example",
                "envs/staging.compilation.json.example",
                "envs/prod.compilation.json.example",
            ):
                proc = subprocess.run(
                    [git_bin, "check-ignore", "-q", must_stay_tracked],
                    cwd=REPO_ROOT,
                    check=False,
                )
                self.assertNotEqual(
                    proc.returncode,
                    0,
                    f"{must_stay_tracked} must not be gitignored.",
                )

        questionnaire = (REPO_ROOT / "QUESTIONNAIRE.md").read_text(encoding="utf-8")
        for expected in (
            "https://github.com/choo737/gcp-launchpad",
            "platform-context.json",
            "Greenfield Suite",
            "Brownfield Standalone BigQuery",
            "definitions/01_bronze/*.sqlx",
            "workflow_settings.yaml",
            "envs/{dev,staging,prod}.compilation.json",
            "quality/silver_orders_quality.yaml",
            "filter_cdc_deletes",
            "include_stream_orders",
            "include_batch_orders",
            "sandbox_poc",
            "enterprise_standard",
            "regulated_fsi_rmit",
            "allow_untagged_pii",
            "pii_restricted_policy_tag",
            "pii_masked_policy_tag",
            "pii_policy_tag",
            "cdc_lookback_days",
            "gold_project",
            "gold_retail_project",
            ".agents/skills/split-domain-mesh/SKILL.md",
            "GCP_WIF_PROVIDER",
            "GCP_WIF_SERVICE_ACCOUNT",
            "DATAFORM_REPO_PATH",
            "dataform-dryrun.yml",
            "dataform-promote.yml",
        ):
            self.assertIn(expected, questionnaire)

        setup_skill = (
            REPO_ROOT / ".agents/skills/setup-data-medallion/SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertRegex(setup_skill, r"(?ms)^---\nname:\s*setup-data-medallion\n.*?^---")
        for expected in (
            "choo737/gcp-launchpad",
            "platform-context.json",
            "QUESTIONNAIRE.md",
            "workflow_settings.yaml",
            "3.1.5",
            "package.json",
            "envs/{dev,staging,prod}.compilation.json",
            "envs/dev.compilation.json.example",
            "include_stream_orders",
            "include_batch_orders",
            "allow_untagged_pii",
            "cdc_lookback_days",
            "GCP_WIF_PROVIDER",
            "GCP_WIF_SERVICE_ACCOUNT",
            "DATAFORM_REPO_PATH",
            "gh repo create",
            "--private",
            "make test",
        ):
            self.assertIn(expected, setup_skill)

        for doc_name in ("README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md"):
            doc_text = (REPO_ROOT / doc_name).read_text(encoding="utf-8")
            self.assertIn("QUESTIONNAIRE.md", doc_text, f"{doc_name} must reference QUESTIONNAIRE.md.")
            self.assertIn(
                ".agents/skills/setup-data-medallion/SKILL.md",
                doc_text,
                f"{doc_name} must register setup-data-medallion.",
            )
            self.assertIn(
                "https://github.com/choo737/gcp-launchpad",
                doc_text,
                f"{doc_name} must reference gcp-launchpad.",
            )
            self.assertIn(
                "platform-context.json",
                doc_text,
                f"{doc_name} must document platform-context.json.",
            )

        agents_text = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(".agents/skills/add-medallion-model/SKILL.md", agents_text)
        self.assertIn(".agents/skills/split-domain-mesh/SKILL.md", agents_text)

        claude_body = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").split("\n", 1)[1]
        gemini_body = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8").split("\n", 1)[1]
        self.assertEqual(claude_body, gemini_body, "CLAUDE.md and GEMINI.md must stay aligned.")

    def test_dataform_workflows_security_and_contract(self):
        workflow_files = sorted((REPO_ROOT / ".github/workflows").glob("*.yml"))
        for wf_path in workflow_files:
            wf_text = wf_path.read_text(encoding="utf-8")
            uses_refs = re.findall(r"uses:\s*([^\s#]+)", wf_text)
            self.assertGreaterEqual(len(uses_refs), 1, f"{wf_path.name}: expected pinned actions.")
            for ref in uses_refs:
                self.assertRegex(
                    ref,
                    r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$",
                    f"{wf_path.name}: action '{ref}' must be pinned to a 40-char commit SHA.",
                )

            in_run_block = False
            run_indent = 0
            for line_no, raw_line in enumerate(wf_text.splitlines(), start=1):
                stripped = raw_line.strip()
                indent = len(raw_line) - len(raw_line.lstrip(" "))
                if in_run_block:
                    if stripped and indent <= run_indent:
                        in_run_block = False
                    else:
                        self.assertNotIn(
                            "${{",
                            raw_line,
                            f"{wf_path.name}:{line_no}: GitHub Actions expression interpolation inside run block is forbidden.",
                        )
                        continue
                if re.match(r"^(?:-\s*)?run\s*:\s*\|", stripped):
                    in_run_block = True
                    run_indent = indent
                elif re.match(r"^(?:-\s*)?run\s*:", stripped):
                    self.assertNotIn(
                        "${{",
                        raw_line,
                        f"{wf_path.name}:{line_no}: GitHub Actions expression interpolation inside run line is forbidden.",
                    )

        dryrun = (REPO_ROOT / ".github/workflows/dataform-dryrun.yml").read_text(encoding="utf-8")
        self.assertRegex(dryrun, r"(?m)^\s*workflow_dispatch:\s*$")
        self.assertRegex(dryrun, r"(?m)^\s*pull_request:\s*$")
        self.assertRegex(dryrun, r"(?m)^permissions:\s*\n\s+contents:\s*read\s*\n\s+id-token:\s*write\b")
        self.assertIn("python3 -m unittest discover -s tests -v", dryrun)
        self.assertIn(
            "vars.GCP_WIF_PROVIDER != '' && vars.GCP_WIF_SERVICE_ACCOUNT != '' && vars.DATAFORM_REPO_PATH != ''",
            dryrun,
        )
        self.assertIn("https://dataform.googleapis.com/v1/", dryrun)
        self.assertNotIn("v1beta1", dryrun)
        self.assertIn("codeCompilationConfig", dryrun)
        self.assertIn("PII_MASKED_POLICY_TAG", dryrun)
        self.assertIn("PII_RESTRICTED_POLICY_TAG", dryrun)
        self.assertIn('"allow_untagged_pii"] = "false"', dryrun)
        self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262", dryrun)
        self.assertIn("google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093", dryrun)
        self.assertIn("workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}", dryrun)
        self.assertIn("service_account: ${{ vars.GCP_WIF_SERVICE_ACCOUNT }}", dryrun)
        self.assertIn("token_format: access_token", dryrun)
        self.assertIn("urllib.request", dryrun)
        self.assertIn("GITHUB_HEAD_REF", dryrun)
        self.assertIn("compilationResults", dryrun)
        self.assertIn("compilationErrors", dryrun)
        self.assertNotRegex(dryrun, r"\bcurl\b")

        promote = (REPO_ROOT / ".github/workflows/dataform-promote.yml").read_text(encoding="utf-8")
        self.assertRegex(promote, r"(?m)^permissions:\s*\n\s+contents:\s*read\s*\n\s+id-token:\s*write\b")
        self.assertIn("environment: dev", promote)
        self.assertIn("environment: staging", promote)
        self.assertIn("environment: prod", promote)
        self.assertIn("dev-main", promote)
        self.assertIn("staging-main", promote)
        self.assertIn("prod-main", promote)
        self.assertIn("prod-release", promote)
        self.assertIn("https://dataform.googleapis.com/v1/", promote)
        self.assertNotIn("v1beta1", promote)
        self.assertIn("releaseCompilationResult", promote)
        self.assertIn('"allow_untagged_pii": "false"', promote)
        self.assertIn("refs/tags/v", promote)
        self.assertNotRegex(promote, r"\bcurl\b")

    def test_markdown_prose_sentence_length(self):
        actual_md_files = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in iter_repo_files()
            if path.suffix == ".md"
        }
        self.assertEqual(
            set(MARKDOWN_DOC_FILES),
            actual_md_files,
            "MARKDOWN_DOC_FILES must include every .md file in the repository.",
        )
        for rel_path in MARKDOWN_DOC_FILES:
            text = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
            for line in extract_markdown_prose_lines(text):
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
                for sentence in sentences:
                    words = re.findall(r"[A-Za-z0-9_./:-]+", sentence)
                    self.assertLessEqual(
                        len(words),
                        20,
                        f"{rel_path}: prose sentence exceeds 20 words ({len(words)}): {sentence}",
                    )

    def test_no_leaked_internal_identifiers(self):
        for file_path in iter_repo_files():
            rel = file_path.relative_to(REPO_ROOT).as_posix()
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            lowered = text.lower()

            for size in FORBIDDEN_TOKEN_LENGTHS:
                if len(lowered) < size:
                    continue
                for idx in range(len(lowered) - size + 1):
                    digest = hashlib.sha256(lowered[idx : idx + size].encode("utf-8")).hexdigest()
                    self.assertNotIn(
                        digest,
                        FORBIDDEN_TOKEN_SHA256,
                        f"{rel}: detected forbidden internal identifier substring.",
                    )

            for pattern, label in FORBIDDEN_REGEXES:
                self.assertIsNone(
                    pattern.search(text),
                    f"{rel}: detected forbidden {label}.",
                )

    def test_no_decorative_emojis_or_section_symbol(self):
        section_char = "\u00a7"
        for file_path in iter_repo_files():
            rel = file_path.relative_to(REPO_ROOT).as_posix()
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(section_char, text, f"{rel}: forbidden section symbol found.")
            self.assertIsNone(
                EMOJI_PATTERN.search(text),
                f"{rel}: decorative emoji character found.",
            )

    def test_no_blacklisted_ai_words(self):
        pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(word) for word in AI_BLACKLIST) + r")\b",
            re.IGNORECASE,
        )
        for file_path in iter_repo_files():
            rel = file_path.relative_to(REPO_ROOT).as_posix()
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            if file_path.resolve() == THIS_FILE:
                text = re.sub(
                    r"# BEGIN_AI_BLACKLIST.*?# END_AI_BLACKLIST",
                    "",
                    text,
                    flags=re.DOTALL,
                )
            match = pattern.search(text)
            self.assertIsNone(
                match,
                f"{rel}: forbidden AI filler term '{match.group(0) if match else ''}'.",
            )


if __name__ == "__main__":
    unittest.main()
