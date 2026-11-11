"""Hermetic integrity tests for the gcp-data-medallion Dataform repository."""

import hashlib
import re
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
    "allow_untagged_pii",
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
    ".github/workflows/ci.yml",
    "quality/silver_orders_quality.yaml",
    ".agents/skills/add-medallion-model/SKILL.md",
    ".agents/skills/split-domain-mesh/SKILL.md",
    "definitions/01_bronze/pos_orders_cdc.sqlx",
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
    ".agents/skills/add-medallion-model/SKILL.md",
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


class MedallionIntegrityTest(unittest.TestCase):
    """Validate Dataform config, SQLX medallion contracts, docs, and repository hygiene."""

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
        self.assertEqual(vars_map["pii_policy_tag"], "")
        self.assertEqual(vars_map["allow_untagged_pii"], "true")

    def test_includes_helpers_present(self):
        expected_exports = {
            "includes/audit_columns.js": ("ingestedAtSql", "recordHashSql"),
            "includes/policy_tags.js": ("allowUntaggedPii", "piiColumnConfig"),
            "includes/scd_type2.js": ("scd2WindowColumnsSql", "buildScd2Query"),
        }
        for rel_path, symbols in expected_exports.items():
            full_path = REPO_ROOT / rel_path
            self.assertTrue(full_path.is_file(), f"Missing helper file: {rel_path}")
            content = full_path.read_text(encoding="utf-8")
            for symbol in symbols:
                self.assertIn(symbol, content, f"{rel_path} must define {symbol}.")

    def test_sqlx_definitions_and_layer_contracts(self):
        definitions_dir = REPO_ROOT / "definitions"
        sqlx_files = sorted(definitions_dir.rglob("*.sqlx"))
        self.assertEqual(
            len(sqlx_files),
            7,
            "Expected 2 Bronze, 2 Silver tables, 1 Silver assertion, and 2 Gold SQLX files.",
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
                if model_type in ("table", "incremental"):
                    self.assertRegex(
                        config_body,
                        r"\bassertions\s*:\s*\{",
                        f"{rel}: Gold tables must define assertions.",
                    )

            if rel.startswith("definitions/03_gold/") and '${ref("fct_orders")}' in raw_text:
                self.assertRegex(
                    clean_sql,
                    r"\bWHERE\b[\s\S]*\border_date\b",
                    f"{rel}: queries over fct_orders must filter on order_date.",
                )

        fct_orders = (REPO_ROOT / "definitions/02_silver/fct_orders.sqlx").read_text(encoding="utf-8")
        self.assertIn("store_id", fct_orders)
        self.assertIn("policy_tags.piiColumnConfig", fct_orders)

        dim_customers = (REPO_ROOT / "definitions/02_silver/dim_customers.sqlx").read_text(
            encoding="utf-8"
        )
        self.assertIn("scd_type2.", dim_customers)
        self.assertRegex(dim_customers, r"customer_name\s*:\s*policy_tags\.piiColumnConfig\(")
        self.assertRegex(dim_customers, r"customer_ic_number\s*:\s*policy_tags\.piiColumnConfig\(")

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
        self.assertIn("workflow_settings.yaml", readme)
        self.assertIn("3.1.5", readme)
        self.assertIn("> [!NOTE]", readme)
        self.assertIn("google_bigquery_reservation", readme)
        self.assertIn("modules/data/bigquery-reservations/", readme)
        self.assertIn("Who Creates Bronze Tables", readme)
        self.assertIn("Why Dataform Over dbt", readme)
        self.assertNotIn("25 data engineers", readme)
        for var_name in REQUIRED_VARS:
            self.assertIn(var_name, readme)

        split_skill = (REPO_ROOT / ".agents/skills/split-domain-mesh/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("25 data engineers", split_skill)

    def test_markdown_prose_sentence_length(self):
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
